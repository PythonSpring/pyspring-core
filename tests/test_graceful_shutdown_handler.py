import signal
import threading
import time
from typing import Optional
from unittest.mock import MagicMock, patch
import pytest

from py_spring_core.core.interfaces.graceful_shutdown_handler import (
    GracefulShutdownHandler,
    ShutdownType,
)


class TestGracefulShutdownHandler:
    """Test suite for the graceful shutdown handler functionality."""

    def setup_method(self):
        """Reset any signal handlers before each test."""
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    def test_graceful_shutdown_handler_interface(self):
        """Test that GracefulShutdownHandler enforces abstract methods."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            # Should not be able to instantiate abstract class directly
            GracefulShutdownHandler(timeout_seconds=30.0, timeout_enabled=True) # pyright: ignore[reportAbstractUsage]

    def test_concrete_implementation_creation(self):
        """Test that a concrete implementation can be created successfully."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        # Should be able to create concrete implementation
        handler = TestShutdownHandler(timeout_seconds=5.0, timeout_enabled=True)
        assert handler.get_timeout_seconds() == 5.0
        assert handler.is_timeout_enabled() is True
        assert handler.is_shutdown() is False
        assert handler.get_type() is None

    def test_sigint_handling(self):
        """Test SIGINT signal handling."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        handler = TestShutdownHandler(timeout_seconds=1.0, timeout_enabled=False)
        
        # Simulate SIGINT
        handler._handle_sigint(signal.SIGINT, None)
        
        assert handler.is_shutdown() is True
        assert handler.get_type() == ShutdownType.MANUAL
        assert len(handler.shutdown_calls) == 1
        assert handler.shutdown_calls[0] == ShutdownType.MANUAL

    def test_sigterm_handling(self):
        """Test SIGTERM signal handling."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        handler = TestShutdownHandler(timeout_seconds=1.0, timeout_enabled=False)
        
        # Simulate SIGTERM
        handler._handle_sigterm(signal.SIGTERM, None)
        
        assert handler.is_shutdown() is True
        assert handler.get_type() == ShutdownType.SIGTERM
        assert len(handler.shutdown_calls) == 1
        assert handler.shutdown_calls[0] == ShutdownType.SIGTERM

    def test_duplicate_signal_handling(self):
        """Test that duplicate signals are ignored."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        handler = TestShutdownHandler(timeout_seconds=1.0, timeout_enabled=False)
        
        # First signal
        handler._handle_sigint(signal.SIGINT, None)
        assert len(handler.shutdown_calls) == 1
        
        # Second signal should be ignored
        handler._handle_sigint(signal.SIGINT, None)
        assert len(handler.shutdown_calls) == 1  # Still only one call

    @patch('os._exit')
    def test_timeout_functionality(self, mock_exit):
        """Test shutdown timeout functionality."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        # Test with timeout enabled
        handler = TestShutdownHandler(timeout_seconds=0.1, timeout_enabled=True)
        
        # Trigger shutdown
        handler._handle_sigint(signal.SIGINT, None)
        
        # Wait for timeout to trigger
        time.sleep(0.2)
        
        # Should have called timeout and os._exit
        assert len(handler.timeout_calls) == 1
        mock_exit.assert_called_once_with(0)

    def test_timeout_disabled(self):
        """Test that timeout doesn't trigger when disabled."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        # Test with timeout disabled
        handler = TestShutdownHandler(timeout_seconds=0.1, timeout_enabled=False)
        
        # Trigger shutdown
        handler._handle_sigint(signal.SIGINT, None)
        
        # Wait for potential timeout
        time.sleep(0.2)
        
        # Should not have called timeout
        assert len(handler.timeout_calls) == 0

    def test_complete_shutdown(self):
        """Test shutdown completion functionality."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        handler = TestShutdownHandler(timeout_seconds=10.0, timeout_enabled=True)
        
        # Trigger shutdown
        handler._handle_sigint(signal.SIGINT, None)
        
        # Complete shutdown before timeout
        handler.complete_shutdown()
        
        # Wait to ensure timeout doesn't trigger
        time.sleep(0.1)
        
        # Should not have called timeout since shutdown was completed
        assert len(handler.timeout_calls) == 0

    def test_error_handling_in_signals(self):
        """Test error handling in signal handlers."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                raise RuntimeError("Test error in shutdown")

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        handler = TestShutdownHandler(timeout_seconds=1.0, timeout_enabled=False)
        
        # Signal should trigger error handling
        handler._handle_sigint(signal.SIGINT, None)
        
        assert len(handler.error_calls) == 1
        assert isinstance(handler.error_calls[0], RuntimeError)

    def test_shutdown_elapsed_time(self):
        """Test shutdown elapsed time tracking."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                pass

            def on_timeout(self) -> None:
                pass

            def on_error(self, error: Exception) -> None:
                pass

        # Use a longer timeout to ensure timer starts
        handler = TestShutdownHandler(timeout_seconds=30.0, timeout_enabled=True)
        
        # Before shutdown
        assert handler.get_shutdown_elapsed_time() is None
        
        # Trigger shutdown - this should start the timer and set _shutdown_start_time
        handler._handle_sigint(signal.SIGINT, None)
        
        # Small delay
        time.sleep(0.1)
        
        # Should have elapsed time
        elapsed = handler.get_shutdown_elapsed_time()
        assert elapsed is not None
        assert elapsed >= 0.1

    def test_shutdown_types_enum(self):
        """Test ShutdownType enum values."""
        assert ShutdownType.MANUAL is not None
        assert ShutdownType.SIGTERM is not None
        assert ShutdownType.TIMEOUT is not None
        assert ShutdownType.ERROR is not None
        assert ShutdownType.UNKNOWN is not None
        
        # Ensure all types are unique
        types = [ShutdownType.MANUAL, ShutdownType.SIGTERM, ShutdownType.TIMEOUT, 
                ShutdownType.ERROR, ShutdownType.UNKNOWN]
        assert len(set(types)) == len(types)

    @patch('os._exit')
    def test_timeout_force_exit(self, mock_exit):
        """Test that timeout eventually forces exit."""
        
        class TestShutdownHandler(GracefulShutdownHandler):
            def __init__(self, timeout_seconds: float, timeout_enabled: bool):
                self.shutdown_calls = []
                self.timeout_calls = []
                self.error_calls = []
                super().__init__(timeout_seconds, timeout_enabled)

            def on_shutdown(self, shutdown_type: ShutdownType) -> None:
                self.shutdown_calls.append(shutdown_type)

            def on_timeout(self) -> None:
                self.timeout_calls.append("timeout")

            def on_error(self, error: Exception) -> None:
                self.error_calls.append(error)

        handler = TestShutdownHandler(timeout_seconds=0.1, timeout_enabled=True)
        
        # Trigger shutdown
        handler._handle_sigint(signal.SIGINT, None)
        
        # Wait for timeout to trigger
        time.sleep(0.2)
        
        # Should have called os._exit
        mock_exit.assert_called_once_with(0) 