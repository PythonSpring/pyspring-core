from fastapi import FastAPI
import pytest

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection import BeanCollection
from py_spring_core.core.entities.component import Component
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
            "TestComponent" in app_context.component_cls_container
            and app_context.component_cls_container["TestComponent"] == TestComponent
        )
        assert (
            "TestController" in app_context.controller_cls_container
            and app_context.controller_cls_container["TestController"] == TestController
        )
        assert (
            "TestBeanCollection" in app_context.bean_collection_cls_container
            and app_context.bean_collection_cls_container["TestBeanCollection"]
            == TestBeanCollection
        )
        assert (
            "test_properties" in app_context.properties_cls_container
            and app_context.properties_cls_container["test_properties"]
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

        assert "TestComponent" in app_context.component_cls_container
        assert "TestController" in app_context.controller_cls_container
        assert "TestBeanCollection" in app_context.bean_collection_cls_container
        assert "test_properties" in app_context.properties_cls_container

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
        app_context.singleton_component_instance_container["TestComponent"] = (
            component_instance
        )
        retrieved_component = app_context.get_component(TestComponent, None)
        assert retrieved_component is component_instance

        # Test retrieving singleton beans
        bean_instance = TestBeanCollection()
        app_context.singleton_bean_instance_container["TestBeanCollection"] = (
            bean_instance
        )
        retrieved_bean = app_context.get_bean(TestBeanCollection, None)
        assert retrieved_bean is bean_instance

        # Test retrieving singleton properties
        properties_instance = TestProperties()
        app_context.singleton_properties_instance_container["test_properties"] = (
            properties_instance
        )
        retrieved_properties = app_context.get_properties(TestProperties)
        assert retrieved_properties is properties_instance

    def test_inject_dependencies_for_components_and_controllers(
        self, app_context: ApplicationContext
    ):
        """
        Tests the injection of dependencies for components and controllers in the ApplicationContext.

        This test ensures that the ApplicationContext correctly injects the dependencies for the registered components and controllers. It verifies that the necessary dependencies are available and accessible on the component and controller instances.
        """

        class TestNestedComponent(Component): ...

        class TestComponent(Component):
            test_nested_component: TestNestedComponent

        class TestController(RestController):
            test_component: TestComponent

        app_context.register_component(TestComponent)
        app_context.register_component(TestNestedComponent)
        app_context.register_controller(TestController)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()
        assert hasattr(TestComponent, "test_nested_component") and isinstance(
            TestComponent.test_nested_component, TestNestedComponent
        )
        assert hasattr(TestController, "test_component") and isinstance(
            TestController.test_component, TestComponent
        )
