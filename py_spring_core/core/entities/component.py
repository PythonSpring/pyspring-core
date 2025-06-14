from enum import Enum
from typing import Type, final


class ComponentLifeCycle(Enum):
    """
    The `ComponentLifeCycle` enum defines the possible lifecycle stages for a `Component` in the application.
    The `Init` stage represents the initialization of the component, while the `Destruction` stage represents the destruction of the component.
    """

    Init = "initialization"
    Destruction = "destruction"


class ComponentScope(Enum):
    """
    The `ComponentScope` enum defines the possible scopes for a `Component` in the application.
    The `Singleton` scope indicates that there should be a single instance of the component shared across the application,
    while the `Prototype` scope indicates that a new instance of the component should be created each time it is requested.
    """

    Singleton = "Singleton"
    Prototype = "Prototype"


class Component:
    """
    The `Component` class is the base class for all components in the application. It provides a set of lifecycle hooks that can be overridden by subclasses to customize the initialization and destruction of the component.

    The `Config` class is a nested class within `Component` that holds configuration options for the component, such as the component's scope (either `Singleton` or `Prototype`).

    The `get_name()` method returns the name of the component class.
    The `get_component_base()` method returns the base `Component` class.
    The `get_scope()` and `set_scope()` methods allow you to get and set the scope of the component.

    The lifecycle hooks are:
    - `post_initialize()`: Called after the component is initialized.
    - `pre_destroy()`: Called before the component is destroyed.

    The `finish_initialization_cycle()` and `finish_destruction_cycle()` methods are final and call the corresponding lifecycle hooks in the correct order.
    """

    class Config:
        name: str = ""
        scope: ComponentScope = ComponentScope.Singleton

    @classmethod
    def get_name(cls) -> str:
        if hasattr(cls.Config, "name") and cls.Config.name:
            return cls.Config.name
        return cls.__name__

    @classmethod
    def get_component_base(cls) -> "Type[Component]":
        return cls

    @classmethod
    def get_scope(cls) -> ComponentScope:
        return cls.Config.scope

    @classmethod
    def set_scope(cls, scope: ComponentScope) -> None:
        cls.Config.scope = scope

    def post_construct(self) -> None:
        """Hook method called after construction (i.e., __init__)"""
        pass

    def pre_destroy(self) -> None:
        """Hook method called before destruction"""
        pass

    @final
    def finish_initialization_cycle(self) -> None:
        self.post_construct()

    @final
    def finish_destruction_cycle(self) -> None:
        self.pre_destroy()
