"""
Edge case tests for the exception handler system.

Covers:
- ExceptionHandler decorator registration
- Duplicate exception handler detection
- Drain behavior (clear after drain)
- ExceptionHandlerRegistry.register
- Handler function preservation (wraps)
- Exception handler for custom exception types
- Exception handler for built-in exception types
"""

import pytest
from unittest.mock import MagicMock

from py_spring_core.exception_handler.decorator import ExceptionHandler
from py_spring_core.exception_handler.exception_handler_registry import (
    ExceptionHandlerRegistry,
    _pending_exception_handlers,
    drain_pending_exception_handlers,
)


@pytest.fixture(autouse=True)
def clean_pending_exception_handlers():
    """Clear pending exception handlers before and after each test."""
    _pending_exception_handlers.clear()
    yield
    _pending_exception_handlers.clear()


class TestExceptionHandlerDecorator:

    def test_registers_handler_for_custom_exception(self):
        class MyError(Exception):
            pass

        @ExceptionHandler(MyError)
        def handle_my_error(error: MyError):
            return {"error": str(error)}

        drained = drain_pending_exception_handlers()
        assert len(drained) == 1
        key, handler_func = drained[0]
        assert key == "MyError"

    def test_registers_handler_for_builtin_exception(self):
        @ExceptionHandler(ValueError)
        def handle_value_error(error: ValueError):
            return {"error": str(error)}

        drained = drain_pending_exception_handlers()
        assert len(drained) == 1
        key, _ = drained[0]
        assert key == "ValueError"

    def test_decorated_function_is_still_callable(self):
        class MyError(Exception):
            pass

        @ExceptionHandler(MyError)
        def handle_error(error: MyError):
            return "handled"

        result = handle_error(MyError("test"))
        assert result == "handled"

    def test_decorated_function_preserves_name(self):
        class MyError(Exception):
            pass

        @ExceptionHandler(MyError)
        def my_special_handler(error: MyError):
            return "handled"

        assert my_special_handler.__name__ == "my_special_handler"


class TestDuplicateExceptionHandlerDetection:

    def test_duplicate_handler_for_same_exception_raises(self):
        class DupError(Exception):
            pass

        @ExceptionHandler(DupError)
        def handler_1(error: DupError):
            return "first"

        with pytest.raises(RuntimeError, match="already registered"):
            @ExceptionHandler(DupError)
            def handler_2(error: DupError):
                return "second"

    def test_different_exceptions_can_have_separate_handlers(self):
        class ErrorA(Exception):
            pass

        class ErrorB(Exception):
            pass

        @ExceptionHandler(ErrorA)
        def handle_a(error: ErrorA):
            return "A"

        @ExceptionHandler(ErrorB)
        def handle_b(error: ErrorB):
            return "B"

        drained = drain_pending_exception_handlers()
        assert len(drained) == 2
        keys = {key for key, _ in drained}
        assert keys == {"ErrorA", "ErrorB"}


class TestDrainPendingExceptionHandlers:

    def test_drain_returns_all_and_clears(self):
        class E1(Exception):
            pass

        @ExceptionHandler(E1)
        def h1(e: E1): ...

        assert len(_pending_exception_handlers) == 1
        drained = drain_pending_exception_handlers()
        assert len(drained) == 1
        assert len(_pending_exception_handlers) == 0

    def test_drain_twice_returns_empty(self):
        class E1(Exception):
            pass

        @ExceptionHandler(E1)
        def h1(e: E1): ...

        drain_pending_exception_handlers()
        assert drain_pending_exception_handlers() == []

    def test_drain_returns_copy(self):
        class E1(Exception):
            pass

        @ExceptionHandler(E1)
        def h1(e: E1): ...

        drained = drain_pending_exception_handlers()
        drained.clear()
        assert len(_pending_exception_handlers) == 0


class TestExceptionHandlerRegistry:

    def test_register_stores_handler(self):
        class CustomError(Exception):
            pass

        handler = MagicMock()
        ExceptionHandlerRegistry.register(CustomError, handler)

        drained = drain_pending_exception_handlers()
        assert len(drained) == 1
        assert drained[0][0] == "CustomError"

    def test_register_duplicate_raises(self):
        class DupError(Exception):
            pass

        handler1 = MagicMock()
        handler2 = MagicMock()

        ExceptionHandlerRegistry.register(DupError, handler1)

        with pytest.raises(RuntimeError, match="already registered"):
            ExceptionHandlerRegistry.register(DupError, handler2)


class TestExceptionHandlerIntegrationWithRegistry:

    def test_handlers_drain_into_application_registry(self):
        from py_spring_core.core.application.application_registry import ApplicationRegistry

        class AppError(Exception):
            pass

        @ExceptionHandler(AppError)
        def handle_app_error(error: AppError):
            return "handled"

        registry = ApplicationRegistry()
        for exc_name, handler_func in drain_pending_exception_handlers():
            registry.exception_handlers[exc_name] = handler_func

        assert "AppError" in registry.exception_handlers
        result = registry.exception_handlers["AppError"](AppError("test"))
        assert result == "handled"


class TestExceptionHandlerWithInheritance:

    def test_handler_registered_by_class_name_not_parent(self):
        class BaseError(Exception):
            pass

        class SpecificError(BaseError):
            pass

        @ExceptionHandler(SpecificError)
        def handle_specific(error: SpecificError):
            return "specific"

        drained = drain_pending_exception_handlers()
        assert len(drained) == 1
        assert drained[0][0] == "SpecificError"
