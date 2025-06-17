
from typing import Any, Callable, Type


class ApplicationEvent: ...

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
        return list(cls.event_handlers[event_name].values())