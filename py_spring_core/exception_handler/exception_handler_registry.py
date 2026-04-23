

from typing import Any, Callable, Type, TypeVar

from loguru import logger

E = TypeVar('E', bound=Exception)

class ExceptionHandlerRegistry:
    _handlers: dict[str, Callable[[Any], Any]] = {}

    @classmethod
    def register(cls, exception_cls: Type[E], handler: Callable[[E], Any]):
        key = exception_cls.__name__
        handler_name = getattr(handler, "__name__", repr(handler))
        logger.debug(f"Registering exception handler for {key}: {handler_name}")
        if key in cls._handlers:
            error_message = f"Exception handler for {exception_cls} already registered"
            logger.error(error_message)
            raise RuntimeError(error_message)
        
        cls._handlers[exception_cls.__name__] = handler

    @classmethod
    def get_handler(cls, exception_cls: Type[E]) -> Callable[[E], Any]:
        return cls._handlers[exception_cls.__name__]