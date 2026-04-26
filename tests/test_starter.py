import pytest
from fastapi import FastAPI
from unittest.mock import MagicMock

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    InvalidDependencyError,
)
from py_spring_core.core.application.context.application_context_config import (
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component.component import Component, ComponentLifeCycle
from py_spring_core.core.starter.py_spring_starter import PySpringStarter


class TestComponent(Component): ...


class TestStarter:
    @pytest.fixture
    def test_starter(self):
        return PySpringStarter(depends_on=[TestComponent])

    @pytest.fixture
    def server(self) -> FastAPI:
        return FastAPI()

    @pytest.fixture
    def test_app_context(
        self, test_starter: PySpringStarter, server: FastAPI
    ) -> ApplicationContext:
        app_context = ApplicationContext(
            ApplicationContextConfig(properties_path=""), server=server
        )
        app_context.starters.append(test_starter)
        return app_context

    def test_did_raise_error_when_no_depends_on_is_provided(
        self, test_app_context: ApplicationContext
    ):
        with pytest.raises(InvalidDependencyError):
            test_app_context.validate_starters()

    def test_did_not_raise_error_when_depends_on_is_provided(
        self, test_app_context: ApplicationContext
    ):
        test_app_context.register_component(TestComponent)
        test_app_context.validate_starters()


class AnotherComponent(Component): ...


class ConfigurableStarter(PySpringStarter):
    def on_configure(self) -> None:
        self.component_classes.append(AnotherComponent)


class ContextAwareStarter(PySpringStarter):
    context_seen_in_init: object = None

    def on_initialized(self) -> None:
        self.context_seen_in_init = self.app_context


class DestroyAwareStarter(PySpringStarter):
    destroyed: bool = False

    def on_destroy(self) -> None:
        self.destroyed = True


class OrderTrackingComponent(Component):
    order_log: list[str] = []

    def pre_destroy(self) -> None:
        OrderTrackingComponent.order_log.append("component_pre_destroy")


class OrderTrackingStarter(PySpringStarter):
    order_log: list[str] = []

    def on_destroy(self) -> None:
        OrderTrackingStarter.order_log.append("starter_on_destroy")


class TestStarterLifecycle:
    def test_on_configure_populates_entities(self):
        starter = ConfigurableStarter()
        starter.on_configure()
        entities = starter.get_entities()
        assert AnotherComponent in entities

    def test_get_entities_is_pure_without_on_configure(self):
        starter = ConfigurableStarter()
        entities = starter.get_entities()
        assert AnotherComponent not in entities
        assert entities == []

    def test_backward_compat_dataclass_style(self):
        starter = PySpringStarter(component_classes=[TestComponent])
        entities = starter.get_entities()
        assert TestComponent in entities

    def test_set_context_provides_app_context(self):
        starter = PySpringStarter()
        mock_ctx = MagicMock()
        starter.set_context(mock_ctx)
        assert starter.app_context is mock_ctx

    def test_on_initialized_can_use_app_context(self):
        starter = ContextAwareStarter()
        mock_ctx = MagicMock()
        starter.set_context(mock_ctx)
        starter.on_initialized()
        assert starter.context_seen_in_init is mock_ctx

    def test_on_destroy_default_is_noop(self):
        starter = PySpringStarter()
        starter.on_destroy()

    def test_finish_destruction_cycle_calls_on_destroy(self):
        starter = DestroyAwareStarter()
        assert not starter.destroyed
        starter.finish_destruction_cycle()
        assert starter.destroyed


class TestStarterTeardownOrdering:
    def test_on_destroy_called_after_component_pre_destroy(self):
        from py_spring_core.core.application.py_spring_application import (
            PySpringApplication,
        )

        OrderTrackingComponent.order_log = []
        OrderTrackingStarter.order_log = []
        shared_log: list[str] = []

        original_component_pre_destroy = OrderTrackingComponent.pre_destroy
        original_starter_on_destroy = OrderTrackingStarter.on_destroy

        def tracked_component_pre_destroy(self):
            shared_log.append("component_pre_destroy")
            original_component_pre_destroy(self)

        def tracked_starter_on_destroy(self):
            shared_log.append("starter_on_destroy")
            original_starter_on_destroy(self)

        OrderTrackingComponent.pre_destroy = tracked_component_pre_destroy
        OrderTrackingStarter.on_destroy = tracked_starter_on_destroy

        try:
            starter = OrderTrackingStarter(
                component_classes=[OrderTrackingComponent],
            )
            app = PySpringApplication.__new__(PySpringApplication)
            starters: list[PySpringStarter] = [starter]
            app.starters = starters

            server = FastAPI()
            app.app_context = ApplicationContext(
                ApplicationContextConfig(properties_path=""), server=server
            )
            app.app_context.register_component(OrderTrackingComponent)
            app.app_context.init_ioc_container()
            app.app_context.inject_dependencies_for_app_entities()
            app._handle_singleton_components_life_cycle(
                ComponentLifeCycle.Init
            )

            # Simulate teardown
            app._handle_singleton_components_life_cycle(
                ComponentLifeCycle.Destruction
            )
            app._notify_starters_destroyed(app.starters)

            assert shared_log == [
                "component_pre_destroy",
                "starter_on_destroy",
            ]
        finally:
            OrderTrackingComponent.pre_destroy = original_component_pre_destroy
            OrderTrackingStarter.on_destroy = original_starter_on_destroy
