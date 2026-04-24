"""
End-to-end tests for _drain_pending_registrations.

Verifies that decorator-registered routes, event handlers, and exception
handlers are properly drained into the ApplicationRegistry and become
functional after the full init sequence (scan → drain → register → init).

Entity classes are defined at module level so that __qualname__ is clean
(e.g. "ItemController.list_items" not "TestClass.test_method.<locals>...").
"""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from py_spring_core.core.application.application_registry import ApplicationRegistry
from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import Component, ComponentScope
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.controllers.route_mapping import (
    DeleteMapping,
    GetMapping,
    PostMapping,
    _pending_routes,
    drain_pending_routes,
)
from py_spring_core.event.application_event_handler_registry import (
    EventListener,
    _pending_event_handlers,
    drain_pending_event_handlers,
)
from py_spring_core.event.commons import ApplicationEvent
from py_spring_core.exception_handler.decorator import ExceptionHandler
from py_spring_core.exception_handler.exception_handler_registry import (
    _pending_exception_handlers,
    drain_pending_exception_handlers,
)


# ===========================================================================
# Module-level entity definitions (clean __qualname__ for decorators)
# ===========================================================================

# --- Routes ---

class ItemController(RestController):
    class Config:
        prefix = "/items"

    @GetMapping("/")
    def list_items(self):
        return [{"id": 1, "name": "apple"}]


class UserController(RestController):
    class Config:
        prefix = "/users"

    @GetMapping("/")
    def list_users(self):
        return []

    @PostMapping("/")
    def create_user(self):
        return {"created": True}

    @DeleteMapping("/{user_id}")
    def delete_user(self, user_id: int):
        return {"deleted": user_id}


class GhostController(RestController):
    @GetMapping("/ghost")
    def ghost(self):
        return "boo"


# --- Events ---

class OrderPlaced(ApplicationEvent):
    pass


class UserCreated(ApplicationEvent):
    pass


class PaymentReceived(ApplicationEvent):
    pass


class SkippedEvent(ApplicationEvent):
    pass


class OrderService(Component):
    class Config:
        scope = ComponentScope.Singleton

    def __init__(self):
        self.handled_events = []

    @EventListener(OrderPlaced)
    def on_order_placed(self, event: OrderPlaced):
        self.handled_events.append(event)


class NotificationService(Component):
    class Config:
        scope = ComponentScope.Singleton
        name = "NotificationService"

    def __init__(self):
        self.notified = False

    @EventListener(UserCreated)
    def on_user_created(self, event: UserCreated):
        self.notified = True


class BillingService(Component):
    class Config:
        name = "BillingService"

    @EventListener(PaymentReceived)
    def on_payment(self, event: PaymentReceived):
        pass


class AuditService(Component):
    class Config:
        name = "AuditService"

    @EventListener(PaymentReceived)
    def on_payment(self, event: PaymentReceived):
        pass


class SkippedComponent(Component):
    @EventListener(SkippedEvent)
    def handle(self, event: SkippedEvent):
        pass


# --- Exceptions ---

class AppError(Exception):
    pass


class ServiceError(Exception):
    pass


class OrphanError(Exception):
    pass


@ExceptionHandler(AppError)
def handle_app_error(exc: AppError):
    return {"error": str(exc)}


@ExceptionHandler(ServiceError)
def handle_service_error(exc: ServiceError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@ExceptionHandler(OrphanError)
def handle_orphan(exc: OrphanError):
    return "handled"


# --- Full-sequence entities ---

class TaskCompleted(ApplicationEvent):
    pass


class TaskError(Exception):
    pass


class TaskController(RestController):
    class Config:
        prefix = "/tasks"

    @GetMapping("/")
    def list_tasks(self):
        return [{"task": "write tests"}]

    @PostMapping("/")
    def create_task(self):
        return {"created": True}


class TaskWorker(Component):
    class Config:
        scope = ComponentScope.Singleton
        name = "TaskWorker"

    def __init__(self):
        self.completed = []

    @EventListener(TaskCompleted)
    def on_complete(self, event: TaskCompleted):
        self.completed.append(event)


@ExceptionHandler(TaskError)
def handle_task_error(exc: TaskError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"error": str(exc)})


