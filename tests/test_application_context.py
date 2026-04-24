import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.properties.properties import Properties


class TestApplicationContext:
    @pytest.fixture
    def server(self) -> FastAPI:
        return FastAPI()

    @pytest.fixture
    def app_context(self, server: FastAPI):
        config = ApplicationContextConfig(properties_path="")
        return ApplicationContext(config, server=server)

    def test_register_entities_correctly(self, app_context: ApplicationContext):
        class TestComponent(Component): ...

        class TestController(RestController): ...

        class TestBeanCollection(BeanCollection): ...

        class TestProperties(Properties):
            __key__ = "test_properties"

        app_context.register_component(TestComponent)
        app_context.register_controller(TestController)
        app_context.register_bean_collection(TestBeanCollection)
        app_context.register_properties(TestProperties)

        assert (
            "TestComponent" in app_context.container_manager.component_classes
            and app_context.container_manager.component_classes["TestComponent"]
            == TestComponent
        )
        assert (
            "TestController" in app_context.container_manager.controller_classes
            and app_context.container_manager.controller_classes["TestController"]
            == TestController
        )
        assert (
            "TestBeanCollection"
            in app_context.container_manager.bean_collection_classes
            and app_context.container_manager.bean_collection_classes[
                "TestBeanCollection"
            ]
            == TestBeanCollection
        )
        assert (
            "test_properties" in app_context.container_manager.properties_classes
            and app_context.container_manager.properties_classes[
                "test_properties"
            ]
            == TestProperties
        )

    def test_registering_entities_without_errors(self, app_context: ApplicationContext):
        class TestComponent(Component): ...

        class TestController(RestController): ...

        class TestBeanCollection(BeanCollection): ...

        class TestProperties(Properties):
            __key__ = "test_properties"

        app_context.register_component(TestComponent)
        app_context.register_controller(TestController)
        app_context.register_bean_collection(TestBeanCollection)
        app_context.register_properties(TestProperties)

        assert "TestComponent" in app_context.container_manager.component_classes
        assert (
            "TestController" in app_context.container_manager.controller_classes
        )
        assert (
            "TestBeanCollection"
            in app_context.container_manager.bean_collection_classes
        )
        assert (
            "test_properties" in app_context.container_manager.properties_classes
        )

    def test_register_invalid_entities_raises_error(
        self, app_context: ApplicationContext
    ):
        """
        Tests that attempting to register invalid entities (not subclasses of the expected base classes) with the ApplicationContext raises the expected TypeError.
        """

        class InvalidComponent: ...

        class InvalidController: ...

        class InvalidBeanCollection: ...

        class InvalidProperties: ...

        with pytest.raises(TypeError):
            app_context.register_component(InvalidComponent)  # type: ignore

        with pytest.raises(TypeError):
            app_context.register_controller(InvalidController)  # type: ignore

        with pytest.raises(TypeError):
            app_context.register_bean_collection(InvalidBeanCollection)  # type: ignore

        with pytest.raises(TypeError):
            app_context.register_properties(InvalidProperties)  # type: ignore

    def test_retrieve_singleton_app_entities(self, app_context: ApplicationContext):
        """
        Tests the retrieval of singleton instances of application entities (components, beans, and properties) from the ApplicationContext.

        This test ensures that the ApplicationContext correctly retrieves and returns the singleton instances of the registered components, beans, and properties.
        """

        class TestComponent(Component):
            pass

        class TestController(RestController):
            pass

        class TestBeanCollection(BeanCollection):
            pass

        class TestProperties(Properties):
            __key__ = "test_properties"

        app_context.register_component(TestComponent)
        app_context.register_controller(TestController)
        app_context.register_bean_collection(TestBeanCollection)
        app_context.register_properties(TestProperties)

        # Test retrieving singleton components
        component_instance = TestComponent()
        app_context.container_manager.component_instances[
            "TestComponent"
        ] = component_instance
        retrieved_component = app_context.get_component(TestComponent, None)
        assert retrieved_component is component_instance

        # Test retrieving singleton beans
        bean_instance = TestBeanCollection()
        app_context.container_manager.bean_instances[
            "TestBeanCollection"
        ] = bean_instance
        retrieved_bean = app_context.get_bean(TestBeanCollection, None)
        assert retrieved_bean is bean_instance

        # Test retrieving singleton properties
        properties_instance = TestProperties()
        app_context.container_manager.properties_instances[
            "test_properties"
        ] = properties_instance
        retrieved_properties = app_context.get_properties(TestProperties)
        assert retrieved_properties is properties_instance

    def test_inject_dependencies_for_components(
        self, app_context: ApplicationContext
    ):
        """
        Tests the injection of dependencies for component instances in the ApplicationContext.

        This test ensures that the ApplicationContext correctly injects the dependencies
        onto singleton component instances (not on classes).
        """

        class TestNestedComponent(Component): ...

        class TestComponent(Component):
            test_nested_component: TestNestedComponent

        app_context.register_component(TestComponent)
        app_context.register_component(TestNestedComponent)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        test_component_instance = app_context.get_component(TestComponent)
        assert test_component_instance is not None
        assert hasattr(test_component_instance, "test_nested_component")
        assert isinstance(
            test_component_instance.test_nested_component, TestNestedComponent
        )

    def test_inject_dependencies_for_controllers(
        self, app_context: ApplicationContext
    ):
        """
        Tests that controller instances receive DI when injected via inject_dependencies_for_instance.
        """

        class TestComponent(Component): ...

        class TestController(RestController):
            test_component: TestComponent

        app_context.register_component(TestComponent)
        app_context.register_controller(TestController)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        controller: TestController = app_context.get_controller_instances()[0] # type: ignore
        app_context.inject_dependencies_for_instance(controller)
        assert hasattr(controller, "test_component")
        assert isinstance(controller.test_component, TestComponent)
