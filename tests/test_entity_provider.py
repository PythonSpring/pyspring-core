from fastapi import FastAPI
import pytest

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    InvalidDependencyError,
)
from py_spring_core.core.application.context.application_context_config import (
    ApplicationContextConfig,
)
from py_spring_core.core.entities.component import Component
from py_spring_core.core.entities.entity_provider import EntityProvider


class TestComponent(Component): ...


class TestEntityProvider:
    @pytest.fixture
    def test_entity_provider(self):
        return EntityProvider(depends_on=[TestComponent])
    
    @pytest.fixture
    def server(self) -> FastAPI:
        return FastAPI()

    @pytest.fixture
    def test_app_context(
        self, test_entity_provider: EntityProvider, server: FastAPI
    ) -> ApplicationContext:
        app_context = ApplicationContext(ApplicationContextConfig(properties_path=""), server=server)
        app_context.providers.append(test_entity_provider)
        return app_context

    def test_did_raise_error_when_no_depends_on_is_provided(
        self, test_app_context: ApplicationContext
    ):
        with pytest.raises(InvalidDependencyError):
            test_app_context.validate_entity_providers()

    def test_did_not_raise_error_when_depends_on_is_provided(
        self, test_app_context: ApplicationContext
    ):
        test_app_context.register_component(TestComponent)
        test_app_context.validate_entity_providers()
