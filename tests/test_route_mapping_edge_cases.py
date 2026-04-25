"""
Edge case tests for route mapping decorators and RouteRegistration.

Covers:
- All HTTP method decorators (GET, POST, PUT, DELETE, PATCH)
- RouteRegistration equality/hash semantics
- Pending routes drain behavior (idempotency, interleaving)
- Decorator with all FastAPI-compatible parameters
- Edge cases: empty path, special characters, nested class methods
- Route deduplication in sets
- Multiple decorators on different methods of same controller
"""

import pytest

from py_spring_core.core.entities.controllers.route_mapping import (
    DeleteMapping,
    GetMapping,
    HTTPMethod,
    PatchMapping,
    PostMapping,
    PutMapping,
    RouteRegistration,
    _pending_routes,
    drain_pending_routes,
)


@pytest.fixture(autouse=True)
def clean_pending_routes():
    """Ensure pending routes are drained before and after each test."""
    _pending_routes.clear()
    yield
    _pending_routes.clear()


class TestRouteRegistrationEquality:

    def test_same_method_and_path_are_equal(self):
        def handler_a(): ...
        def handler_b(): ...

        r1 = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler_a)
        r2 = RouteRegistration(class_name="B", method=HTTPMethod.GET, path="/foo", func=handler_b)
        assert r1 == r2

    def test_different_method_same_path_not_equal(self):
        def handler(): ...
        r1 = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler)
        r2 = RouteRegistration(class_name="A", method=HTTPMethod.POST, path="/foo", func=handler)
        assert r1 != r2

    def test_same_method_different_path_not_equal(self):
        def handler(): ...
        r1 = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler)
        r2 = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/bar", func=handler)
        assert r1 != r2

    def test_equality_with_non_route_registration_returns_false(self):
        def handler(): ...
        r = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler)
        assert r != "not a route"
        assert r != 42
        assert r != None

    def test_hash_consistency_for_equal_routes(self):
        def handler(): ...
        r1 = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler)
        r2 = RouteRegistration(class_name="B", method=HTTPMethod.GET, path="/foo", func=handler)
        assert hash(r1) == hash(r2)

    def test_routes_in_set_deduplicate_by_method_and_path(self):
        def handler(): ...
        r1 = RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler)
        r2 = RouteRegistration(class_name="B", method=HTTPMethod.GET, path="/foo", func=handler)
        route_set = {r1, r2}
        assert len(route_set) == 1

    def test_routes_in_set_keep_different_methods(self):
        def handler(): ...
        routes = {
            RouteRegistration(class_name="A", method=HTTPMethod.GET, path="/foo", func=handler),
            RouteRegistration(class_name="A", method=HTTPMethod.POST, path="/foo", func=handler),
            RouteRegistration(class_name="A", method=HTTPMethod.PUT, path="/foo", func=handler),
            RouteRegistration(class_name="A", method=HTTPMethod.DELETE, path="/foo", func=handler),
            RouteRegistration(class_name="A", method=HTTPMethod.PATCH, path="/foo", func=handler),
        }
        assert len(routes) == 5


# --- Module-level classes for decorator tests (qualname must be ClassName.method) ---

class _DrainCtrl:
    @GetMapping("/a")
    def get_a(self): ...

    @PostMapping("/b")
    def post_b(self): ...


class _GetCtrl:
    @GetMapping("/items")
    def list_items(self): ...


class _PostCtrl:
    @PostMapping("/items")
    def create_item(self): ...


class _PutCtrl:
    @PutMapping("/items/{id}")
    def update_item(self): ...


class _DeleteCtrl:
    @DeleteMapping("/items/{id}")
    def delete_item(self): ...


class _PatchCtrl:
    @PatchMapping("/items/{id}")
    def patch_item(self): ...


