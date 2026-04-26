# Starter Teardown Hook (`on_destroy`)

## Problem

`PySpringStarter` has initialization lifecycle hooks (`on_configure`, `on_initialized`) but no teardown hook. Starters that acquire resources (threads, connections, file handles) in `on_initialized()` have no framework-managed way to release them during application shutdown. This causes resource leaks in tests and non-server use cases.

## Approach

Mirror the `Component` lifecycle pattern: add `on_destroy()` as a no-op override point and `finish_destruction_cycle()` as a `@final` framework wrapper. Wire it into `PySpringApplication.run()`'s `finally` block in reverse-of-init order.

## Changes

### 1. `PySpringStarter` (py_spring_core/core/starter/py_spring_starter.py)

Add two methods:

- `on_destroy(self) -> None` — no-op, subclasses override for cleanup logic. Called after all singleton components are destroyed.
- `finish_destruction_cycle(self) -> None` — `@final` wrapper that calls `on_destroy()`. Gives the framework a hook for future error isolation or logging.

Requires adding `final` to imports from `typing`.

### 2. `PySpringApplication` (py_spring_core/core/application/py_spring_application.py)

Add helper method:

- `_notify_starters_destroyed(self, starters: Iterable[PySpringStarter]) -> None` — iterates starters and calls `finish_destruction_cycle()` on each.

Wire into `run()`'s `finally` block after component destruction, before shutdown handler completion:

```
finally:
    self._handle_singleton_components_life_cycle(ComponentLifeCycle.Destruction)
    self._notify_starters_destroyed(self.starters)          # NEW
    if self.shutdown_handler:
        self.shutdown_handler.complete_shutdown()
```

### 3. Full lifecycle after change

**Init order:**
1. `starter.on_configure()` — pre-IoC setup
2. IoC container build + dependency injection
3. `starter.on_initialized()` — post-IoC, resources can be acquired
4. `component.post_construct()` — component init

**Teardown order (reverse of init):**
1. `component.pre_destroy()` — component cleanup
2. `starter.on_destroy()` — starter cleanup (resources released)
3. `shutdown_handler.complete_shutdown()` — final shutdown

### 4. Tests (tests/test_starter.py)

Add to existing `TestStarterLifecycle` class:

- `test_on_destroy_default_is_noop` — calling `on_destroy()` on base `PySpringStarter` does not raise.
- `test_finish_destruction_cycle_calls_on_destroy` — subclass sets a flag in `on_destroy()`, verify `finish_destruction_cycle()` triggers it.
- `test_on_destroy_called_after_component_pre_destroy` — verify ordering: component `pre_destroy()` runs before starter `on_destroy()`.

## Out of scope

- Specific starter implementations (e.g., scheduler starter) — those will use this hook once it exists.
- Error handling within `on_destroy()` (e.g., catching exceptions from one starter so others still run) — can be added to `finish_destruction_cycle()` later without breaking subclasses.
