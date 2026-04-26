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
from py_spring_core.core.entities.component.component import Component
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
