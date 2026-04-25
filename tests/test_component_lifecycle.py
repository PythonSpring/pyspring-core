"""
Edge case tests for Component lifecycle, Config inheritance, and scope isolation.

Covers:
- post_construct / pre_destroy lifecycle hooks
- Config.scope inheritance across class hierarchy
- Config isolation between sibling classes
- Custom Config.name vs default name
- ComponentScope.Singleton vs Prototype behavior
- finish_initialization_cycle / finish_destruction_cycle
- Config not shared between unrelated components
- Deep inheritance chain scope propagation
"""

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import (
    Component,
    ComponentLifeCycle,
    ComponentScope,
)


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server)


class TestLifecycleHooks:

    def test_post_construct_called_during_init_cycle(self):
        call_log = []

        class TrackedComponent(Component):
            def post_construct(self):
                call_log.append("post_construct")

        comp = TrackedComponent()
        comp.finish_initialization_cycle()
        assert call_log == ["post_construct"]

    def test_pre_destroy_called_during_destruction_cycle(self):
        call_log = []

        class TrackedComponent(Component):
            def pre_destroy(self):
                call_log.append("pre_destroy")

        comp = TrackedComponent()
        comp.finish_destruction_cycle()
        assert call_log == ["pre_destroy"]

    def test_default_hooks_are_no_ops(self):
        comp = Component()
        comp.finish_initialization_cycle()
        comp.finish_destruction_cycle()

    def test_lifecycle_order_init_before_destroy(self, app_context: ApplicationContext):
        call_log = []

        class OrderedComponent(Component):
            def post_construct(self):
                call_log.append("init")

            def pre_destroy(self):
                call_log.append("destroy")

        app_context.register_component(OrderedComponent)
        app_context.init_ioc_container()

        components = app_context.get_singleton_component_instances()
        for comp in components:
            comp.finish_initialization_cycle()
        for comp in components:
            comp.finish_destruction_cycle()

        assert call_log == ["init", "destroy"]

    def test_post_construct_exception_propagates(self):
        class BadComponent(Component):
            def post_construct(self):
                raise RuntimeError("init failed")

        comp = BadComponent()
        with pytest.raises(RuntimeError, match="init failed"):
            comp.finish_initialization_cycle()

    def test_pre_destroy_exception_propagates(self):
        class BadComponent(Component):
            def pre_destroy(self):
                raise RuntimeError("cleanup failed")

        comp = BadComponent()
        with pytest.raises(RuntimeError, match="cleanup failed"):
            comp.finish_destruction_cycle()


class TestConfigScopeInheritance:

    def test_default_scope_is_singleton(self):
        class DefaultComp(Component): ...

        assert DefaultComp.get_scope() == ComponentScope.Singleton

    def test_explicit_singleton_scope(self):
        class SingletonComp(Component):
            class Config:
                scope = ComponentScope.Singleton

        assert SingletonComp.get_scope() == ComponentScope.Singleton

    def test_explicit_prototype_scope(self):
        class ProtoComp(Component):
            class Config:
                scope = ComponentScope.Prototype

        assert ProtoComp.get_scope() == ComponentScope.Prototype

    def test_child_inherits_parent_scope(self):
        class Parent(Component):
            class Config:
                scope = ComponentScope.Prototype

        class Child(Parent): ...

        assert Child.get_scope() == ComponentScope.Prototype

    def test_child_can_override_parent_scope(self):
        class Parent(Component):
            class Config:
                scope = ComponentScope.Prototype

        class Child(Parent):
            class Config:
                scope = ComponentScope.Singleton

        assert Child.get_scope() == ComponentScope.Singleton
        assert Parent.get_scope() == ComponentScope.Prototype

    def test_sibling_classes_have_isolated_configs(self):
        class SiblingA(Component):
            class Config:
                scope = ComponentScope.Prototype

        class SiblingB(Component):
            class Config:
                scope = ComponentScope.Singleton

        assert SiblingA.get_scope() == ComponentScope.Prototype
        assert SiblingB.get_scope() == ComponentScope.Singleton

    def test_set_scope_changes_scope(self):
        class DynamicComp(Component): ...

        assert DynamicComp.get_scope() == ComponentScope.Singleton
        DynamicComp.set_scope(ComponentScope.Prototype)
        assert DynamicComp.get_scope() == ComponentScope.Prototype
        DynamicComp.set_scope(ComponentScope.Singleton)

    def test_set_scope_on_child_doesnt_affect_parent(self):
        class Parent(Component): ...
        class Child(Parent): ...

        Child.set_scope(ComponentScope.Prototype)
        assert Parent.get_scope() == ComponentScope.Singleton
        assert Child.get_scope() == ComponentScope.Prototype
        Child.set_scope(ComponentScope.Singleton)


