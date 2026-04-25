# Subclass-based PySpringStarter Auto-Configuration

## Problem

`PySpringStarter` is a passive data holder. There is no way to subclass it and define a self-contained, reusable starter that auto-registers its own entities. Additionally, `set_context()` is never called, so starters cannot access the IoC container during `starter_init()`.

## Goal

Enable subclass-based auto-configuration via a `configure()` hook, and wire up `set_context()` so starters have `ApplicationContext` access during initialization.

## Design Decision

`configure()` is an **explicit lifecycle step** called by the framework — NOT lazily triggered inside `get_entities()`. Getters must remain pure (no side effects, no hidden mutation).

Framework lifecycle:

```
for s in starters:
    s.configure()          # explicit mutation step

for s in starters:
    entities = s.get_entities()  # pure read
```

---

## Stage 1: Add `configure()` hook to `PySpringStarter`

**Goal**: Allow subclasses to override `configure()` to register their own entities.

**File**: `py_spring_core/core/starter/py_spring_starter.py`

**Changes**:
- Add `configure(self) -> None` method (no-op base implementation)
- `get_entities()` remains a **pure getter** — no side effects

**Success Criteria**:
- Subclass overriding `configure()` can append to `component_classes`, `bean_collection_classes`, etc.
- `get_entities()` returns entities registered in `configure()` — but only if `configure()` was called first by the caller
- Existing dataclass-style usage (`PySpringStarter(component_classes=[...])`) still works

**Status**: Not Started

---

## Stage 2: Wire up explicit lifecycle in `PySpringApplication`

**Goal**: Framework explicitly calls `configure()` before collecting entities, and `set_context()` before `starter_init()`.

**File**: `py_spring_core/core/application/py_spring_application.py`

**Changes**:
- Add `_configure_starters(self, starters)` — calls `configure()` on each starter
- Call `_configure_starters()` in `_prepare_injected_classes()` before `_get_all_entities_from_starters()`
- Add `_set_context_for_starters(self, starters)` — calls `set_context(app_context)` on each starter
- Call `_set_context_for_starters()` in `_init_app()` before `_init_starters()`

**Lifecycle in `_init_app()`**:
```
_prepare_injected_classes:
    _configure_starters(starters)     # 1. configure
    _get_all_entities_from_starters() # 2. pure read
...
_set_context_for_starters(starters)   # 3. inject context
_init_starters(starters)              # 4. starter_init()
```

**Success Criteria**:
- All starters are configured before any entities are collected
- After `_init_app()`, every starter has `app_context` set
- `starter_init()` can safely access `self.app_context`

**Status**: Not Started

---

## Stage 3: Tests

**Goal**: Verify all new behavior and backward compatibility.

**File**: `tests/test_starter.py`

**Test Cases**:

1. **Subclass configure populates entities** — A `PySpringStarter` subclass overrides `configure()` to append a component class; after calling `configure()`, `get_entities()` returns it.

2. **get_entities is pure without configure** — Calling `get_entities()` without first calling `configure()` returns only dataclass-provided entities (no implicit configure).

3. **set_context provides app_context** — After calling `set_context(mock_context)`, `starter.app_context` is the mock context.

4. **starter_init can use app_context** — A subclass accessing `self.app_context` in `starter_init()` works without error after `set_context()`.

5. **Backward compatibility** — A plain `PySpringStarter(component_classes=[SomeComponent])` still returns the component from `get_entities()`.

**Success Criteria**:
- All tests pass
- Existing tests still pass

**Status**: Not Started

---

## Verification

```bash
pytest tests/test_starter.py -v
pytest tests/ -v
```