class _ParamsCtrl:
    @GetMapping(
        "/items",
        response_model=dict,
        status_code=201,
        tags=["items", "v1"],
        summary="List all items",
        description="Returns a list of all items in the system",
        response_description="A list of items",
        deprecated=True,
        operation_id="listAllItems",
        response_model_include={"id", "name"},
        response_model_exclude={"secret"},
        response_model_by_alias=False,
        response_model_exclude_unset=True,
        response_model_exclude_defaults=True,
        response_model_exclude_none=True,
        include_in_schema=False,
        name="list_items_v1",
    )
    def list_items(self): ...


class _DefaultsCtrl:
    @GetMapping("/items")
    def list_items(self): ...


class _SummaryCtrl:
    @GetMapping("/items")
    def my_special_handler(self): ...


class _DocstringCtrl:
    @GetMapping("/items")
    def handler(self):
        """This is the handler docstring."""
        ...


class _EmptyPathCtrl:
    @GetMapping("")
    def root(self): ...


class _RootSlashCtrl:
    @GetMapping("/")
    def root(self): ...


class _MultiParamCtrl:
    @GetMapping("/users/{user_id}/posts/{post_id}/comments/{comment_id}")
    def get_comment(self): ...


class _ItemController:
    @GetMapping("/items")
    def list_items(self): ...

    @PostMapping("/items")
    def create_item(self): ...

    @GetMapping("/items/{id}")
    def get_item(self): ...

    @PutMapping("/items/{id}")
    def update_item(self): ...

    @DeleteMapping("/items/{id}")
    def delete_item(self): ...


class _UserController:
    @GetMapping("/users")
    def list_users(self): ...


class _ItemController2:
    @GetMapping("/items2")
    def list_items(self): ...


class _WrapTestCtrl:
    @GetMapping("/items")
    def list_items(self):
        return "items"


class _DocWrapCtrl:
    @GetMapping("/items")
    def list_items(self):
        """Get all items."""
        return "items"


# Drain all module-level registrations so they don't pollute test isolation
_module_level_routes = drain_pending_routes()


class TestDrainPendingRoutes:

    def test_drain_returns_all_pending_and_clears(self):
        _pending_routes.extend(_module_level_routes[:2])  # reuse 2 routes
        drained = drain_pending_routes()
        assert len(drained) == 2
        assert len(_pending_routes) == 0

    def test_drain_twice_returns_empty_on_second_call(self):
        _pending_routes.append(_module_level_routes[0])
        drain_pending_routes()
        assert drain_pending_routes() == []

    def test_drain_returns_copy_not_reference(self):
        _pending_routes.append(_module_level_routes[0])
        drained = drain_pending_routes()
        drained.append(None)  # type: ignore
        assert len(_pending_routes) == 0

    def test_drain_preserves_registration_order(self):
        # Use routes that have distinct paths
        ordered = [r for r in _module_level_routes if r.class_name == "_DrainCtrl"]
        _pending_routes.extend(ordered)
        drained = drain_pending_routes()
        paths = [r.path for r in drained]
        assert paths == ["/a", "/b"]


class TestAllHttpMethodDecorators:

    def test_get_mapping_registers_correct_method(self):
        routes = [r for r in _module_level_routes if r.class_name == "_GetCtrl"]
        assert len(routes) == 1
        assert routes[0].method == HTTPMethod.GET
        assert routes[0].path == "/items"
        assert routes[0].class_name == "_GetCtrl"

    def test_post_mapping_registers_correct_method(self):
        routes = [r for r in _module_level_routes if r.class_name == "_PostCtrl"]
        assert len(routes) == 1
        assert routes[0].method == HTTPMethod.POST

    def test_put_mapping_registers_correct_method(self):
        routes = [r for r in _module_level_routes if r.class_name == "_PutCtrl"]
        assert len(routes) == 1
        assert routes[0].method == HTTPMethod.PUT

    def test_delete_mapping_registers_correct_method(self):
        routes = [r for r in _module_level_routes if r.class_name == "_DeleteCtrl"]
        assert len(routes) == 1
        assert routes[0].method == HTTPMethod.DELETE

    def test_patch_mapping_registers_correct_method(self):
        routes = [r for r in _module_level_routes if r.class_name == "_PatchCtrl"]
        assert len(routes) == 1
        assert routes[0].method == HTTPMethod.PATCH


