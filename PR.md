# PR: Fix 4 Framework Stability Bugs + Add 193 Edge Case Tests

## Summary

Fixes 4 confirmed bugs that would bite framework users in production, and adds 193 new edge-case tests across all core modules. (168 existing → 361 total)

## Bugs Fixed

### 1. `BeanCollection.scan_beans()` crashes with `KeyError('return')` on missing annotation

**Before:** If a `create_*` method lacks a return type annotation, users get an unhelpful `KeyError: 'return'`.
**After:** Raises `TypeError` with message: `"Bean creation method 'create_service' in MyCollection must have a return type annotation"`.

**File:** `py_spring_core/core/entities/bean_collection/bean_collection.py`

### 2. Prototype-scoped components never get `post_construct()` called

**Before:** `ComponentManager.get_component()` creates a Prototype instance and injects dependencies, but never calls `finish_initialization_cycle()`. Singleton components get it via `_handle_singleton_components_life_cycle()`, but prototypes are silently skipped.
**After:** `finish_initialization_cycle()` is called after dependency injection for prototype instances.

**File:** `py_spring_core/core/application/context/application_context.py`

### 3. DI crashes on non-injectable annotations with defaults (`config: dict = {}`)

**Before:** The injector iterates ALL class annotations. If a Component has `config: dict = {}`, the injector tries collection injection (fails), then entity injection (fails), then raises `ValueError`. Users expect default-valued attributes to be left alone.
**After:** Before raising an injection error, checks if the attribute has a default value. If it does and the type isn't injectable, the attribute is skipped with a debug log.

**File:** `py_spring_core/core/application/context/application_context.py`

### 4. Abstract class dependency resolution only checks direct `__subclasses__()`

**Before:** `_determine_target_cls_name()` and `_get_abstract_class_component_subclasses()` only check `cls.__subclasses__()`. A deeper hierarchy like `ABC -> MiddleABC -> ConcreteImpl` fails to resolve because `__subclasses__()` on the base returns `[MiddleABC]`, not `[ConcreteImpl]`.
**After:** Both methods recursively traverse the subclass tree, skipping abstract intermediaries and collecting only concrete implementations.

**File:** `py_spring_core/core/application/context/application_context.py`

## Test Coverage Added (193 new tests)

| Test File | Tests | Coverage |
| --- | --- | --- |
| `test_dependency_injection_edge_cases.py` | 30 | Missing deps, qualifiers, abstract classes, prototype DI, collection injection |
| `test_route_mapping_edge_cases.py` | 28 | Route equality/hash, all HTTP decorators, drain behavior, FastAPI params, edge case paths |
| `test_component_lifecycle.py` | 27 | Lifecycle hooks, Config scope inheritance/isolation, singleton vs prototype |
| `test_event_system.py` | 20 | EventListener decorator, drain behavior, EventHandler equality |
| `test_properties_edge_cases.py` | 18 | Key validation, nested models, optional fields, JSON/YAML loading |
| `test_framework_bugs.py` | 17 | Bug regression tests + documented surprising behaviors |
| `test_bean_collection_edge_cases.py` | 16 | Bean scanning, name validation, duplicates, bean-into-component injection |
| `test_rest_controller_edge_cases.py` | 16 | Router guards, prefix handling, all HTTP methods E2E, controller DI |
| `test_exception_handler.py` | 13 | Decorator registration, duplicate detection, drain behavior |
| `test_single_inheritance_required.py` | 8 | Subclass enforcement, ApplicationContextRequired |
| **Total new** | **193** | **168 existing + 193 new = 361 total** |

## Test Plan

- [x] All 361 tests pass (`pytest tests/ -v`)
- [x] No xfailed tests remain — all 4 bugs are fixed
- [x] Existing 168 tests unaffected
- [x] Each bug fix has a dedicated regression test in `test_framework_bugs.py`

## Files Changed

| File | Change |
| --- | --- |
| `py_spring_core/core/entities/bean_collection/bean_collection.py` | Add return annotation check in `scan_beans()` |
| `py_spring_core/core/application/context/application_context.py` | Fix prototype lifecycle, DI default handling, recursive abstract resolution |
| `tests/test_framework_bugs.py` | **New** — 17 bug regression + edge case tests |
| `tests/test_dependency_injection_edge_cases.py` | **New** — 30 DI tests |
| `tests/test_route_mapping_edge_cases.py` | **New** — 28 route mapping tests |
| `tests/test_component_lifecycle.py` | **New** — 27 component lifecycle tests |
| `tests/test_event_system.py` | **New** — 20 event system tests |
| `tests/test_properties_edge_cases.py` | **New** — 18 properties tests |
| `tests/test_bean_collection_edge_cases.py` | **New** — 16 bean collection tests |
| `tests/test_rest_controller_edge_cases.py` | **New** — 16 controller tests |
| `tests/test_exception_handler.py` | **New** — 13 exception handler tests |
| `tests/test_single_inheritance_required.py` | **New** — 8 inheritance tests |
