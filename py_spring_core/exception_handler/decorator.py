

from functools import wraps
from typing import Any, Callable, Type


from py_spring_core.exception_handler.exception_handler_registry import ExceptionHandlerRegistry


def ExceptionHandler(exception_cls: Type[Exception]) -> Callable[[Callable[[Exception], Any]], Callable]:
    def decorator(func: Callable[[Exception], Any]) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)
        ExceptionHandlerRegistry.register(exception_cls, wrapper)
        return wrapper
    
    return decorator