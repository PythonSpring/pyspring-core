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
    """Base class for framework starters that register entities into the IoC container.

    A starter bundles related components, properties, bean collections, and controllers
    into a reusable module. Starters are auto-discovered via the ``pyspring.starters``
    entry-point group or registered manually on ``PySpringApplication``.

    Lifecycle:
        1. ``on_configure()``  — called before the IoC container is built.
        2. IoC container initializes (components, beans, properties wired).
        3. ``set_context()``   — framework injects the ``ApplicationContext``.
        4. ``on_initialized()``— called after the container is fully ready.
        5. ``on_destroy()``    — called during shutdown, after component destruction.

    Exposing derived objects:
        Starters can accept user-input ``Properties`` and expose system-assembled
        objects for injection elsewhere by combining ``Properties`` with a
        ``BeanCollection``. This is useful when a starter needs to build a
        configured client, connection pool, or similar derived object from raw
        user configuration.

        Example::

            class DatabaseProperties(Properties):
                __key__ = "database"
                host: str = "localhost"
                port: int = 5432
                db_name: str = "mydb"

            class DataSourceConfig:
                def __init__(self, connection_string: str):
                    self.connection_string = connection_string

            class DataSourceBeanCollection(BeanCollection):
                db_props: DatabaseProperties

                @classmethod
                def create_data_source_config(cls) -> DataSourceConfig:
                    p = cls.db_props
                    return DataSourceConfig(f"postgresql://{p.host}:{p.port}/{p.db_name}")

            class DatabaseStarter(PySpringStarter):
                def on_configure(self) -> None:
                    self.properties_classes.append(DatabaseProperties)
                    self.bean_collection_classes.append(DataSourceBeanCollection)

        Any ``Component`` can then inject the derived bean directly::

            class UserRepository(Component):
                data_source: DataSourceConfig  # injected automatically
    """
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
