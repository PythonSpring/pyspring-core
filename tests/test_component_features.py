from abc import ABC, abstractmethod
from typing import Annotated

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import Component, ComponentScope


class TestComponentFeatures:
    """Test suite for component features including primary components, qualifiers, and registration validation."""

    @pytest.fixture
    def server(self) -> FastAPI:
        return FastAPI()

    @pytest.fixture
    def app_context(self, server: FastAPI):
        """Fixture that provides a fresh ApplicationContext instance for each test."""
        config = ApplicationContextConfig(properties_path="")
        return ApplicationContext(config, server=server)

    def test_qualifier_based_injection(self, app_context: ApplicationContext):
        """
        Test the qualifier-based dependency injection mechanism.

        This test verifies that:
        1. Multiple implementations of an abstract component can coexist
        2. Specific implementations can be injected using qualifiers
        3. Both primary and non-primary components can be injected using qualifiers
        4. The correct implementation is injected for each qualifier

        The test creates an abstract service with two implementations and verifies
        that each can be injected into a consumer using appropriate qualifiers.
        """

        # Define abstract base class
        class AbstractService(Component):
            class Config:
                is_primary = True
                scope = ComponentScope.Singleton

            def process(self) -> str:
                raise NotImplementedError()

        # Define implementations
        class ServiceA(AbstractService):
            class Config:
                is_primary = True
                name = "ServiceA"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "Service A processing"

        class ServiceB(AbstractService):
            class Config:
                is_primary = False
                name = "ServiceB"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "Service B processing"

        # Register implementations
        app_context.register_component(ServiceA)
        app_context.register_component(ServiceB)
        app_context.init_ioc_container()

        # Test qualifier-based injection
        class ServiceConsumer(Component):
            service_a: Annotated[AbstractService, "ServiceA"]
            service_b: Annotated[AbstractService, "ServiceB"]

            def post_construct(self) -> None:
                assert isinstance(self.service_a, ServiceA)
                assert isinstance(self.service_b, ServiceB)
                assert self.service_a.process() == "Service A processing"
                assert self.service_b.process() == "Service B processing"

        app_context.register_component(ServiceConsumer)
        app_context.init_ioc_container()  # Initialize the consumer component
        app_context.inject_dependencies_for_app_entities()

    def test_duplicate_component_registration(self, app_context: ApplicationContext):
        """
        Test the prevention of duplicate component registration.

        This test verifies that:
        1. A component can only be registered once
        2. Attempting to register the same component again doesn't raise an error (silent skip)
        3. The component is only registered once in the container

        The test attempts to register the same component twice and verifies
        that it's handled gracefully without errors.
        """

        # Define a component
        class TestService(Component):
            class Config:
                name = "TestService"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "Test service processing"

        # Register the same component multiple times
        app_context.register_component(TestService)
        initial_count = len(app_context.container_manager.component_classes)
        app_context.register_component(TestService)
        app_context.register_component(TestService)
        final_count = len(app_context.container_manager.component_classes)

        # Verify the component is registered only once
        assert initial_count == final_count == 1
        assert "TestService" in app_context.container_manager.component_classes

    def test_component_name_override(self, app_context: ApplicationContext):
        """
        Test the ability to override component names during registration.

        This test verifies that:
        1. Components can be registered with custom names
        2. The custom name is correctly stored in the component container
        3. The component can be retrieved using the custom name

        The test registers a component with a custom name and verifies
        that it is correctly stored in the container.
        """

        # Define component with custom name
        class TestService(Component):
            class Config:
                name = "CustomServiceName"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "Test service processing"

        # Register component
        app_context.register_component(TestService)
        app_context.init_ioc_container()

        # Check if component is registered with custom name
        assert (
            "CustomServiceName" in app_context.container_manager.component_classes
        )
        component_instance = (
            app_context.container_manager.component_classes["CustomServiceName"]
        )

    def test_qualifier_with_invalid_component(self, app_context: ApplicationContext):
        """
        Test error handling for invalid qualifier usage.

        This test verifies that:
        1. Attempting to inject a component with an invalid qualifier raises an error
        2. The error message clearly indicates the invalid qualifier
        3. The error occurs during dependency injection

        The test attempts to inject a component using a non-existent qualifier
        and verifies that an appropriate error is raised.
        """

        # Define abstract base class
        class AbstractService(Component):
            class Config:
                is_primary = True
                scope = ComponentScope.Singleton

            def process(self) -> str:
                raise NotImplementedError()

        # Define implementation
        class TestService(AbstractService):
            class Config:
                is_primary = True
                name = "TestService"
                scope = ComponentScope.Singleton

            def process(self) -> str:
                return "Test service processing"

        # Register implementation
        app_context.register_component(TestService)
        app_context.init_ioc_container()

        # Test injection with invalid qualifier
        class ServiceConsumer(Component):
            service: Annotated[AbstractService, "NonExistentService"]

            def post_construct(self) -> None:
                pass

        app_context.register_component(ServiceConsumer)
        app_context.init_ioc_container()  # Initialize the consumer component

        # Attempting to inject with invalid qualifier should raise error
        with pytest.raises(
            ValueError,
            match="\\[DEPENDENCY INJECTION FAILED\\] Fail to inject dependency for attribute: service with dependency: AbstractService with qualifier: NonExistentService",
        ):
            app_context.inject_dependencies_for_app_entities()

    def test_single_implementation_auto_resolves_without_qualifier(
        self, app_context: ApplicationContext
    ):
        """When an abstract class has exactly one registered subclass,
        it should auto-resolve without needing a qualifier."""

        class AbstractHandler(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def handle(self) -> str: ...

        class OnlyHandler(AbstractHandler):
            class Config:
                name = "OnlyHandler"
                scope = ComponentScope.Singleton

            def handle(self) -> str:
                return "handled"

        app_context.register_component(AbstractHandler)
        app_context.register_component(OnlyHandler)
        app_context.init_ioc_container()

        class HandlerConsumer(Component):
            handler: AbstractHandler

        app_context.register_component(HandlerConsumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(HandlerConsumer)
        assert consumer is not None
        assert isinstance(consumer.handler, OnlyHandler)
        assert consumer.handler.handle() == "handled"

    def test_qualifier_matches_class_name_without_config_name(
        self, app_context: ApplicationContext
    ):
        """When a component has no Config.name, the qualifier should match
        the class's __name__."""

        class AbstractRepo(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def find(self) -> str: ...

        class InMemoryRepo(AbstractRepo):
            class Config:
                scope = ComponentScope.Singleton

            def find(self) -> str:
                return "in-memory"

        class PostgresRepo(AbstractRepo):
            class Config:
                scope = ComponentScope.Singleton

            def find(self) -> str:
                return "postgres"

        app_context.register_component(AbstractRepo)
        app_context.register_component(InMemoryRepo)
        app_context.register_component(PostgresRepo)
        app_context.init_ioc_container()

        class RepoConsumer(Component):
            repo: Annotated[AbstractRepo, "InMemoryRepo"]

        app_context.register_component(RepoConsumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(RepoConsumer)
        assert consumer is not None
        assert isinstance(consumer.repo, InMemoryRepo)
        assert consumer.repo.find() == "in-memory"

    def test_chained_qualifier_injection(self, app_context: ApplicationContext):
        """Component A depends on B via qualifier, B depends on C via qualifier.
        The entire chain should resolve correctly."""

        class AbstractLogger(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def log(self) -> str: ...

        class FileLogger(AbstractLogger):
            class Config:
                name = "FileLogger"
                scope = ComponentScope.Singleton

            def log(self) -> str:
                return "file"

        class ConsoleLogger(AbstractLogger):
            class Config:
                name = "ConsoleLogger"
                scope = ComponentScope.Singleton

            def log(self) -> str:
                return "console"

        class AbstractNotifier(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def notify(self) -> str: ...

        class EmailNotifier(AbstractNotifier):
            class Config:
                name = "EmailNotifier"
                scope = ComponentScope.Singleton

            logger: Annotated[AbstractLogger, "FileLogger"]

            def notify(self) -> str:
                return f"email+{self.logger.log()}"

        class SlackNotifier(AbstractNotifier):
            class Config:
                name = "SlackNotifier"
                scope = ComponentScope.Singleton

            logger: Annotated[AbstractLogger, "ConsoleLogger"]

            def notify(self) -> str:
                return f"slack+{self.logger.log()}"

        class AlertService(Component):
            class Config:
                scope = ComponentScope.Singleton

            notifier: Annotated[AbstractNotifier, "EmailNotifier"]

        app_context.register_component(AbstractLogger)
        app_context.register_component(FileLogger)
        app_context.register_component(ConsoleLogger)
        app_context.register_component(AbstractNotifier)
        app_context.register_component(EmailNotifier)
        app_context.register_component(SlackNotifier)
        app_context.register_component(AlertService)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        alert = app_context.get_component(AlertService)
        assert alert is not None
        assert isinstance(alert.notifier, EmailNotifier)
        assert isinstance(alert.notifier.logger, FileLogger)
        assert alert.notifier.notify() == "email+file"

    def test_annotated_with_extra_metadata_uses_first_as_qualifier(
        self, app_context: ApplicationContext
    ):
        """Annotated[T, 'qualifier', 'extra'] should use only the first
        metadata element as the qualifier and ignore the rest."""

        class AbstractCache(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def get(self) -> str: ...

        class RedisCache(AbstractCache):
            class Config:
                name = "RedisCache"
                scope = ComponentScope.Singleton

            def get(self) -> str:
                return "redis"

        class MemCache(AbstractCache):
            class Config:
                name = "MemCache"
                scope = ComponentScope.Singleton

            def get(self) -> str:
                return "memcache"

        app_context.register_component(AbstractCache)
        app_context.register_component(RedisCache)
        app_context.register_component(MemCache)
        app_context.init_ioc_container()

        class CacheConsumer(Component):
            cache: Annotated[AbstractCache, "RedisCache", "this-is-ignored"]

        app_context.register_component(CacheConsumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(CacheConsumer)
        assert consumer is not None
        assert isinstance(consumer.cache, RedisCache)

    def test_empty_string_qualifier_fails_injection(
        self, app_context: ApplicationContext
    ):
        """An empty string qualifier should not match any registered component
        and result in a dependency injection failure."""

        class AbstractWorker(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def work(self) -> str: ...

        class ConcreteWorker(AbstractWorker):
            class Config:
                name = "ConcreteWorker"
                scope = ComponentScope.Singleton

            def work(self) -> str:
                return "working"

        app_context.register_component(AbstractWorker)
        app_context.register_component(ConcreteWorker)
        app_context.init_ioc_container()

        class WorkerConsumer(Component):
            worker: Annotated[AbstractWorker, ""]

        app_context.register_component(WorkerConsumer)
        app_context.init_ioc_container()

        with pytest.raises(ValueError, match="DEPENDENCY INJECTION FAILED"):
            app_context.inject_dependencies_for_app_entities()

    def test_qualifier_on_concrete_type(self, app_context: ApplicationContext):
        """A qualifier can be used to inject a specific concrete component
        even when the type hint is also concrete (not abstract)."""

        class ServiceX(Component):
            class Config:
                name = "ServiceX"
                scope = ComponentScope.Singleton

            def run(self) -> str:
                return "X"

        class ServiceY(Component):
            class Config:
                name = "ServiceY"
                scope = ComponentScope.Singleton

            def run(self) -> str:
                return "Y"

        app_context.register_component(ServiceX)
        app_context.register_component(ServiceY)
        app_context.init_ioc_container()

        result = app_context.get_component(ServiceX, qualifier="ServiceX")
        assert result is not None
        assert isinstance(result, ServiceX)
        assert result.run() == "X"

    def test_multiple_consumers_share_singleton_via_qualifier(
        self, app_context: ApplicationContext
    ):
        """Two different consumers injecting the same qualifier should
        receive the exact same singleton instance."""

        class AbstractEngine(Component, ABC):
            class Config:
                scope = ComponentScope.Singleton

            @abstractmethod
            def start(self) -> str: ...

        class DieselEngine(AbstractEngine):
            class Config:
                name = "DieselEngine"
                scope = ComponentScope.Singleton

            def start(self) -> str:
                return "diesel"

        class ElectricEngine(AbstractEngine):
            class Config:
                name = "ElectricEngine"
                scope = ComponentScope.Singleton

            def start(self) -> str:
                return "electric"

        class CarA(Component):
            class Config:
                name = "CarA"
                scope = ComponentScope.Singleton

            engine: Annotated[AbstractEngine, "DieselEngine"]

        class CarB(Component):
            class Config:
                name = "CarB"
                scope = ComponentScope.Singleton

            engine: Annotated[AbstractEngine, "DieselEngine"]

        app_context.register_component(AbstractEngine)
        app_context.register_component(DieselEngine)
        app_context.register_component(ElectricEngine)
        app_context.register_component(CarA)
        app_context.register_component(CarB)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        car_a = app_context.get_component(CarA)
        car_b = app_context.get_component(CarB)
        assert car_a is not None
        assert car_b is not None
        assert car_a.engine is car_b.engine
        assert isinstance(car_a.engine, DieselEngine)