class TestConfigName:

    def test_default_name_is_class_name(self):
        class MyComponent(Component): ...

        assert MyComponent.get_name() == "MyComponent"

    def test_custom_name(self):
        class MyComponent(Component):
            class Config:
                name = "custom_name"

        assert MyComponent.get_name() == "custom_name"

    def test_empty_name_falls_back_to_class_name(self):
        class MyComponent(Component):
            class Config:
                name = ""

        assert MyComponent.get_name() == "MyComponent"

    def test_child_without_config_gets_own_default_name(self):
        class Parent(Component):
            class Config:
                name = "parent_name"

        class Child(Parent): ...

        assert Child.get_name() == "Child"
        assert Parent.get_name() == "parent_name"


class TestConfigIsolation:

    def test_modifying_one_class_config_does_not_affect_another(self):
        class CompA(Component):
            class Config:
                scope = ComponentScope.Singleton

        class CompB(Component):
            class Config:
                scope = ComponentScope.Singleton

        CompA.set_scope(ComponentScope.Prototype)
        assert CompA.get_scope() == ComponentScope.Prototype
        assert CompB.get_scope() == ComponentScope.Singleton
        CompA.set_scope(ComponentScope.Singleton)

    def test_deep_inheritance_chain(self):
        class L0(Component):
            class Config:
                scope = ComponentScope.Prototype

        class L1(L0): ...
        class L2(L1): ...
        class L3(L2): ...

        assert L3.get_scope() == ComponentScope.Prototype

    def test_config_with_explicit_scope_and_name(self):
        class Parent(Component):
            class Config:
                scope = ComponentScope.Prototype

        class Child(Parent):
            class Config:
                name = "child_custom"
                scope = ComponentScope.Prototype

        assert Child.get_scope() == ComponentScope.Prototype
        assert Child.get_name() == "child_custom"

    def test_child_config_without_scope_defaults_to_singleton(self):
        class Parent(Component):
            class Config:
                scope = ComponentScope.Prototype

        class Child(Parent):
            class Config:
                name = "child_custom"

        # When child defines its own Config class, scope defaults to Singleton
        # unless explicitly set (the parent's scope is not inherited through user-defined Config)
        assert Child.get_scope() == ComponentScope.Singleton
        assert Child.get_name() == "child_custom"


class TestComponentGetComponentBase:

    def test_get_component_base_returns_cls(self):
        class MyComp(Component): ...

        assert MyComp.get_component_base() is MyComp

    def test_get_component_base_on_subclass(self):
        class Parent(Component): ...
        class Child(Parent): ...

        assert Child.get_component_base() is Child


class TestSingletonVsPrototypeInContext:

    def test_singleton_components_share_state(self, app_context: ApplicationContext):
        class Counter(Component):
            count: int = 0

            def increment(self):
                self.count += 1

        app_context.register_component(Counter)
        app_context.init_ioc_container()

        c1 = app_context.get_component(Counter)
        c1.increment()

        c2 = app_context.get_component(Counter)
        assert c2.count == 1
        assert c1 is c2

    def test_prototype_components_have_independent_state(self, app_context: ApplicationContext):
        class Counter(Component):
            class Config:
                scope = ComponentScope.Prototype
            count: int = 0

        app_context.register_component(Counter)
        app_context.init_ioc_container()

        c1 = app_context.get_component(Counter)
        c1.count = 5

        c2 = app_context.get_component(Counter)
        assert c2.count == 0
        assert c1 is not c2

    def test_prototype_not_stored_in_instances(self, app_context: ApplicationContext):
        class Proto(Component):
            class Config:
                scope = ComponentScope.Prototype

        app_context.register_component(Proto)
        app_context.init_ioc_container()

        assert len(app_context.container_manager.component_instances) == 0
