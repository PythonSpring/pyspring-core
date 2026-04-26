from dataclasses import dataclass, field
from typing import Any, Optional, Type, final

from py_spring_core.core.application.commons import AppEntities
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.properties.properties import Properties

try:
    from py_spring_core.core.application.context.application_context import (
        ApplicationContext,
    )
except ImportError:
    ...


@dataclass
class PySpringStarter:
    component_classes: list[Type[Component]] = field(default_factory=list)
    bean_collection_classes: list[Type[BeanCollection]] = field(default_factory=list)
    properties_classes: list[Type[Properties]] = field(default_factory=list)
    rest_controller_classes: list[Type[RestController]] = field(default_factory=list)
    depends_on: list[Type[AppEntities]] = field(default_factory=list)
    external_dependencies: list[Any] = field(default_factory=list)
    app_context: Optional["ApplicationContext"] = None

    def on_configure(self) -> None:
        """Override in subclasses to configure the starter before the IoC container is built.

        Use this to register entities (append to component_classes, etc.)
        or perform any pre-IoC setup.
        """
        ...

    def get_entities(self) -> list[Type[AppEntities]]:
        return [
            *self.component_classes,
            *self.bean_collection_classes,
            *self.properties_classes,
            *self.rest_controller_classes,
        ]

    def set_context(self, app_context: "ApplicationContext") -> None:
        self.app_context = app_context

    def on_initialized(self) -> None:
        """Override in subclasses for post-initialization logic.

        Called by the framework after the IoC container is built, dependencies
        are injected, and app_context is set.
        """
        ...

    def on_destroy(self) -> None:
        """Override in subclasses for cleanup logic before the starter is destroyed.

        Called by the framework during application shutdown, after all singleton
        components have been destroyed.
        """
        ...

    @final
    def finish_destruction_cycle(self) -> None:
        self.on_destroy()
