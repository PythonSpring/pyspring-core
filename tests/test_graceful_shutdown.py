import threading
import time
import unittest
from typing import Optional

from py_spring_core.core.interfaces.graceful_shutdown_handler import GracefulShutdownHandler, ShutdownType


class TestService(GracefulShutdownHandler):
    def __init__(self):
        super().__init__()
        self.shutdown_type: Optional[ShutdownType] = None
        self.timeout_called = False
        self.error_message: Optional[str] = None

    def on_shutdown(self, shutdown_type: ShutdownType) -> None:
        self.shutdown_type = shutdown_type

    def on_timeout(self) -> None:
        self.timeout_called = True

    def on_error(self, error: Exception) -> None:
        self.error_message = str(error)


class TestGracefulShutdownHandler(unittest.TestCase):
    def setUp(self):
        self.service = TestService()

    def test_manual_shutdown(self):
        """Test manual shutdown (SIGINT simulation)"""
        def trigger_shutdown():
            time.sleep(0.1)  # Small delay to ensure wait() is called first
            self.service._handle_sigint(2, None)  # Simulate SIGINT

        thread = threading.Thread(target=trigger_shutdown)
        thread.start()

        shutdown_type = self.service.wait(timeout=1.0)
        thread.join()

        self.assertEqual(shutdown_type, ShutdownType.MANUAL)
        self.assertEqual(self.service.shutdown_type, ShutdownType.MANUAL)
        self.assertTrue(self.service.is_shutdown())
        self.assertFalse(self.service.timeout_called)

    def test_sigterm_shutdown(self):
        """Test SIGTERM shutdown"""
        def trigger_shutdown():
            time.sleep(0.1)
            self.service._handle_sigterm(15, None)  # Simulate SIGTERM

        thread = threading.Thread(target=trigger_shutdown)
        thread.start()

        shutdown_type = self.service.wait(timeout=1.0)
        thread.join()

        self.assertEqual(shutdown_type, ShutdownType.SIGTERM)
        self.assertEqual(self.service.shutdown_type, ShutdownType.SIGTERM)
        self.assertTrue(self.service.is_shutdown())
        self.assertFalse(self.service.timeout_called)

    def test_timeout(self):
        """Test timeout scenario"""
        shutdown_type = self.service.wait(timeout=0.1)  # Short timeout

        self.assertEqual(shutdown_type, ShutdownType.TIMEOUT)
        self.assertTrue(self.service.timeout_called)
        self.assertFalse(self.service.is_shutdown())
        self.assertIsNone(self.service.shutdown_type)

    def test_error_shutdown(self):
        """Test error shutdown"""
        error = Exception("Test error")
        self.service.trigger_error_shutdown(error)

        self.assertEqual(self.service.shutdown_type, ShutdownType.ERROR)
        self.assertEqual(self.service.error_message, "Test error")
        self.assertTrue(self.service.is_shutdown())

    def test_get_shutdown_type(self):
        """Test get_type method"""
        self.assertIsNone(self.service.get_type())
        
        self.service._handle_sigint(2, None)
        self.assertEqual(self.service.get_type(), ShutdownType.MANUAL)


if __name__ == '__main__':
    unittest.main() 