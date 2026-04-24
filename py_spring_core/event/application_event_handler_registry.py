from threading import Thread
from typing import Callable, Optional, Type

from loguru import logger
from pydantic import BaseModel

from py_spring_core.core.entities.component.component import Component
from py_spring_core.core.interfaces.application_context_required import (
    ApplicationContextRequired,
)
from py_spring_core.event.commons import ApplicationEvent, _ShutdownSentinel

EventHandlerT = Callable[[Component, ApplicationEvent], None]


# Module-level staging area for import-time event handler registrations.
# Drained into ApplicationRegistry at app boot, then cleared.
_pending_event_handlers: list["EventHandler"] = []


def _register_event_handler(
    event_type: Type[ApplicationEvent], handler: EventHandlerT
) -> None:
    """Build an EventHandler from the decorated function and stage it."""
    handler_name = getattr(handler, "__qualname__", "")
    func_name_parts = handler_name.split(".")
    if len(func_name_parts) != 2:
        raise ValueError("Handler must be a member function of a class")
    class_name, func_name = func_name_parts
    event_handler = EventHandler(
        class_name=class_name,
        func_name=func_name,
        event_type=event_type,
        func=handler,
    )
    if event_handler not in _pending_event_handlers:
        _pending_event_handlers.append(event_handler)


def drain_pending_event_handlers() -> list["EventHandler"]:
    """Return all pending event handler registrations and clear the staging area."""
    handlers = list(_pending_event_handlers)
    _pending_event_handlers.clear()
    return handlers


def EventListener(event_type: Type[ApplicationEvent]) -> Callable:
    """
    The EventListener decorator is used to register an event handler for an application event.
    It is responsible for binding an event handler to a component and a function.
    """

    def decorator(func: EventHandlerT) -> EventHandlerT:
        if not issubclass(event_type, ApplicationEvent):
            raise ValueError("Event type must be a subclass of ApplicationEvent")

        _register_event_handler(event_type, func)
        return func

    return decorator


class EventHandler(BaseModel):
    """
    The EventHandler class is a model that represents an event handler for an application event.
    It is responsible for binding an event handler to a component and a function.
    """

    class_name: str
    func_name: str
    event_type: Type[ApplicationEvent]
    func: EventHandlerT

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventHandler):
            return False
        return self.class_name == other.class_name and self.func_name == other.func_name

    def __hash__(self) -> int:
        return hash((self.class_name, self.func_name))


class ApplicationEventHandlerRegistry(Component, ApplicationContextRequired):
    """
    The ApplicationEventHandlerRegistry is a component that registers event handlers for application events.
    It is responsible for binding event handlers to their corresponding components and handling event messages.

    The class performs the following key tasks:
    - Registers event handlers for application events
    - Binds event handlers to their corresponding components
    """

    def __init__(self) -> None:
        self._event_handlers: dict[str, list[EventHandler]] = {}
        self._message_thread: Optional[Thread] = None

    def post_construct(self) -> None:
        logger.info("Initializing event handlers...")
        self._init_event_handlers()
        logger.info("Starting event message handler thread...")
        self._message_thread = Thread(target=self._handle_messages, daemon=True)
        self._message_thread.start()

    def _init_event_handlers(self) -> None:
        app_context = self.get_application_context()
        # get_name might be different from the class name, so we use the class name for function binding
        self.component_instance_map = {
            component.__class__.__name__: component
            for component in app_context.get_singleton_component_instances()
        }
        self._event_handlers = app_context.registry.event_handlers

    def get_event_handlers(
        self, event_type: Type[ApplicationEvent]
    ) -> list[EventHandler]:
        event_name = event_type.__name__
        handlers = self._event_handlers.get(event_name, [])
        return handlers

    def _handle_messages(self) -> None:
        app_context = self.get_application_context()
        event_queue = app_context.registry.event_queue
        logger.info("Event message handler thread started...")
        while True:
            message = event_queue.get()
            if isinstance(message, _ShutdownSentinel):
                logger.info("Event message handler thread stopping...")
                break
            for handler in self.get_event_handlers(message.__class__):
                try:
                    optional_instance = self.component_instance_map.get(
                        handler.class_name, None
                    )
                    if optional_instance is None:
                        logger.error(
                            f"Component instance not found for handler: {handler.class_name}"
                        )
                        continue
                    handler.func(optional_instance, message)
                except Exception as error:
                    logger.error(f"Error handling event: {error}")

    def shutdown(self, timeout: float = 5.0) -> None:
        """Stop the event message handler thread gracefully."""
        if self._message_thread is not None and self._message_thread.is_alive():
            app_context = self.get_application_context()
            app_context.registry.event_queue.put(_ShutdownSentinel())
            self._message_thread.join(timeout=timeout)
            if self._message_thread.is_alive():
                logger.warning("Event message handler thread did not stop within timeout")
