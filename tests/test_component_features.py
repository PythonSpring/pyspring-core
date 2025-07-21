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

        # Register component first time
        app_context.register_component(TestService)
        initial_count = len(app_context.container_manager.component_cls_container)

        # Register same component again - should be silently skipped
        app_context.register_component(TestService)
        final_count = len(app_context.container_manager.component_cls_container)

        # Verify component count didn't change (no duplicate registration)
        assert final_count == initial_count
        assert "TestService" in app_context.container_manager.component_cls_container

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

        # Verify component is registered with custom name
        assert (
            "CustomServiceName" in app_context.container_manager.component_cls_container
        )
        assert (
            app_context.container_manager.component_cls_container["CustomServiceName"]
            == TestService
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
