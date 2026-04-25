"""
Tests for framework edge cases and behavioral contracts.

These tests validate specific framework behaviors including error handling,
dependency injection rules, component lifecycle, and configuration loading.
"""

from abc import ABC, abstractmethod

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
    InvalidDependencyError,
)
from py_spring_core.core.application.application_registry import ApplicationRegistry
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component, ComponentScope
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.controllers.route_mapping import (
    RouteRegistration,
    HTTPMethod,
    _pending_routes,
)
from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.entities.properties.properties_loader import (
    InvalidPropertiesKeyError,
    _PropertiesLoader,
)
from py_spring_core.core.starter.py_spring_starter import PySpringStarter


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
    return ApplicationContext(config, server=server)


# ============================================================================
# Bean Collection
# ============================================================================


class _ParentBean:
    pass


class _ChildBean:
    pass


class _ParentCollection(BeanCollection):
    @classmethod
    def create_parent_bean(cls) -> _ParentBean:
        return _ParentBean()


class _ChildCollection(_ParentCollection):
    @classmethod
    def create_child_bean(cls) -> _ChildBean:
        return _ChildBean()


class TestBeanCollectionScanning:

    def test_create_method_without_return_annotation_raises_type_error(self):
        """A create_ method must have a return type annotation."""

        class BadCollection(BeanCollection):
            @classmethod
            def create_service(cls):
                return object()

        with pytest.raises(TypeError, match="must have a return type annotation"):
            BadCollection.scan_beans()

    def test_child_collection_inherits_parent_create_methods(self):
        """A child BeanCollection includes create_ methods from its parent via dir()."""
        views = _ChildCollection.scan_beans()
        bean_names = {v.bean_name for v in views}
        assert "_ParentBean" in bean_names
        assert "_ChildBean" in bean_names


# ============================================================================
# Component Lifecycle
# ============================================================================


class TestComponentLifecycle:

    def test_prototype_component_calls_post_construct(self, app_context: ApplicationContext):
        """Prototype-scoped components must have post_construct() invoked after creation."""
        call_log = []

        class ProtoComp(Component):
            class Config:
                scope = ComponentScope.Prototype

            def post_construct(self):
                call_log.append("post_construct")

        app_context.register_component(ProtoComp)
        app_context.init_ioc_container()

        instance = app_context.get_component(ProtoComp)
        assert instance is not None
        assert "post_construct" in call_log

    def test_set_scope_on_base_class_mutates_global_default(self):
        """Calling set_scope on Component base class changes the default for all subclasses."""
        original_scope = Component.get_scope()
        try:
            Component.set_scope(ComponentScope.Prototype)
            assert Component.get_scope() == ComponentScope.Prototype
        finally:
            Component.set_scope(original_scope)


# ============================================================================
# Dependency Injection
# ============================================================================


class TestDependencyInjection:

    def test_non_injectable_annotation_with_default_value_is_skipped(self, app_context: ApplicationContext):
        """Annotations with default values for non-injectable types (dict, list) are left unchanged."""

        class ServiceWithDefaults(Component):
            config: dict = {}
            tags: list = []
            name: str = "default"

        app_context.register_component(ServiceWithDefaults)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        comp = app_context.get_component(ServiceWithDefaults)
        assert comp is not None
        assert comp.config == {}
        assert comp.tags == []

    def test_deep_abstract_hierarchy_resolves_to_concrete(self, app_context: ApplicationContext):
        """A concrete class that is a grandchild of an ABC is resolved for injection."""

        class BaseHandler(Component, ABC):
            @abstractmethod
            def handle(self): ...

        class MiddleHandler(BaseHandler, ABC):
            @abstractmethod
            def handle(self): ...

        class ConcreteHandler(MiddleHandler):
            def handle(self):
                return "handled"

        class Consumer(Component):
            handler: BaseHandler

        app_context.register_component(BaseHandler)
        app_context.register_component(ConcreteHandler)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert isinstance(consumer.handler, ConcreteHandler)


# ============================================================================
# Component Registration
# ============================================================================


