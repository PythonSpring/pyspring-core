from functools import wraps
from typing import Any, Callable, Type, TypeVar

from py_spring_core.exception_handler.exception_handler_registry import ExceptionHandlerRegistry

E = TypeVar("E", bound=Exception)


def ExceptionHandler(exception_cls: Type[E]) -> Callable[[Callable[[E], Any]], Callable]:
    def decorator(func: Callable[[E], Any]) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)
        ExceptionHandlerRegistry.register(exception_cls, wrapper)
        return wrapper
    return decorator