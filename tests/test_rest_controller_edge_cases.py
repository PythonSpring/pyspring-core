"""
Edge case tests for RestController registration, routing, and initialization.

Covers:
- Controller with empty prefix
- Controller with nested prefix
- must_get_router raises when not initialized
- get_router returns None before init
- Multiple controllers with different prefixes
- Controller with all HTTP method routes
- Controller dependency injection
- _register_decorated_routes with no routes
- Controller post_construct hook
"""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from py_spring_core.core.application.application_registry import ApplicationRegistry
from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import Component
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.controllers.route_mapping import (
    GetMapping,
    PostMapping,
    PutMapping,
    DeleteMapping,
    PatchMapping,
    RouteRegistration,
    HTTPMethod,
    _pending_routes,
    drain_pending_routes,
)


@pytest.fixture(autouse=True)
def clean_pending_routes():
    _pending_routes.clear()
    yield
    _pending_routes.clear()


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI):
    config = ApplicationContextConfig(properties_path="")
    registry = ApplicationRegistry()
    return ApplicationContext(config, server=server, registry=registry)


class TestControllerBasics:

    def test_get_name_returns_class_name(self):
        class UserController(RestController):
            class Config:
                prefix = "/users"

        assert UserController.get_name() == "UserController"

    def test_get_router_prefix(self):
        class ItemController(RestController):
            class Config:
                prefix = "/api/v1/items"

        assert ItemController.get_router_prefix() == "/api/v1/items"

    def test_default_prefix_is_empty(self):
        class RootController(RestController):
            pass

        assert RootController.get_router_prefix() == ""

    def test_get_router_returns_none_before_init(self):
        ctrl = RestController()
        assert ctrl.get_router() is None

    def test_must_get_router_raises_when_not_initialized(self):
        ctrl = RestController()
        with pytest.raises(LookupError, match="Router not initialized"):
            ctrl.must_get_router()

    def test_must_get_router_returns_router_after_init(self):
        ctrl = RestController()
        ctrl.router = APIRouter()
        router = ctrl.must_get_router()
        assert isinstance(router, APIRouter)


class TestControllerRegistration:

    def test_register_controller(self, app_context: ApplicationContext):
        class TestCtrl(RestController):
            class Config:
                prefix = "/test"

        app_context.register_controller(TestCtrl)
        assert "TestCtrl" in app_context.container_manager.controller_classes

    def test_register_non_controller_raises(self, app_context: ApplicationContext):
        class NotAController:
            pass

        with pytest.raises(TypeError, match="CONTROLLER REGISTRATION ERROR"):
            app_context.register_controller(NotAController)  # type: ignore

    def test_get_controller_instances(self, app_context: ApplicationContext):
        class CtrlA(RestController):
            class Config:
                prefix = "/a"

        class CtrlB(RestController):
            class Config:
                prefix = "/b"

        app_context.register_controller(CtrlA)
        app_context.register_controller(CtrlB)

        instances = app_context.get_controller_instances()
        assert len(instances) == 2
        class_names = {inst.__class__.__name__ for inst in instances}
        assert class_names == {"CtrlA", "CtrlB"}


class TestControllerRouteRegistration:

    def test_register_decorated_routes_with_no_routes(self, server: FastAPI):
        ctrl = RestController()
        ctrl.router = APIRouter()
        ctrl._register_decorated_routes([])
        assert len(ctrl.router.routes) == 0

    def test_register_decorated_routes_raises_without_router(self):
        ctrl = RestController()
        assert ctrl.router is None

        def dummy(self): ...
        route = RouteRegistration(
            class_name="Test", method=HTTPMethod.GET, path="/test", func=dummy
        )
        with pytest.raises(RuntimeError, match="Router not initialized"):
            ctrl._register_decorated_routes([route])


# --- Module-level classes for decorator-based integration tests ---

class _GreetService(Component):
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

class _GreetController(RestController):
    class Config:
        prefix = "/greet"

    service: _GreetService

    @GetMapping("/{name}")
    def greet(self, name: str):
        return {"message": self.service.greet(name)}


class _UserCtrl(RestController):
    class Config:
        prefix = "/users"

    @GetMapping("/")
    def list_users(self):
        return [{"id": 1, "name": "Alice"}]


