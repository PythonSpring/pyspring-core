"""
Tests exposing real bugs and unhandled edge cases in the framework.

These tests document behaviors that would bite framework users in production.
Tests marked with xfail are KNOWN BUGS that should be fixed.
Tests that pass document surprising-but-intended behaviors that need documentation.
"""

from abc import ABC, abstractmethod
from typing import Optional

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component, ComponentScope
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.controllers.route_mapping import (
    GetMapping,
    RouteRegistration,
    HTTPMethod,
    _pending_routes,
    drain_pending_routes,
)
from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.entities.properties.properties_loader import (
    InvalidPropertiesKeyError,
    _PropertiesLoader,
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
    return ApplicationContext(config, server=server)


# ============================================================================
# BUG: BeanCollection.scan_beans() crashes with KeyError when create_ method
# has no return type annotation. User gets unhelpful "KeyError: 'return'"
# instead of a clear error message.
# ============================================================================

class TestBeanScanningMissingAnnotation:

    def test_create_method_without_return_annotation_gives_clear_error(self):
        """A create_ method without return type should give a descriptive TypeError."""

        class NoAnnotation(BeanCollection):
            @classmethod
            def create_service(cls):  # no return annotation
                return object()

        with pytest.raises(TypeError, match="must have a return type annotation"):
            NoAnnotation.scan_beans()


# ============================================================================
# BUG: Prototype-scoped components never get post_construct() called.
# Singleton components get it via _handle_singleton_components_life_cycle(),
# but prototype instances created by get_component() skip it entirely.
# ============================================================================

class TestPrototypeLifecycleBug:

    def test_prototype_post_construct_is_called(self, app_context: ApplicationContext):
        """Prototype components should have post_construct() called after DI."""
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


# ============================================================================
# BUG: DI crashes on non-primitive, non-component annotations with defaults.
# If a Component has `options: dict = {}`, the injector tries to inject it
# as a collection, fails, then tries entity injection, fails, then raises
# ValueError. Users expect default-valued attributes to be left alone.
# ============================================================================

class TestDIAnnotationWithDefaults:

    def test_non_injectable_annotation_with_default_is_left_alone(self, app_context: ApplicationContext):
        """Annotations with default values for non-injectable types should be skipped."""

        class ServiceWithDefaults(Component):
            config: dict = {}
            tags: list = []
            name: str = "default"  # primitive - skipped OK

        app_context.register_component(ServiceWithDefaults)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        comp = app_context.get_component(ServiceWithDefaults)
        assert comp is not None
        assert comp.config == {}
        assert comp.tags == []


# ============================================================================
# BUG: Component.set_scope() on the base Component class changes the default
# scope for ALL future subclasses. This is a global side effect.
# ============================================================================

class TestSetScopeGlobalSideEffect:

    def test_set_scope_on_base_component_affects_future_subclasses(self):
        """Demonstrates that set_scope on Component base class is a global mutation."""
        original_scope = Component.get_scope()

        try:
            Component.set_scope(ComponentScope.Prototype)
            # Now any new subclass created without explicit Config gets Prototype
            # This is a dangerous global side effect
            assert Component.get_scope() == ComponentScope.Prototype
        finally:
            Component.set_scope(original_scope)


# ============================================================================
# BUG: register_component silently overwrites when two different classes
# have the same Config.name. No warning, no error - one class disappears.
# ============================================================================

class TestSilentComponentOverwrite:

    def test_same_config_name_silently_overwrites(self, app_context: ApplicationContext):
        """Two different classes with same Config.name: second silently wins."""

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

        # ServiceV1 was silently overwritten by ServiceV2
        result = app_context.get_component(ServiceV1)
        # The user expected ServiceV1, but they get ServiceV2
        # This is silent data loss - no error, no warning
        assert result is not None
        # The returned instance is actually ServiceV2
        assert isinstance(result, ServiceV2)


# ============================================================================
# BUG: Properties loader rejects unknown keys in the config file.
# Users can't have extra keys for other tools/metadata in their YAML.
# ============================================================================

class TestPropertiesRejectsUnknownKeys:

    def test_extra_keys_in_config_crash_app(self, tmp_path):
        """Properties loader crashes if config file has keys not matching
        any registered Properties class."""
        import json

        class AppProps(Properties):
            __key__ = "app"
            name: str

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "app": {"name": "myapp"},
            "logging": {"level": "DEBUG"},  # extra key - not a registered Properties
        }))

        loader = _PropertiesLoader(str(config_file), [AppProps])
        # This raises InvalidPropertiesKeyError instead of ignoring unknown keys
        with pytest.raises(InvalidPropertiesKeyError, match="INVALID PROPERTIES KEY"):
            loader.load_properties()


# ============================================================================
# BUG: Route deduplication is silent. If two controllers define the same
# GET /path, only one survives in the set. No error, no warning.
# ============================================================================

class TestSilentRouteDedupliation:

    def test_duplicate_routes_across_controllers_silently_dropped(self):
        """When two routes have same method+path, one is silently lost in a set."""
        def handler_a(self): return "A"
        def handler_b(self): return "B"

        route_a = RouteRegistration(
            class_name="ControllerA", method=HTTPMethod.GET, path="/health", func=handler_a
        )
        route_b = RouteRegistration(
            class_name="ControllerB", method=HTTPMethod.GET, path="/health", func=handler_b
        )

        # When stored in a set, only one survives
        route_set = {route_a, route_b}
        assert len(route_set) == 1  # one route silently disappeared


