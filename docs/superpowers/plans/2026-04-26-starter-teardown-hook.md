# Starter Teardown Hook (`on_destroy`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `on_destroy()` teardown lifecycle hook to `PySpringStarter` so starters can clean up resources during application shutdown.

**Architecture:** Mirror `Component`'s `pre_destroy()` / `finish_destruction_cycle()` pattern. Add `on_destroy()` as a no-op override point and `@final finish_destruction_cycle()` as a framework wrapper on `PySpringStarter`. Wire `_notify_starters_destroyed()` into `PySpringApplication.run()`'s `finally` block after component destruction.

**Tech Stack:** Python 3.11+, pytest, dataclasses, typing.final

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `py_spring_core/core/starter/py_spring_starter.py` | Modify | Add `on_destroy()` and `finish_destruction_cycle()` |
| `py_spring_core/core/application/py_spring_application.py` | Modify | Add `_notify_starters_destroyed()`, wire into `finally` block |
| `tests/test_starter.py` | Modify | Add teardown lifecycle tests |

---

### Task 1: Add `on_destroy` and `finish_destruction_cycle` to `PySpringStarter`

**Files:**
- Modify: `py_spring_core/core/starter/py_spring_starter.py`
- Test: `tests/test_starter.py`

- [x] **Step 1: Write failing tests for `on_destroy` and `finish_destruction_cycle`**

Add to `tests/test_starter.py`. First, add a new test helper class after the existing `ContextAwareStarter` (line 59):

```python
class DestroyAwareStarter(PySpringStarter):
    destroyed: bool = False

    def on_destroy(self) -> None:
        self.destroyed = True
```

Then add these tests inside the existing `TestStarterLifecycle` class (after line 95):

```python
    def test_on_destroy_default_is_noop(self):
        starter = PySpringStarter()
        starter.on_destroy()

    def test_finish_destruction_cycle_calls_on_destroy(self):
        starter = DestroyAwareStarter()
        assert not starter.destroyed
        starter.finish_destruction_cycle()
        assert starter.destroyed
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_starter.py::TestStarterLifecycle::test_on_destroy_default_is_noop tests/test_starter.py::TestStarterLifecycle::test_finish_destruction_cycle_calls_on_destroy -v`

Expected: FAIL — `AttributeError: 'PySpringStarter' object has no attribute 'on_destroy'` and `'finish_destruction_cycle'`

- [x] **Step 3: Implement `on_destroy` and `finish_destruction_cycle` on `PySpringStarter`**

In `py_spring_core/core/starter/py_spring_starter.py`:

1. Add `final` to the typing import (line 1):

```python
from typing import Any, Optional, Type, final
```

2. Add two methods after the existing `on_initialized()` method (after line 53):

```python
    def on_destroy(self) -> None:
        """Override in subclasses for cleanup logic before the starter is destroyed.

        Called by the framework during application shutdown, after all singleton
        components have been destroyed.
        """
        ...

    @final
    def finish_destruction_cycle(self) -> None:
        self.on_destroy()
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_starter.py::TestStarterLifecycle -v`

Expected: All tests in `TestStarterLifecycle` PASS (including both new tests)

- [x] **Step 5: Commit**

```bash
git add py_spring_core/core/starter/py_spring_starter.py tests/test_starter.py
git commit -m "feat: add on_destroy teardown hook to PySpringStarter

Mirror Component's pre_destroy/finish_destruction_cycle pattern so
starters can clean up resources during application shutdown."
```

---

### Task 2: Wire starter teardown into `PySpringApplication.run()`

**Files:**
- Modify: `py_spring_core/core/application/py_spring_application.py`
- Test: `tests/test_starter.py`

- [x] **Step 1: Write failing test for teardown ordering**

Add a new test helper class to `tests/test_starter.py` after `DestroyAwareStarter`:

