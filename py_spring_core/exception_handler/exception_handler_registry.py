from typing import Any, Callable, Type, TypeVar

from loguru import logger

E = TypeVar('E', bound=Exception)

# Module-level staging area for import-time exception handler registrations.
# Drained into ApplicationRegistry at app boot, then cleared.
_pending_exception_handlers: list[tuple[str, Callable]] = []


def drain_pending_exception_handlers() -> list[tuple[str, Callable]]:
    """Return all pending exception handler registrations and clear the staging area."""
    handlers = list(_pending_exception_handlers)
    _pending_exception_handlers.clear()
    return handlers


class ExceptionHandlerRegistry:

    @classmethod
    def register(cls, exception_cls: Type[E], handler: Callable[[E], Any]) -> None:
        key = exception_cls.__name__
        handler_name = getattr(handler, "__name__", repr(handler))
        logger.debug(f"Registering exception handler for {key}: {handler_name}")
        # Check for duplicates in pending list
        for existing_key, _ in _pending_exception_handlers:
            if existing_key == key:
                error_message = f"Exception handler for {exception_cls} already registered"
                logger.error(error_message)
                raise RuntimeError(error_message)
        _pending_exception_handlers.append((key, handler))
