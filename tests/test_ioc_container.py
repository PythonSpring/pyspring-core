"""
Tests for Component Config, Qualifier resolution, Abstract class handling,
and IoC container lifecycle behavior.
"""

from abc import ABC, abstractmethod
from typing import Annotated

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import Component, ComponentScope


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server)


class TestComponentConfig:

    def test_config_without_scope_defaults_to_singleton(
        self, app_context: ApplicationContext
    ):
        class AbstractService(Component, ABC):
            @abstractmethod
            def process(self) -> str: ...

        class ServiceA(AbstractService):
            class Config:
                name = "ServiceA"

            def process(self) -> str:
                return "A"

        assert ServiceA.get_scope() == ComponentScope.Singleton

        app_context.register_component(AbstractService)
        app_context.register_component(ServiceA)
        app_context.init_ioc_container()

        result = app_context.get_component(AbstractService, qualifier="ServiceA")
        assert result is not None
        assert result.process() == "A"

    def test_config_scope_isolated_across_subclasses(
        self, app_context: ApplicationContext
    ):
        class BaseService(Component):
            class Config:
                scope = ComponentScope.Singleton

        class ChildA(BaseService):
            pass

        class ChildB(BaseService):
            pass

        ChildA.set_scope(ComponentScope.Prototype)

        assert ChildA.get_scope() == ComponentScope.Prototype
        assert ChildB.get_scope() == ComponentScope.Singleton
        assert BaseService.get_scope() == ComponentScope.Singleton


class TestAbstractClassResolution:

    def test_multiple_implementations_without_qualifier_raises_ambiguity(
        self, app_context: ApplicationContext
    ):
        class AbstractService(Component, ABC):
            @abstractmethod
            def process(self) -> str: ...

        class ServiceA(AbstractService):
            class Config:
                name = "ServiceA"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "A"

        class ServiceB(AbstractService):
            class Config:
                name = "ServiceB"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "B"

        app_context.register_component(AbstractService)
        app_context.register_component(ServiceA)
        app_context.register_component(ServiceB)
        app_context.init_ioc_container()

        class Consumer(Component):
            class Config:
                scope = ComponentScope.Singleton

            service: AbstractService

        app_context.register_component(Consumer)
        app_context.init_ioc_container()

        with pytest.raises(ValueError, match="AMBIGUOUS DEPENDENCY"):
            app_context.inject_dependencies_for_app_entities()

    def test_abstract_without_abc_treated_as_concrete(
        self, app_context: ApplicationContext
    ):
        class AbstractService(Component):
            class Config:
                scope = ComponentScope.Singleton

            def process(self) -> str:
                raise NotImplementedError()

        app_context.register_component(AbstractService)
        app_context.init_ioc_container()

        instance = app_context.get_component(AbstractService)
        assert instance is not None

        with pytest.raises(NotImplementedError):
            instance.process()

    def test_abstract_without_subclasses_fails_at_init(
        self, app_context: ApplicationContext
    ):
        class LonelyAbstractService(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def process(self) -> str: ...

        app_context.register_component(LonelyAbstractService)

        with pytest.raises(ValueError, match="has no registered subclasses"):
            app_context.init_ioc_container()

    def test_scope_resolved_from_target_class(self, app_context: ApplicationContext):
        class AbstractService(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def process(self) -> str: ...

        class PrototypeService(AbstractService):
            class Config:
                name = "PrototypeService"
                scope = ComponentScope.Prototype

            def process(self) -> str:
                return "prototype"

        app_context.register_component(AbstractService)
        app_context.register_component(PrototypeService)
        app_context.init_ioc_container()

        result1 = app_context.get_component(
            AbstractService, qualifier="PrototypeService"
        )
        result2 = app_context.get_component(
            AbstractService, qualifier="PrototypeService"
        )

        assert result1 is not None
        assert result2 is not None
        assert isinstance(result1, PrototypeService)
        assert isinstance(result2, PrototypeService)
        assert result1 is not result2


class TestQualifierResolution:

    def test_qualifier_rejects_unrelated_component(
        self, app_context: ApplicationContext
    ):
        class ServiceA(Component):
            class Config:
                name = "ServiceA"
                scope = ComponentScope.Singleton

            def do_a(self) -> str:
                return "A"

        class TotallyUnrelated(Component):
            class Config:
                name = "TotallyUnrelated"
                scope = ComponentScope.Singleton

            def do_something_else(self) -> str:
                return "unrelated"

        app_context.register_component(ServiceA)
        app_context.register_component(TotallyUnrelated)
        app_context.init_ioc_container()

        with pytest.raises(TypeError, match="QUALIFIER TYPE ERROR"):
            app_context.get_component(ServiceA, qualifier="TotallyUnrelated")

    def test_qualifier_resolves_concrete_impl_via_abstract_type_hint(
        self, app_context: ApplicationContext
    ):
        class PaymentProcessor(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def pay(self, amount: float) -> str: ...

        class StripeProcessor(PaymentProcessor):
            class Config:
                name = "StripeProcessor"
                scope = ComponentScope.Singleton

            def pay(self, amount: float) -> str:
                return f"stripe:{amount}"

        class PayPalProcessor(PaymentProcessor):
            class Config:
                name = "PayPalProcessor"
                scope = ComponentScope.Singleton

            def pay(self, amount: float) -> str:
                return f"paypal:{amount}"

        app_context.register_component(StripeProcessor)
        app_context.register_component(PayPalProcessor)
        app_context.init_ioc_container()

        class CheckoutService(Component):
            class Config:
                scope = ComponentScope.Singleton

            processor: Annotated[PaymentProcessor, "StripeProcessor"]

        app_context.register_component(CheckoutService)
        app_context.init_ioc_container()

        app_context.inject_dependencies_for_app_entities()

        checkout = app_context.get_component(CheckoutService)
        assert checkout is not None
        assert isinstance(checkout.processor, StripeProcessor)
        assert checkout.processor.pay(100) == "stripe:100"

    def test_bean_qualifier_filters_lookup(self, app_context: ApplicationContext):
        from py_spring_core.core.entities.bean_collection.bean_collection import (
            BeanCollection,
        )

        class CacheClient:
            pass

        class MyBeanCollection(BeanCollection):
            @staticmethod
            def create_cache_client() -> CacheClient:
                return CacheClient()

        app_context.register_bean_collection(MyBeanCollection)
        app_context.init_ioc_container()

        result_with_bogus_qualifier = app_context.get_bean(
            CacheClient, qualifier="CompletelyFakeQualifier"
        )
        result_without_qualifier = app_context.get_bean(CacheClient)

        assert result_with_bogus_qualifier is None
        assert result_without_qualifier is not None


class TestIoCContainerLifecycle:

    def test_init_ioc_container_is_idempotent(self, app_context: ApplicationContext):
        class CounterService(Component):
            instance_count = 0

            class Config:
                name = "CounterService"
                scope = ComponentScope.Singleton

            def __init__(self):
                CounterService.instance_count += 1

        app_context.register_component(CounterService)
        app_context.init_ioc_container()

        first_instance = app_context.get_component(CounterService)
        assert CounterService.instance_count == 1

        app_context.init_ioc_container()

        second_instance = app_context.get_component(CounterService)
        assert CounterService.instance_count == 1
        assert first_instance is second_instance
