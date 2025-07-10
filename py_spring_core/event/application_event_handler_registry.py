
from threading import Thread
from typing import Callable, ClassVar, Type

from loguru import logger
from pydantic import BaseModel

from py_spring_core.core.entities.component import Component
from py_spring_core.core.interfaces.application_context_required import ApplicationContextRequired
from py_spring_core.event.commons import ApplicationEvent, EventQueue

EventHandlerT = Callable[[Component, ApplicationEvent], None]

def EventListener(event_type: Type[ApplicationEvent]) -> Callable:
    """
    The EventListener decorator is used to register an event handler for an application event.
    It is responsible for binding an event handler to a component and a function.
    """
    def decorator(func: EventHandlerT) -> None:
        if not issubclass(event_type, ApplicationEvent):
            raise ValueError(f"Event type must be a subclass of ApplicationEvent")

        ApplicationEventHandlerRegistry.register_event_handler(event_type, func)
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
    _class_event_handlers: ClassVar[dict[str, list[EventHandler]]] = {}
    def __init__(self) -> None:
        self._event_handlers: dict[str, list[EventHandler]] = {}
        self._event_message_queue = EventQueue.queue

    def post_construct(self) -> None:
        logger.info("Initializing event handlers...")
        self._init_event_handlers()
        logger.info("Starting event message handler thread...")
        Thread(target= self._handle_messages, daemon=True).start()

    def _init_event_handlers(self) -> None:
        app_context = self.get_application_context()
        # get_name might be different from the class name, so we use the class name for function binding
        self.component_instance_map = {
            component.__class__.__name__: component 
            for component in app_context.get_singleton_component_instances()
        }
        self._event_handlers = self._class_event_handlers


    @classmethod
    def register_event_handler(cls, event_type: Type[ApplicationEvent], handler: EventHandlerT):
        event_name = event_type.__name__
        func_name_parts = handler.__qualname__.split(".")
        if len(func_name_parts) != 2:
            raise ValueError(f"Handler must be a member function of a class")
        class_name, func_name = func_name_parts
        if event_name not in cls._class_event_handlers:
            cls._class_event_handlers[event_name] = []
        event_handler = EventHandler(class_name=class_name, func_name=func_name, event_type=event_type, func=handler)
        if event_handler not in cls._class_event_handlers[event_name]:
            cls._class_event_handlers[event_name].append(event_handler)

    def get_event_handlers(self, event_type: Type[ApplicationEvent]) -> list[EventHandler]:
        event_name = event_type.__name__
        handlers = self._event_handlers.get(event_name, [])
        return handlers
    
    def _handle_messages(self) -> None:
        logger.info("Event message handler thread started...")
        while True:
            message = self._event_message_queue.get()
            for handler in self.get_event_handlers(message.__class__):
                try:
                    optional_instance = self.component_instance_map.get(handler.class_name, None)
                    if optional_instance is None:
                        logger.error(f"Component instance not found for handler: {handler.class_name}")
                        continue
                    handler.func(optional_instance, message)
                except Exception as error:
                    logger.error(f"Error handling event: {error}")
            