class TestComponentRegistration:

    def test_duplicate_config_name_overwrites_silently(self, app_context: ApplicationContext):
        """When two components share the same Config.name, the later registration wins."""

        class ServiceV1(Component):
            class Config:
                name = "MyService"
            version: str = "v1"

        class ServiceV2(Component):
            class Config:
                name = "MyService"
            version: str = "v2"

        app_context.register_component(ServiceV1)
        app_context.register_component(ServiceV2)
        app_context.init_ioc_container()

        result = app_context.get_component(ServiceV1)
        assert result is not None
        assert isinstance(result, ServiceV2)

    def test_is_within_context_returns_false_for_unregistered(self, app_context: ApplicationContext):
        class Unknown(Component): ...
        assert app_context.is_within_context(Unknown) is False

    def test_is_within_context_returns_true_for_registered(self, app_context: ApplicationContext):
        class Known(Component): ...
        app_context.register_component(Known)
        assert app_context.is_within_context(Known) is True


# ============================================================================
# Properties
# ============================================================================


class TestProperties:

    def test_unknown_keys_in_config_raises_invalid_properties_key_error(self, tmp_path):
        """Properties loader rejects config keys that do not match any registered Properties class."""
        import json

        class AppProps(Properties):
            __key__ = "app"
            name: str

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "app": {"name": "myapp"},
            "logging": {"level": "DEBUG"},
        }))

        loader = _PropertiesLoader(str(config_file), [AppProps])
        with pytest.raises(InvalidPropertiesKeyError, match="INVALID PROPERTIES KEY"):
            loader.load_properties()

    def test_key_set_to_none_raises_value_error(self):
        """Setting __key__ to None must raise ValueError."""

        class BadProps(Properties):
            __key__ = None  # type: ignore

        with pytest.raises(ValueError, match="KEY NOT SET"):
            BadProps.get_key()


# ============================================================================
# REST Controller
# ============================================================================


class TestRestController:

    def test_duplicate_routes_are_deduplicated_in_set(self):
        """RouteRegistrations with same method+path collapse to one entry in a set."""

        def handler_a(self):
            return "A"

        def handler_b(self):
            return "B"

        route_a = RouteRegistration(
            class_name="ControllerA", method=HTTPMethod.GET, path="/health", func=handler_a
        )
        route_b = RouteRegistration(
            class_name="ControllerB", method=HTTPMethod.GET, path="/health", func=handler_b
        )

        route_set = {route_a, route_b}
        assert len(route_set) == 1

    def test_get_controller_instances_creates_new_objects_each_call(self, app_context: ApplicationContext):
        """Each call to get_controller_instances() returns fresh instances."""

        class MyCtrl(RestController):
            class Config:
                prefix = "/api"

        app_context.register_controller(MyCtrl)

        instances_1 = app_context.get_controller_instances()
        instances_2 = app_context.get_controller_instances()

        assert instances_1[0] is not instances_2[0]

    def test_controller_registered_only_as_controller(self, app_context: ApplicationContext):
        """RestController is stored in controller_classes, not in component_classes."""

        class MyCtrl(RestController):
            class Config:
                prefix = "/test"

        app_context.register_controller(MyCtrl)
        assert "MyCtrl" in app_context.container_manager.controller_classes
        assert "MyCtrl" not in app_context.container_manager.component_classes


# ============================================================================
# Starter Validation
# ============================================================================


class TestStarterValidation:

    def test_depends_on_unregistered_class_raises_invalid_dependency(self, app_context: ApplicationContext):
        """Starter depending on an unregistered class must raise InvalidDependencyError."""

        class UnregisteredDep(Component): ...

        starter = PySpringStarter(depends_on=[UnregisteredDep])
        app_context.starters.append(starter)

        with pytest.raises(InvalidDependencyError, match="not found in the application context"):
            app_context.validate_starters()

    def test_depends_on_non_entity_class_raises_invalid_dependency(self, app_context: ApplicationContext):
        """Starter depending on a non-AppEntities type must raise InvalidDependencyError."""

        class NotAnEntity:
            pass

        starter = PySpringStarter(depends_on=[NotAnEntity])  # type: ignore
        app_context.starters.append(starter)

        with pytest.raises(InvalidDependencyError, match="INVALID DEPENDENCY"):
            app_context.validate_starters()


# ============================================================================
# Application Registry
# ============================================================================


class TestApplicationRegistry:

    def test_clear_resets_all_state(self):
        """ApplicationRegistry.clear() must reset all internal collections."""
        registry = ApplicationRegistry()
        registry.routes["TestCtrl"] = set()
        registry.event_handlers["TestEvent"] = []
        registry.exception_handlers["TestError"] = lambda e: None
        registry.loaded_properties["key"] = "value"

        registry.clear()

        assert len(registry.routes) == 0
        assert len(registry.event_handlers) == 0
        assert len(registry.exception_handlers) == 0
        assert len(registry.loaded_properties) == 0
        assert registry.event_queue.empty()
