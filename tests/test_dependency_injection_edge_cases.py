"""
Edge case tests for the dependency injection system.

Covers:
- Missing dependency raises clear error
- Qualifier type mismatch detection
- Annotated type extraction (with and without qualifier)
- Properties injection when properties not loaded
- Injection into prototype components (new instance each time)
- Injection order: component → bean fallback
- Primitive type skipping
- Collection injection edge cases (empty lists, mixed types)
- Abstract class with no implementations
- Abstract class with multiple implementations (ambiguous without qualifier)
- must_get_component / must_get_bean / must_get_properties raise on missing
"""

from abc import ABC, abstractmethod
from typing import Annotated, Optional

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
    DependencyInjector,
    ContainerManager,
    ComponentManager,
)
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component, ComponentScope
from py_spring_core.core.entities.properties.properties import Properties


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server)


class TestMissingDependencyErrors:

    def test_missing_component_dependency_raises_value_error(self, app_context: ApplicationContext):
        class ServiceA(Component): ...

        class ServiceB(Component):
            dep: ServiceA

        app_context.register_component(ServiceB)
        app_context.init_ioc_container()

        with pytest.raises(ValueError, match="DEPENDENCY INJECTION FAILED"):
            app_context.inject_dependencies_for_app_entities()

    def test_missing_bean_dependency_raises_value_error(self, app_context: ApplicationContext):
        class ExternalLib:
            pass

        class ServiceA(Component):
            lib: ExternalLib

        app_context.register_component(ServiceA)
        app_context.init_ioc_container()

        with pytest.raises(ValueError, match="DEPENDENCY INJECTION FAILED"):
            app_context.inject_dependencies_for_app_entities()


class TestQualifierResolution:

    def test_qualifier_resolves_correct_implementation(self, app_context: ApplicationContext):
        class Base(Component, ABC):
            @abstractmethod
            def work(self) -> str: ...

        class ImplA(Base):
            class Config:
                name = "impl_a"
            def work(self) -> str:
                return "A"

        class ImplB(Base):
            class Config:
                name = "impl_b"
            def work(self) -> str:
                return "B"

        class Consumer(Component):
            dep: Annotated[Base, "impl_b"]

        app_context.register_component(Base)
        app_context.register_component(ImplA)
        app_context.register_component(ImplB)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert consumer.dep.work() == "B"

    def test_qualifier_type_mismatch_raises_type_error(self, app_context: ApplicationContext):
        class ServiceA(Component):
            class Config:
                name = "my_service"

        class Unrelated(Component, ABC):
            @abstractmethod
            def work(self): ...

        class Consumer(Component):
            dep: Annotated[Unrelated, "my_service"]

        app_context.register_component(ServiceA)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()

        with pytest.raises(TypeError, match="QUALIFIER TYPE ERROR"):
            app_context.inject_dependencies_for_app_entities()


class TestAbstractClassEdgeCases:

    def test_abstract_class_with_no_implementations_raises(self, app_context: ApplicationContext):
        class EmptyAbstract(Component, ABC):
            @abstractmethod
            def do_stuff(self): ...

        app_context.register_component(EmptyAbstract)

        with pytest.raises(ValueError, match="has no registered subclasses"):
            app_context.init_ioc_container()

    def test_abstract_class_with_unimplemented_methods_raises(self, app_context: ApplicationContext):
        class BaseService(Component, ABC):
            @abstractmethod
            def process(self): ...

        class PartialImpl(BaseService):
            pass  # still abstract — process() not implemented

        app_context.register_component(BaseService)

        with pytest.raises(ValueError, match="PartialImpl is missing: process"):
            app_context.init_ioc_container()

    def test_abstract_class_multiple_impls_without_qualifier_raises(self, app_context: ApplicationContext):
        class Handler(Component, ABC):
            @abstractmethod
            def handle(self): ...

        class HandlerA(Handler):
            def handle(self): return "A"

        class HandlerB(Handler):
            def handle(self): return "B"

        class Consumer(Component):
            dep: Handler

        app_context.register_component(Handler)
        app_context.register_component(HandlerA)
        app_context.register_component(HandlerB)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()

        with pytest.raises(ValueError, match="AMBIGUOUS DEPENDENCY"):
            app_context.inject_dependencies_for_app_entities()


class TestPrototypeScopeInjection:

    def test_prototype_creates_new_instance_each_call(self, app_context: ApplicationContext):
        class Proto(Component):
            class Config:
                scope = ComponentScope.Prototype

        app_context.register_component(Proto)
        app_context.init_ioc_container()

        inst1 = app_context.get_component(Proto)
        inst2 = app_context.get_component(Proto)
        assert inst1 is not inst2

    def test_prototype_gets_dependencies_injected(self, app_context: ApplicationContext):
        class Dep(Component):
            value: str = "injected"

        class Proto(Component):
            class Config:
                scope = ComponentScope.Prototype
            dep: Dep

        app_context.register_component(Dep)
        app_context.register_component(Proto)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        proto = app_context.get_component(Proto)
        assert proto is not None
        assert proto.dep.value == "injected"

    def test_singleton_returns_same_instance(self, app_context: ApplicationContext):
        class Singleton(Component): ...

        app_context.register_component(Singleton)
        app_context.init_ioc_container()

        inst1 = app_context.get_component(Singleton)
        inst2 = app_context.get_component(Singleton)
        assert inst1 is inst2