class _ItemCtrl(RestController):
    class Config:
        prefix = "/items"

    @GetMapping("/")
    def list_items(self):
        return [{"id": 1, "title": "Widget"}]


class _CrudController(RestController):
    class Config:
        prefix = "/crud"

    @GetMapping("/resource")
    def get_resource(self):
        return {"action": "get"}

    @PostMapping("/resource")
    def create_resource(self):
        return {"action": "create"}

    @PutMapping("/resource/{id}")
    def update_resource(self, id: int):
        return {"action": "update", "id": id}

    @DeleteMapping("/resource/{id}")
    def delete_resource(self, id: int):
        return {"action": "delete", "id": id}

    @PatchMapping("/resource/{id}")
    def patch_resource(self, id: int):
        return {"action": "patch", "id": id}


# Drain module-level routes
_all_routes = drain_pending_routes()


def _routes_for(class_name: str) -> set[RouteRegistration]:
    return {r for r in _all_routes if r.class_name == class_name}


class TestControllerWithDependencyInjection:

    def test_controller_gets_dependencies_injected(self, server: FastAPI):
        config = ApplicationContextConfig(properties_path="")
        registry = ApplicationRegistry()
        ctx = ApplicationContext(config, server=server, registry=registry)

        ctx.register_component(_GreetService)
        ctx.register_controller(_GreetController)
        ctx.init_ioc_container()
        ctx.inject_dependencies_for_app_entities()

        greet_routes = _routes_for("_GreetController")
        registry.routes["_GreetController"] = greet_routes

        controllers = ctx.get_controller_instances()
        for ctrl in controllers:
            ctrl.app = server
            ctrl.router = APIRouter(prefix=ctrl.get_router_prefix())
            ctx.inject_dependencies_for_instance(ctrl)
            ctrl_routes = registry.routes.get(ctrl.__class__.__name__, set())
            ctrl._register_decorated_routes(ctrl_routes)
            ctrl.post_construct()
            server.include_router(ctrl.must_get_router())

        client = TestClient(server)
        resp = client.get("/greet/World")
        assert resp.status_code == 200
        assert resp.json() == {"message": "Hello, World!"}


class TestControllerPostConstruct:

    def test_post_construct_is_called(self):
        call_log = []

        class InitCtrl(RestController):
            def post_construct(self):
                call_log.append("post_construct")

        ctrl = InitCtrl()
        ctrl.post_construct()
        assert call_log == ["post_construct"]

    def test_default_post_construct_is_no_op(self):
        ctrl = RestController()
        ctrl.post_construct()


class TestMultipleControllersIntegration:

    def test_multiple_controllers_with_different_prefixes(self, server: FastAPI):
        registry = ApplicationRegistry()
        registry.routes["_UserCtrl"] = _routes_for("_UserCtrl")
        registry.routes["_ItemCtrl"] = _routes_for("_ItemCtrl")

        for ctrl_cls in [_UserCtrl, _ItemCtrl]:
            ctrl = ctrl_cls()
            ctrl.app = server
            ctrl.router = APIRouter(prefix=ctrl.get_router_prefix())
            ctrl_routes = registry.routes.get(ctrl_cls.__name__, set())
            ctrl._register_decorated_routes(ctrl_routes)
            server.include_router(ctrl.must_get_router())

        client = TestClient(server)

        users_resp = client.get("/users/")
        assert users_resp.status_code == 200
        assert len(users_resp.json()) == 1

        items_resp = client.get("/items/")
        assert items_resp.status_code == 200
        assert len(items_resp.json()) == 1


class TestControllerAllHttpMethods:

    def test_controller_with_all_methods(self, server: FastAPI):
        registry = ApplicationRegistry()
        registry.routes["_CrudController"] = _routes_for("_CrudController")

        ctrl = _CrudController()
        ctrl.app = server
        ctrl.router = APIRouter(prefix="/crud")
        ctrl._register_decorated_routes(registry.routes.get("_CrudController", set()))
        server.include_router(ctrl.must_get_router())

        client = TestClient(server)

        assert client.get("/crud/resource").status_code == 200
        assert client.post("/crud/resource").status_code == 200
        assert client.put("/crud/resource/1").status_code == 200
        assert client.delete("/crud/resource/1").status_code == 200
        assert client.patch("/crud/resource/1").status_code == 200
