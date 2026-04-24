"""
Tests for instance-owned application state (ApplicationRegistry, drain functions, instance-level DI).

Covers:
- Drain functions (routes, event handlers, exception handlers)
- ApplicationRegistry isolation and clear()
- Instance-level DI (not class-level)
- Prototype DI per-instantiation
- Controller instance-level app/router
"""

from abc import ABC, abstractmethod
from typing import Annotated

import pytest
from fastapi import APIRouter, FastAPI

from py_spring_core.core.application.application_registry import ApplicationRegistry
from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import Component, ComponentScope
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.controllers.route_mapping import (
    GetMapping,
    PostMapping,
    RouteRegistration,
    _pending_routes,
    drain_pending_routes,
)
from py_spring_core.event.application_event_handler_registry import (
    EventHandler,
    EventListener,
    _pending_event_handlers,
    drain_pending_event_handlers,
)
from py_spring_core.event.commons import ApplicationEvent
from py_spring_core.exception_handler.exception_handler_registry import (
    ExceptionHandlerRegistry,
    _pending_exception_handlers,
    drain_pending_exception_handlers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def registry() -> ApplicationRegistry:
    return ApplicationRegistry()


@pytest.fixture
def app_context(server: FastAPI, registry: ApplicationRegistry):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server, registry=registry)


# ---------------------------------------------------------------------------
# Drain functions
# ---------------------------------------------------------------------------


class TestDrainPendingRoutes:

    @pytest.fixture(autouse=True)
    def _clear_pending(self):
        _pending_routes.clear()
        yield
        _pending_routes.clear()

    def test_drain_returns_registered_routes(self):
        class FakeController(RestController):
            @GetMapping("/items")
            def get_items(self):
                pass

        routes = drain_pending_routes()
        assert len(routes) == 1
        assert routes[0].path == "/items"
        assert routes[0].method.value == "GET"

    def test_drain_clears_pending_list(self):
        class FakeController(RestController):
            @GetMapping("/a")
            def get_a(self):
                pass

            @PostMapping("/b")
            def post_b(self):
                pass

        first = drain_pending_routes()
        assert len(first) == 2

        second = drain_pending_routes()
        assert len(second) == 0

    def test_drain_returns_routes_in_registration_order(self):
        class FakeController(RestController):
            @GetMapping("/first")
            def first(self):
                pass

            @GetMapping("/second")
            def second(self):
                pass

            @PostMapping("/third")
            def third(self):
                pass

        routes = drain_pending_routes()
        paths = [r.path for r in routes]
        assert paths == ["/first", "/second", "/third"]


class TestDrainPendingEventHandlers:

    @pytest.fixture(autouse=True)
    def _clear_pending(self):
        _pending_event_handlers.clear()
        yield
        _pending_event_handlers.clear()

    def test_drain_returns_registered_handlers(self):
        from py_spring_core.event.application_event_handler_registry import (
            _register_event_handler,
        )

        class MyEvent(ApplicationEvent):
            pass

        def handler(self, event):
            pass

        handler.__qualname__ = "MyComponent.on_event"
        _register_event_handler(MyEvent, handler)

        handlers = drain_pending_event_handlers()
        assert len(handlers) == 1
        assert handlers[0].event_type is MyEvent
        assert handlers[0].class_name == "MyComponent"

    def test_drain_clears_pending_list(self):
        from py_spring_core.event.application_event_handler_registry import (
            _register_event_handler,
        )

        class EventA(ApplicationEvent):
            pass

        def handler(self, event):
            pass

        handler.__qualname__ = "Comp.handle_a"
        _register_event_handler(EventA, handler)

        first = drain_pending_event_handlers()
        assert len(first) == 1

        second = drain_pending_event_handlers()
        assert len(second) == 0

    def test_duplicate_handler_not_added_twice(self):
        """The same handler function should not be registered twice."""
        from py_spring_core.event.application_event_handler_registry import (
            _register_event_handler,
        )

        class EventB(ApplicationEvent):
            pass

        def handler_func(self, event):
            pass

        handler_func.__qualname__ = "SomeClass.handler_func"

        _register_event_handler(EventB, handler_func)
        _register_event_handler(EventB, handler_func)

        handlers = drain_pending_event_handlers()
        assert len(handlers) == 1


class TestDrainPendingExceptionHandlers:

    @pytest.fixture(autouse=True)
    def _clear_pending(self):
        _pending_exception_handlers.clear()
        yield
        _pending_exception_handlers.clear()

    def test_drain_returns_registered_handlers(self):
        class CustomError(Exception):
            pass

        def handler(exc: CustomError):
            return "handled"

        ExceptionHandlerRegistry.register(CustomError, handler)

        drained = drain_pending_exception_handlers()
        assert len(drained) == 1
        assert drained[0][0] == "CustomError"

    def test_drain_clears_pending_list(self):
        class ErrorA(Exception):
            pass

        ExceptionHandlerRegistry.register(ErrorA, lambda e: None)

        first = drain_pending_exception_handlers()
        assert len(first) == 1

        second = drain_pending_exception_handlers()
        assert len(second) == 0

    def test_duplicate_exception_handler_raises(self):
        class ErrorB(Exception):
            pass

        ExceptionHandlerRegistry.register(ErrorB, lambda e: None)

        with pytest.raises(RuntimeError, match="already registered"):
            ExceptionHandlerRegistry.register(ErrorB, lambda e: None)


# ---------------------------------------------------------------------------
# ApplicationRegistry
# ---------------------------------------------------------------------------


