
from typing import Any, Callable, Type

from pydantic import BaseModel


class ApplicationEvent(BaseModel): ...

class ApplicationEventHandlerRegistry:
    event_handlers: dict[str, dict[str, Callable[..., Any]]] = {}

    @classmethod
    def register_event_handler(cls, event_type: Type[ApplicationEvent], handler: Callable[[ApplicationEvent], None]):
        event_name = event_type.__name__
        handler_name = handler.__name__
        if event_name not in cls.event_handlers:
            cls.event_handlers[event_name] = {}
        cls.event_handlers[event_name][handler_name] = handler

    @classmethod
    def get_event_handlers(cls, event_type: Type[ApplicationEvent]) -> list[Callable[[ApplicationEvent], None]]:
        event_name = event_type.__name__
        handlers = cls.event_handlers.get(event_name, {})
        return list(handlers.values())