# Snapshot all decorator registrations from module-level definitions, then clear.
_ROUTE_SNAPSHOT = list(_pending_routes)
_EVENT_HANDLER_SNAPSHOT = list(_pending_event_handlers)
_EXCEPTION_HANDLER_SNAPSHOT = list(_pending_exception_handlers)

_pending_routes.clear()
_pending_event_handlers.clear()
_pending_exception_handlers.clear()


# ===========================================================================
# Helpers
# ===========================================================================


def _restore_pending_routes_for(*controller_names: str):
    for r in _ROUTE_SNAPSHOT:
        if r.class_name in controller_names:
            _pending_routes.append(r)


def _restore_pending_event_handlers_for(*class_names: str):
    for h in _EVENT_HANDLER_SNAPSHOT:
        if h.class_name in class_names:
            _pending_event_handlers.append(h)


def _restore_pending_exception_handlers_for(*exc_names: str):
    for name, func in _EXCEPTION_HANDLER_SNAPSHOT:
        if name in exc_names:
            _pending_exception_handlers.append((name, func))


def _drain_into_registry(registry: ApplicationRegistry) -> None:
    """Replicate PySpringApplication._drain_pending_registrations."""
    for route in drain_pending_routes():
        registry.routes.setdefault(route.class_name, set()).add(route)

    for handler in drain_pending_event_handlers():
        event_name = handler.event_type.__name__
        registry.event_handlers.setdefault(event_name, [])
        if handler not in registry.event_handlers[event_name]:
            registry.event_handlers[event_name].append(handler)

    for exc_name, handler_func in drain_pending_exception_handlers():
        registry.exception_handlers[exc_name] = handler_func


def _wire_controllers(server, registry, app_context):
    """Init controllers the same way PySpringApplication._init_controllers does."""
    for ctrl in app_context.get_controller_instances():
        name = ctrl.__class__.__name__
        ctrl.app = server
        ctrl.router = APIRouter(prefix=ctrl.get_router_prefix())
        ctrl.post_construct()
        ctrl._register_decorated_routes(registry.routes.get(name, set()))
        server.include_router(ctrl.must_get_router())


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def _clear_all_pending():
    _pending_routes.clear()
    _pending_event_handlers.clear()
    _pending_exception_handlers.clear()
    yield
    _pending_routes.clear()
    _pending_event_handlers.clear()
    _pending_exception_handlers.clear()


@pytest.fixture
def registry() -> ApplicationRegistry:
    return ApplicationRegistry()


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server, registry):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server, registry=registry)


# ===========================================================================
# E2E: Routes are drained and served via FastAPI
# ===========================================================================


class TestRoutesDrainE2E:

    def test_get_route_is_callable_after_drain(self, server, registry, app_context):
        _restore_pending_routes_for("ItemController")
        _drain_into_registry(registry)

        app_context.register_controller(ItemController)
        _wire_controllers(server, registry, app_context)

        client = TestClient(server)
        resp = client.get("/items/")
        assert resp.status_code == 200
        assert resp.json() == [{"id": 1, "name": "apple"}]

    def test_multiple_routes_on_same_controller(self, server, registry, app_context):
        _restore_pending_routes_for("UserController")
        _drain_into_registry(registry)

        assert "UserController" in registry.routes
        assert len(registry.routes["UserController"]) == 3

        app_context.register_controller(UserController)
        _wire_controllers(server, registry, app_context)

        client = TestClient(server)
        assert client.get("/users/").status_code == 200
        assert client.post("/users/").status_code == 200
        assert client.delete("/users/42").status_code == 200
        assert client.delete("/users/42").json() == {"deleted": 42}

    def test_no_routes_without_drain(self, registry):
        """If drain is skipped, the registry stays empty."""
        _restore_pending_routes_for("GhostController")
        # Intentionally skip drain
        assert registry.routes.get("GhostController") is None


# ===========================================================================
# E2E: Event handlers are drained and bound to components
# ===========================================================================


