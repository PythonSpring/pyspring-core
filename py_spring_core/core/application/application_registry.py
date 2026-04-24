from dataclasses import dataclass, field
from queue import Queue
from typing import Any, Callable

from py_spring_core.core.entities.controllers.route_mapping import RouteRegistration
from py_spring_core.event.commons import ApplicationEvent


@dataclass
class ApplicationRegistry:
    """
    Owns all mutable state that was previously scattered across class variables.
    One instance per PySpringApplication. Passed through ApplicationContext.
    """

    # Route registrations: class_name -> set of routes
    routes: dict[str, set[RouteRegistration]] = field(default_factory=dict)

    # Event handlers: event_name -> list of handler info
    # Stored as dicts to avoid circular import with EventHandler
    event_handlers: dict[str, list[Any]] = field(default_factory=dict)

    # Exception handlers: exception_class_name -> handler callable
    exception_handlers: dict[str, Callable] = field(default_factory=dict)

    # Properties loaded from config files
    loaded_properties: dict[str, Any] = field(default_factory=dict)

    # Event message queue
    event_queue: Queue[ApplicationEvent] = field(default_factory=Queue)

    def clear(self) -> None:
        """Reset all state. Useful for testing."""
        self.routes.clear()
        self.event_handlers.clear()
        self.exception_handlers.clear()
        self.loaded_properties.clear()
        self.event_queue = Queue()
