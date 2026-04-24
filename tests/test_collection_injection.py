"""Tests for collection dependency injection (list[T], set[T], dict[str, T])."""

from abc import ABC, abstractmethod

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component, ComponentScope


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server)


class TestCollectionInjection:

    def test_inject_list_of_components(self, app_context: ApplicationContext):
        class Handler(Component, ABC):
            @abstractmethod
            def handle(self) -> str: ...

        class HandlerA(Handler):
            class Config:
                name = "HandlerA"
                scope = ComponentScope.Singleton

            def handle(self) -> str:
                return "A"

        class HandlerB(Handler):
            class Config:
                name = "HandlerB"
                scope = ComponentScope.Singleton

            def handle(self) -> str:
                return "B"

        class Dispatcher(Component):
            class Config:
                scope = ComponentScope.Singleton

            handlers: list[Handler]

        app_context.register_component(Handler)
        app_context.register_component(HandlerA)
        app_context.register_component(HandlerB)
        app_context.register_component(Dispatcher)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        dispatcher = app_context.get_component(Dispatcher)
        assert dispatcher is not None
        assert isinstance(dispatcher.handlers, list)
        assert len(dispatcher.handlers) == 2
        results = sorted(h.handle() for h in dispatcher.handlers)
        assert results == ["A", "B"]

    def test_inject_set_of_components(self, app_context: ApplicationContext):
        class Plugin(Component, ABC):
            @abstractmethod
            def name(self) -> str: ...

        class PluginX(Plugin):
            class Config:
                name = "PluginX"
                scope = ComponentScope.Singleton

            def name(self) -> str:
                return "X"

        class PluginY(Plugin):
            class Config:
                name = "PluginY"
                scope = ComponentScope.Singleton

            def name(self) -> str:
                return "Y"

        class PluginHost(Component):
            class Config:
                scope = ComponentScope.Singleton

            plugins: set[Plugin]

        app_context.register_component(Plugin)
        app_context.register_component(PluginX)
        app_context.register_component(PluginY)
        app_context.register_component(PluginHost)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        host = app_context.get_component(PluginHost)
        assert host is not None
        assert isinstance(host.plugins, set)
        assert len(host.plugins) == 2
        names = sorted(p.name() for p in host.plugins)
        assert names == ["X", "Y"]

    def test_inject_dict_of_components(self, app_context: ApplicationContext):
        class Validator(Component, ABC):
            @abstractmethod
            def validate(self) -> bool: ...

        class EmailValidator(Validator):
            class Config:
                name = "EmailValidator"
                scope = ComponentScope.Singleton

            def validate(self) -> bool:
                return True

        class PhoneValidator(Validator):
            class Config:
                name = "PhoneValidator"
                scope = ComponentScope.Singleton

            def validate(self) -> bool:
                return False

        class ValidationService(Component):
            class Config:
                scope = ComponentScope.Singleton

            validators: dict[str, Validator]

        app_context.register_component(Validator)
        app_context.register_component(EmailValidator)
        app_context.register_component(PhoneValidator)
        app_context.register_component(ValidationService)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        svc = app_context.get_component(ValidationService)
        assert svc is not None
        assert isinstance(svc.validators, dict)
        assert len(svc.validators) == 2
        assert "EmailValidator" in svc.validators
        assert "PhoneValidator" in svc.validators
        assert svc.validators["EmailValidator"].validate() is True
        assert svc.validators["PhoneValidator"].validate() is False

    def test_inject_list_includes_beans(self, app_context: ApplicationContext):
        class Notifier:
            pass

        class EmailNotifier(Notifier):
            pass

        class SlackNotifier(Notifier):
            pass

        class NotifierBeans(BeanCollection):
            @staticmethod
            def create_email_notifier() -> EmailNotifier:
                return EmailNotifier()

            @staticmethod
            def create_slack_notifier() -> SlackNotifier:
                return SlackNotifier()

        class AlertService(Component):
            class Config:
                scope = ComponentScope.Singleton

            notifiers: list[Notifier]

        app_context.register_component(AlertService)
        app_context.register_bean_collection(NotifierBeans)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        svc = app_context.get_component(AlertService)
        assert svc is not None
        assert isinstance(svc.notifiers, list)
        assert len(svc.notifiers) == 2
        assert any(isinstance(n, EmailNotifier) for n in svc.notifiers)
        assert any(isinstance(n, SlackNotifier) for n in svc.notifiers)

    def test_inject_empty_list_when_no_matches(self, app_context: ApplicationContext):
        class NonExistent:
            pass

        class Consumer(Component):
            class Config:
                scope = ComponentScope.Singleton

            items: list[NonExistent]

        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert consumer.items == []

    def test_non_collection_generic_is_skipped(self, app_context: ApplicationContext):
        """Non-collection generic types (e.g. Optional) should not raise errors."""

        class MyService(Component):
            class Config:
                scope = ComponentScope.Singleton

            count: int

        app_context.register_component(MyService)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()