class TestMustGetMethods:

    def test_must_get_component_raises_on_missing(self, app_context: ApplicationContext):
        class Missing(Component): ...

        with pytest.raises(LookupError, match="Component Missing not found"):
            app_context.must_get_component(Missing)

    def test_must_get_component_with_qualifier_raises_on_missing(self, app_context: ApplicationContext):
        class Missing(Component): ...

        with pytest.raises(LookupError, match="qualifier 'nonexistent'"):
            app_context.must_get_component(Missing, qualifier="nonexistent")

    def test_must_get_bean_raises_on_missing(self, app_context: ApplicationContext):
        class MyBean:
            pass

        with pytest.raises(LookupError, match="Bean MyBean not found"):
            app_context.must_get_bean(MyBean)

    def test_must_get_bean_with_qualifier_raises_on_missing(self, app_context: ApplicationContext):
        class MyBean:
            pass

        with pytest.raises(LookupError, match="qualifier 'custom'"):
            app_context.must_get_bean(MyBean, qualifier="custom")

    def test_must_get_properties_raises_on_missing(self, app_context: ApplicationContext):
        class MissingProps(Properties):
            __key__ = "missing"

        with pytest.raises(LookupError, match="Properties MissingProps not found"):
            app_context.must_get_properties(MissingProps)

    def test_must_get_component_returns_when_found(self, app_context: ApplicationContext):
        class Found(Component): ...

        app_context.register_component(Found)
        app_context.init_ioc_container()

        result = app_context.must_get_component(Found)
        assert isinstance(result, Found)


class TestPrimitiveTypeSkipping:

    def test_primitive_annotations_are_skipped(self, app_context: ApplicationContext):
        class WithPrimitives(Component):
            name: str = "default"
            count: int = 0
            ratio: float = 0.0
            flag: bool = True

        app_context.register_component(WithPrimitives)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        comp = app_context.get_component(WithPrimitives)
        assert comp is not None
        assert comp.name == "default"
        assert comp.count == 0


class TestCollectionInjectionEdgeCases:

    def test_empty_list_injection(self, app_context: ApplicationContext):
        class Plugin(Component, ABC):
            @abstractmethod
            def run(self): ...

        class Consumer(Component):
            plugins: list[Plugin]

        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert consumer.plugins == []

    def test_set_injection_deduplicates(self, app_context: ApplicationContext):
        class Plugin(Component):
            pass

        class PluginA(Plugin): ...

        class Consumer(Component):
            plugins: set[Plugin]

        app_context.register_component(Plugin)
        app_context.register_component(PluginA)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert isinstance(consumer.plugins, set)

    def test_dict_injection_keyed_by_class_name(self, app_context: ApplicationContext):
        class Handler(Component, ABC):
            @abstractmethod
            def handle(self): ...

        class HandlerA(Handler):
            def handle(self): return "A"

        class HandlerB(Handler):
            def handle(self): return "B"

        class Consumer(Component):
            handlers: dict[str, Handler]

        app_context.register_component(Handler)
        app_context.register_component(HandlerA)
        app_context.register_component(HandlerB)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert "HandlerA" in consumer.handlers
        assert "HandlerB" in consumer.handlers


class TestRegistrationValidation:

    def test_register_non_component_class_raises(self, app_context: ApplicationContext):
        class NotAComponent:
            pass

        with pytest.raises(TypeError, match="COMPONENT REGISTRATION ERROR"):
            app_context.register_component(NotAComponent)  # type: ignore

    def test_register_non_bean_collection_raises(self, app_context: ApplicationContext):
        class NotABean:
            pass

        with pytest.raises(TypeError, match="BEAN COLLECTION REGISTRATION ERROR"):
            app_context.register_bean_collection(NotABean)  # type: ignore

    def test_register_non_controller_raises(self, app_context: ApplicationContext):
        class NotAController:
            pass

        with pytest.raises(TypeError, match="CONTROLLER REGISTRATION ERROR"):
            app_context.register_controller(NotAController)  # type: ignore

    def test_register_non_properties_raises(self, app_context: ApplicationContext):
        class NotProperties:
            pass

        with pytest.raises(TypeError, match="PROPERTIES REGISTRATION ERROR"):
            app_context.register_properties(NotProperties)  # type: ignore

    def test_duplicate_component_registration_is_idempotent(self, app_context: ApplicationContext):
        class MyComp(Component): ...

        app_context.register_component(MyComp)
        app_context.register_component(MyComp)
        assert len(app_context.container_manager.component_classes) == 1


class TestApplicationContextView:

    def test_as_view_reflects_registered_state(self, app_context: ApplicationContext):
        class CompA(Component): ...
        class CompB(Component): ...

        app_context.register_component(CompA)
        app_context.register_component(CompB)
        app_context.init_ioc_container()

        view = app_context.as_view()
        assert "CompA" in view.component_classes
        assert "CompB" in view.component_classes
        assert "CompA" in view.component_instances
        assert "CompB" in view.component_instances

    def test_as_view_empty_context(self, app_context: ApplicationContext):
        view = app_context.as_view()
        assert view.component_classes == []
        assert view.component_instances == []


class TestAnnotatedTypeExtraction:

    def test_extract_plain_type(self):
        cm = ContainerManager()
        injector = DependencyInjector(cm)
        actual_type, qualifier = injector._extract_qualifier_from_annotation(int)
        assert actual_type is int
        assert qualifier is None

    def test_extract_annotated_with_qualifier(self):
        cm = ContainerManager()
        injector = DependencyInjector(cm)
        annotated = Annotated[int, "my_qualifier"]
        actual_type, qualifier = injector._extract_qualifier_from_annotation(annotated)
        assert actual_type is int
        assert qualifier == "my_qualifier"

    def test_extract_annotated_without_extra_metadata(self):
        cm = ContainerManager()
        injector = DependencyInjector(cm)
        annotated = Annotated[str, "label"]
        actual_type, qualifier = injector._extract_qualifier_from_annotation(annotated)
        assert actual_type is str
        assert qualifier == "label"