class TestApplicationRegistry:

    def test_clear_resets_all_state(self):
        reg = ApplicationRegistry()
        reg.routes["TestCtrl"] = {
            RouteRegistration(
                class_name="TestCtrl",
                method="GET",
                path="/test",
                func=lambda: None,
            )
        }
        reg.event_handlers["MyEvent"] = [{"some": "handler"}]
        reg.exception_handlers["ValueError"] = lambda e: None
        reg.loaded_properties["db"] = {"host": "localhost"}
        reg.event_queue.put("msg")

        reg.clear()

        assert reg.routes == {}
        assert reg.event_handlers == {}
        assert reg.exception_handlers == {}
        assert reg.loaded_properties == {}
        assert reg.event_queue.empty()

    def test_two_registries_are_independent(self):
        reg_a = ApplicationRegistry()
        reg_b = ApplicationRegistry()

        reg_a.routes["CtrlA"] = set()
        reg_a.event_handlers["EvtA"] = []

        assert "CtrlA" not in reg_b.routes
        assert "EvtA" not in reg_b.event_handlers

    def test_default_factory_creates_independent_instances(self):
        """Each registry should have its own dict/queue, not shared references."""
        reg_a = ApplicationRegistry()
        reg_b = ApplicationRegistry()

        assert reg_a.routes is not reg_b.routes
        assert reg_a.event_handlers is not reg_b.event_handlers
        assert reg_a.event_queue is not reg_b.event_queue


# ---------------------------------------------------------------------------
# Instance-level DI
# ---------------------------------------------------------------------------


class TestInstanceLevelDI:

    def test_di_sets_on_instance_not_class(self, app_context: ApplicationContext):
        """After injection, the dependency should be on the instance, not the class."""

        class DepService(Component):
            class Config:
                scope = ComponentScope.Singleton

        class Consumer(Component):
            class Config:
                scope = ComponentScope.Singleton

            dep: DepService

        app_context.register_component(DepService)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        instance = app_context.get_component(Consumer)
        assert instance is not None
        assert hasattr(instance, "dep")
        assert isinstance(instance.dep, DepService)

        # The class itself should NOT have the attribute set
        assert "dep" not in Consumer.__dict__

    def test_prototype_gets_fresh_di_per_instantiation(
        self, app_context: ApplicationContext
    ):
        """Each prototype instance should get its own injected dependencies."""

        class SharedSingleton(Component):
            class Config:
                scope = ComponentScope.Singleton

        class PrototypeConsumer(Component):
            class Config:
                scope = ComponentScope.Prototype

            shared: SharedSingleton

        app_context.register_component(SharedSingleton)
        app_context.register_component(PrototypeConsumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        proto_a = app_context.get_component(PrototypeConsumer)
        proto_b = app_context.get_component(PrototypeConsumer)

        # Different instances
        assert proto_a is not proto_b
        # Both have the dependency injected
        assert hasattr(proto_a, "shared")
        assert hasattr(proto_b, "shared")
        # Both point to the same singleton
        assert proto_a.shared is proto_b.shared
        assert isinstance(proto_a.shared, SharedSingleton)

    def test_two_singletons_get_independent_instance_di(
        self, app_context: ApplicationContext
    ):
        """Two different singletons that depend on the same type get the same
        singleton instance (identity), but each via their own instance attribute."""

        class SharedDep(Component):
            class Config:
                scope = ComponentScope.Singleton

        class ConsumerA(Component):
            class Config:
                name = "ConsumerA"
                scope = ComponentScope.Singleton

            dep: SharedDep

        class ConsumerB(Component):
            class Config:
                name = "ConsumerB"
                scope = ComponentScope.Singleton

            dep: SharedDep

        app_context.register_component(SharedDep)
        app_context.register_component(ConsumerA)
        app_context.register_component(ConsumerB)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        a = app_context.get_component(ConsumerA)
        b = app_context.get_component(ConsumerB)

        assert a is not b
        assert a.dep is b.dep  # same singleton
        # Both are instance-level, not class-level
        assert "dep" not in ConsumerA.__dict__
        assert "dep" not in ConsumerB.__dict__


# ---------------------------------------------------------------------------
# Controller instance-level app/router
# ---------------------------------------------------------------------------


class TestControllerInstanceState:

    def test_controller_init_has_none_app_router(self):
        """A freshly constructed controller should have None app and router."""

        class MyController(RestController):
            pass

        ctrl = MyController()
        assert ctrl.app is None
        assert ctrl.router is None

    def test_controller_instances_have_independent_state(self):
        """Two controller instances should have independent app/router."""

        class CtrlA(RestController):
            pass

        class CtrlB(RestController):
            pass

        a = CtrlA()
        b = CtrlB()

        app_a = FastAPI()
        app_b = FastAPI()

        a.app = app_a
        a.router = APIRouter(prefix="/a")
        b.app = app_b
        b.router = APIRouter(prefix="/b")

        assert a.app is app_a
        assert b.app is app_b
        assert a.app is not b.app
        assert a.router is not b.router


# ---------------------------------------------------------------------------
# Event queue through registry
# ---------------------------------------------------------------------------


class TestEventQueueThroughRegistry:

    def test_event_queue_is_per_registry(self):
        reg_a = ApplicationRegistry()
        reg_b = ApplicationRegistry()

        reg_a.event_queue.put("event_for_a")

        assert not reg_b.event_queue.qsize()
        assert reg_a.event_queue.qsize() == 1