class TestEventHandlersDrainE2E:

    def test_event_handler_registered_after_drain(self, registry):
        _restore_pending_event_handlers_for("OrderService")
        _drain_into_registry(registry)

        assert "OrderPlaced" in registry.event_handlers
        handlers = registry.event_handlers["OrderPlaced"]
        assert len(handlers) == 1
        assert handlers[0].class_name == "OrderService"
        assert handlers[0].func_name == "on_order_placed"

    def test_event_handler_callable_on_component_instance(self, registry, app_context):
        _restore_pending_event_handlers_for("NotificationService")
        _drain_into_registry(registry)

        app_context.register_component(NotificationService)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        instance = app_context.get_component(NotificationService)
        assert instance is not None

        handler = registry.event_handlers["UserCreated"][0]
        event = UserCreated()
        handler.func(instance, event)
        assert instance.notified is True

    def test_multiple_handlers_for_same_event(self, registry):
        _restore_pending_event_handlers_for("BillingService", "AuditService")
        _drain_into_registry(registry)

        assert len(registry.event_handlers["PaymentReceived"]) == 2
        class_names = {h.class_name for h in registry.event_handlers["PaymentReceived"]}
        assert class_names == {"BillingService", "AuditService"}

    def test_no_handlers_without_drain(self, registry):
        _restore_pending_event_handlers_for("SkippedComponent")
        # Intentionally skip drain
        assert registry.event_handlers.get("SkippedEvent") is None


# ===========================================================================
# E2E: Exception handlers are drained and callable
# ===========================================================================


class TestExceptionHandlersDrainE2E:

    def test_exception_handler_registered_after_drain(self, registry):
        _restore_pending_exception_handlers_for("AppError")
        _drain_into_registry(registry)

        assert "AppError" in registry.exception_handlers
        result = registry.exception_handlers["AppError"](AppError("boom"))
        assert result == {"error": "boom"}

    def test_exception_handler_wired_into_fastapi(self, server, registry):
        _restore_pending_exception_handlers_for("ServiceError")
        _drain_into_registry(registry)

        for exc_name, handler_func in registry.exception_handlers.items():
            server.add_exception_handler(ServiceError, lambda req, exc: handler_func(exc))

        @server.get("/fail")
        def fail_route():
            raise ServiceError("service down")

        client = TestClient(server, raise_server_exceptions=False)
        resp = client.get("/fail")
        assert resp.status_code == 503
        assert resp.json() == {"detail": "service down"}

    def test_no_handlers_without_drain(self, registry):
        _restore_pending_exception_handlers_for("OrphanError")
        # Skip drain
        assert registry.exception_handlers.get("OrphanError") is None


# ===========================================================================
# E2E: All three drain targets in a single init sequence
# ===========================================================================


class TestFullDrainSequence:

    def test_all_drain_targets_populated_in_single_pass(self, server, registry, app_context):
        """Simulate the real boot: decorators fire → drain → everything lands in registry."""
        _restore_pending_routes_for("TaskController")
        _restore_pending_event_handlers_for("TaskWorker")
        _restore_pending_exception_handlers_for("TaskError")

        _drain_into_registry(registry)

        # --- verify all three are populated ---
        assert "TaskController" in registry.routes
        assert len(registry.routes["TaskController"]) == 2

        assert "TaskCompleted" in registry.event_handlers
        assert len(registry.event_handlers["TaskCompleted"]) == 1

        assert "TaskError" in registry.exception_handlers

        # --- wire up controller and verify routes are live ---
        app_context.register_controller(TaskController)
        app_context.register_component(TaskWorker)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        _wire_controllers(server, registry, app_context)

        client = TestClient(server)
        assert client.get("/tasks/").status_code == 200
        assert client.get("/tasks/").json() == [{"task": "write tests"}]
        assert client.post("/tasks/").json() == {"created": True}

        # --- verify event handler is callable on the real component ---
        worker = app_context.get_component(TaskWorker)
        handler = registry.event_handlers["TaskCompleted"][0]
        event = TaskCompleted()
        handler.func(worker, event)
        assert len(worker.completed) == 1

        # --- verify exception handler is callable ---
        result = registry.exception_handlers["TaskError"](TaskError("fail"))
        assert result.status_code == 500
