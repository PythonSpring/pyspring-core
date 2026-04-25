import pytest
from fastapi import FastAPI

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