# ============================================================================
# BUG: Controller instances are created fresh every call to
# get_controller_instances(). Not cached, not singleton.
# ============================================================================

class TestControllerInstancesNotCached:

    def test_get_controller_instances_returns_new_objects_each_call(self, app_context: ApplicationContext):
        """Every call to get_controller_instances() creates new un-injected instances."""

        class MyCtrl(RestController):
            class Config:
                prefix = "/api"

        app_context.register_controller(MyCtrl)

        instances_1 = app_context.get_controller_instances()
        instances_2 = app_context.get_controller_instances()

        # Different object identity each time
        assert instances_1[0] is not instances_2[0]
        # Second set of instances has NOT been dependency-injected
        # This is surprising behavior


# ============================================================================
# BUG: Abstract class dependency resolution only checks direct __subclasses__()
# A deeper hierarchy like ABC -> MiddleABC -> ConcreteImpl won't resolve.
# ============================================================================

class TestDeepAbstractHierarchyResolution:

    def test_indirect_subclass_of_abstract_is_found(self, app_context: ApplicationContext):
        """A concrete class that's a grandchild of an ABC should be resolvable."""

        class BaseHandler(Component, ABC):
            @abstractmethod
            def handle(self): ...

        class MiddleHandler(BaseHandler, ABC):
            """Still abstract, adds some shared logic."""
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
# BUG: BeanCollection.scan_beans uses dir(cls) which includes inherited
# create_ methods from parent classes, potentially creating duplicate beans.
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


class TestBeanInheritanceScanning:

    def test_child_collection_also_scans_parent_create_methods(self):
        """dir(cls) includes inherited methods, so child collection picks up
        parent's create_ methods too. This might be unintended."""
        views = _ChildCollection.scan_beans()
        bean_names = {v.bean_name for v in views}
        # Child collection picks up both its own and parent's beans
        assert "_ParentBean" in bean_names
        assert "_ChildBean" in bean_names
        # If both parent and child are registered separately, this causes
        # BeanConflictError for _ParentBean


# ============================================================================
# BUG: Properties.get_key() doesn't handle the case where __key__ is None
# (different from empty string). The check is `if _key is None or _key == ""`
# but ClassVar[str] = "" means it can never be None in normal usage.
# However, if someone sets __key__ = None, it falls through incorrectly.
# ============================================================================

class TestPropertiesKeyNoneEdgeCase:

    def test_properties_key_set_to_none_raises(self):
        """Setting __key__ to None should raise ValueError."""
        class BadProps(Properties):
            __key__ = None  # type: ignore

        with pytest.raises(ValueError, match="KEY NOT SET"):
            BadProps.get_key()


# ============================================================================
# EDGE CASE: What happens when is_within_context is called with a class
# that hasn't been registered? Should return False cleanly.
# ============================================================================

class TestIsWithinContext:

    def test_unregistered_class_returns_false(self, app_context: ApplicationContext):
        class Unknown(Component): ...
        assert app_context.is_within_context(Unknown) is False

    def test_registered_component_returns_true(self, app_context: ApplicationContext):
        class Known(Component): ...
        app_context.register_component(Known)
        assert app_context.is_within_context(Known) is True


# ============================================================================
# EDGE CASE: PySpringStarter with depends_on referencing unregistered class
# ============================================================================

class TestStarterDependencyValidation:

    def test_depends_on_unregistered_class_raises(self, app_context: ApplicationContext):
        from py_spring_core.core.application.context.application_context import (
            InvalidDependencyError,
        )
        from py_spring_core.core.starter.py_spring_starter import PySpringStarter

        class UnregisteredDep(Component): ...

        starter = PySpringStarter(depends_on=[UnregisteredDep])
        app_context.starters.append(starter)

        with pytest.raises(InvalidDependencyError, match="not found in the application context"):
            app_context.validate_starters()

    def test_depends_on_non_app_entity_raises(self, app_context: ApplicationContext):
        from py_spring_core.core.application.context.application_context import (
            InvalidDependencyError,
        )
        from py_spring_core.core.starter.py_spring_starter import PySpringStarter

        class NotAnEntity:
            pass

        starter = PySpringStarter(depends_on=[NotAnEntity])  # type: ignore
        app_context.starters.append(starter)

        with pytest.raises(InvalidDependencyError, match="INVALID DEPENDENCY"):
            app_context.validate_starters()


# ============================================================================
# EDGE CASE: Registering a RestController that is also a Component subclass
# ============================================================================

class TestControllerAsComponent:

    def test_controller_registered_only_as_controller(self, app_context: ApplicationContext):
        """RestController is NOT a Component subclass, so it should only be
        in controller_classes, not component_classes."""

        class MyCtrl(RestController):
            class Config:
                prefix = "/test"

        app_context.register_controller(MyCtrl)
        assert "MyCtrl" in app_context.container_manager.controller_classes
        assert "MyCtrl" not in app_context.container_manager.component_classes


# ============================================================================
# EDGE CASE: ApplicationRegistry.clear() resets all state
# ============================================================================

class TestApplicationRegistryClear:

    def test_clear_resets_all_state(self):
        from py_spring_core.core.application.application_registry import ApplicationRegistry

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