```python
class OrderTrackingComponent(Component):
    order_log: list[str] = []

    def pre_destroy(self) -> None:
        OrderTrackingComponent.order_log.append("component_pre_destroy")


class OrderTrackingStarter(PySpringStarter):
    order_log: list[str] = []

    def on_destroy(self) -> None:
        OrderTrackingStarter.order_log.append("starter_on_destroy")
```

Add a new test class after `TestStarterLifecycle`:

```python
class TestStarterTeardownOrdering:
    def test_on_destroy_called_after_component_pre_destroy(self):
        from py_spring_core.core.application.py_spring_application import (
            PySpringApplication,
        )

        OrderTrackingComponent.order_log = []
        OrderTrackingStarter.order_log = []
        shared_log: list[str] = []

        original_component_pre_destroy = OrderTrackingComponent.pre_destroy
        original_starter_on_destroy = OrderTrackingStarter.on_destroy

        def tracked_component_pre_destroy(self):
            shared_log.append("component_pre_destroy")
            original_component_pre_destroy(self)

        def tracked_starter_on_destroy(self):
            shared_log.append("starter_on_destroy")
            original_starter_on_destroy(self)

        OrderTrackingComponent.pre_destroy = tracked_component_pre_destroy
        OrderTrackingStarter.on_destroy = tracked_starter_on_destroy

        try:
            starter = OrderTrackingStarter(
                component_classes=[OrderTrackingComponent],
            )
            app = PySpringApplication.__new__(PySpringApplication)
            app.starters = [starter]

            server = FastAPI()
            app.app_context = ApplicationContext(
                ApplicationContextConfig(properties_path=""), server=server
            )
            app.app_context.register_component(OrderTrackingComponent)
            app.app_context.init_ioc_container()
            app.app_context.inject_dependencies_for_app_entities()
            app._handle_singleton_components_life_cycle(
                ComponentLifeCycle.Init
            )

            # Simulate teardown
            app._handle_singleton_components_life_cycle(
                ComponentLifeCycle.Destruction
            )
            app._notify_starters_destroyed(app.starters)

            assert shared_log == [
                "component_pre_destroy",
                "starter_on_destroy",
            ]
        finally:
            OrderTrackingComponent.pre_destroy = original_component_pre_destroy
            OrderTrackingStarter.on_destroy = original_starter_on_destroy
```

Also add the missing import at the top of the test file:

```python
from py_spring_core.core.entities.component.component import Component, ComponentLifeCycle
```

(Replace the existing `Component`-only import on line 12.)

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_starter.py::TestStarterTeardownOrdering::test_on_destroy_called_after_component_pre_destroy -v`

Expected: FAIL — `AttributeError: 'PySpringApplication' object has no attribute '_notify_starters_destroyed'`

- [x] **Step 3: Implement `_notify_starters_destroyed` and wire into `run()`**

In `py_spring_core/core/application/py_spring_application.py`:

1. Add the helper method after `_notify_starters_initialized` (after line 190):

```python
    def _notify_starters_destroyed(self, starters: Iterable[PySpringStarter]) -> None:
        for starter in starters:
            starter.finish_destruction_cycle()
```

2. Wire into the `finally` block of `run()` (line 421–426). Replace:

```python
        finally:
            # Handle component lifecycle destruction
            self._handle_singleton_components_life_cycle(ComponentLifeCycle.Destruction)
            # Handle graceful shutdown completion
            if self.shutdown_handler:
                self.shutdown_handler.complete_shutdown()
```

With:

```python
        finally:
            self._handle_singleton_components_life_cycle(ComponentLifeCycle.Destruction)
            self._notify_starters_destroyed(self.starters)
            if self.shutdown_handler:
                self.shutdown_handler.complete_shutdown()
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_starter.py::TestStarterTeardownOrdering -v`

Expected: PASS

- [x] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v`

Expected: All tests PASS

- [x] **Step 6: Commit**

```bash
git add py_spring_core/core/application/py_spring_application.py tests/test_starter.py
git commit -m "feat: wire starter on_destroy into application shutdown lifecycle

Starters are now notified during teardown in reverse-of-init order:
components pre_destroy first, then starter on_destroy."
```