class TestDecoratorParameters:

    def test_all_fastapi_params_are_forwarded(self):
        routes = [r for r in _module_level_routes if r.class_name == "_ParamsCtrl"]
        assert len(routes) == 1
        route = routes[0]
        assert route.response_model == dict
        assert route.status_code == 201
        assert route.tags == ["items", "v1"]
        assert route.summary == "List all items"
        assert route.description == "Returns a list of all items in the system"
        assert route.response_description == "A list of items"
        assert route.deprecated is True
        assert route.operation_id == "listAllItems"
        assert route.response_model_include == {"id", "name"}
        assert route.response_model_exclude == {"secret"}
        assert route.response_model_by_alias is False
        assert route.response_model_exclude_unset is True
        assert route.response_model_exclude_defaults is True
        assert route.response_model_exclude_none is True
        assert route.include_in_schema is False
        assert route.name == "list_items_v1"

    def test_default_values_when_no_params_specified(self):
        routes = [r for r in _module_level_routes if r.class_name == "_DefaultsCtrl"]
        assert len(routes) == 1
        route = routes[0]
        assert route.response_model is None
        assert route.status_code is None
        assert route.tags is None
        assert route.deprecated is None
        assert route.response_description == "Successful Response"
        assert route.response_model_by_alias is True
        assert route.response_model_exclude_unset is False
        assert route.response_model_exclude_defaults is False
        assert route.response_model_exclude_none is False
        assert route.include_in_schema is True

    def test_summary_defaults_to_function_name(self):
        routes = [r for r in _module_level_routes if r.class_name == "_SummaryCtrl"]
        assert len(routes) == 1
        assert routes[0].summary == "my_special_handler"

    def test_description_uses_docstring_when_not_specified(self):
        routes = [r for r in _module_level_routes if r.class_name == "_DocstringCtrl"]
        assert len(routes) == 1
        assert routes[0].description == "This is the handler docstring."


class TestEdgeCasePaths:

    def test_empty_path(self):
        routes = [r for r in _module_level_routes if r.class_name == "_EmptyPathCtrl"]
        assert len(routes) == 1
        assert routes[0].path == ""

    def test_root_slash_path(self):
        routes = [r for r in _module_level_routes if r.class_name == "_RootSlashCtrl"]
        assert len(routes) == 1
        assert routes[0].path == "/"

    def test_path_with_multiple_params(self):
        routes = [r for r in _module_level_routes if r.class_name == "_MultiParamCtrl"]
        assert len(routes) == 1
        assert routes[0].path == "/users/{user_id}/posts/{post_id}/comments/{comment_id}"


class TestMultipleRoutesOnSameController:

    def test_multiple_methods_on_same_controller_class(self):
        routes = [r for r in _module_level_routes if r.class_name == "_ItemController"]
        assert len(routes) == 5
        class_names = {r.class_name for r in routes}
        assert class_names == {"_ItemController"}

    def test_routes_from_different_controllers_are_separate(self):
        user_routes = [r for r in _module_level_routes if r.class_name == "_UserController"]
        item_routes = [r for r in _module_level_routes if r.class_name == "_ItemController2"]
        assert len(user_routes) == 1
        assert len(item_routes) == 1


class TestDecoratorPreservesFunction:

    def test_wrapped_function_retains_original_name(self):
        assert _WrapTestCtrl.list_items.__name__ == "list_items"

    def test_wrapped_function_is_callable(self):
        c = _WrapTestCtrl()
        assert c.list_items() == "items"

    def test_wrapped_function_preserves_docstring(self):
        assert _DocWrapCtrl.list_items.__doc__ == "Get all items."
