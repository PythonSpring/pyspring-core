

from abc import ABC, abstractmethod
from enum import Enum, auto
import os
import signal
import threading
import time
from types import FrameType
from typing import Optional

from loguru import logger

from py_spring_core.core.interfaces.single_inheritance_required import SingleInheritanceRequired

class ShutdownType(Enum):
    MANUAL = auto()      # e.g., Ctrl+C
    SIGTERM = auto()     # e.g., docker stop, systemctl stop
    TIMEOUT = auto()     # e.g., shutdown triggered by time constraint
    ERROR = auto()       # e.g., unrecoverable fault
    UNKNOWN = auto()

    
class GracefulShutdownHandler(SingleInheritanceRequired, ABC):
    """
    A mixin class that provides a method to handle graceful shutdown.
    """

    def __init__(self, timeout_seconds: float, timeout_enabled: bool) -> None:
        self._shutdown_event = threading.Event()
        self._shutdown_type: Optional[ShutdownType] = None
        self._timeout_seconds = timeout_seconds
        self._timeout_enabled = timeout_enabled
        self._timeout_timer: Optional[threading.Timer] = None
        self._shutdown_start_time: Optional[float] = None

        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigint(self, signum: int, frame: Optional[FrameType]) -> None:
        try:
            # Check if shutdown is already in progress to prevent duplicate execution
            if self._shutdown_event.is_set():
                logger.debug("[Signal] SIGINT ignored - shutdown already in progress")
                return
            
            logger.info("[Signal] SIGINT received")
            self._shutdown_type = ShutdownType.MANUAL
            self._shutdown_event.set()
            self._start_shutdown_timer()
            self.on_shutdown(ShutdownType.MANUAL)
        except Exception as error:
            self.on_error(error)

    def _handle_sigterm(self, signum: int, frame: Optional[FrameType]) -> None:
        try:
            # Check if shutdown is already in progress to prevent duplicate execution
            if self._shutdown_event.is_set():
                logger.debug("[Signal] SIGTERM ignored - shutdown already in progress")
                return
            
            logger.info("[Signal] SIGTERM received")
            self._shutdown_type = ShutdownType.SIGTERM
            self._shutdown_event.set()
            self._start_shutdown_timer()
            self.on_shutdown(ShutdownType.SIGTERM)
        except Exception as error:
            self.on_error(error)

    def _start_shutdown_timer(self) -> None:
        """Start the shutdown timeout timer if enabled."""
        if not self._timeout_enabled:
            return
            
        self._shutdown_start_time = time.time()
        logger.info(f"[Shutdown Timer] Starting shutdown timer for {self._timeout_seconds} seconds")
        
        self._timeout_timer = threading.Timer(self._timeout_seconds, self._handle_timeout)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

    def _handle_timeout(self) -> None:
        """Handle shutdown timeout."""
        try:
            if not self._shutdown_event.is_set():
                return  # Shutdown was not initiated, ignore timeout
                
            logger.info(f"[Shutdown Timer] Shutdown timeout reached after {self._timeout_seconds} seconds")
            self._shutdown_type = ShutdownType.TIMEOUT
            self.on_timeout()
        except Exception as error:
            self.on_error(error)
        finally:
            logger.critical(f"[Shutdown Timer] Timer exited with grace period of {self._timeout_seconds} seconds, exiting application")
            os._exit(0)

    def complete_shutdown(self) -> None:
        """Mark shutdown as complete and cancel timeout timer."""
        if self._timeout_timer and self._timeout_timer.is_alive():
            self._timeout_timer.cancel()
            
        if self._shutdown_start_time:
            elapsed = time.time() - self._shutdown_start_time
            logger.success(f"[Shutdown Timer] Shutdown completed successfully in {elapsed:.2f} seconds")

    def is_shutdown(self) -> bool:
        return self._shutdown_event.is_set()

    def get_type(self) -> Optional[ShutdownType]:
        return self._shutdown_type

    def get_timeout_seconds(self) -> float:
        return self._timeout_seconds

    def is_timeout_enabled(self) -> bool:
        return self._timeout_enabled

    def get_shutdown_elapsed_time(self) -> Optional[float]:
        """Get the elapsed time since shutdown started."""
        if self._shutdown_start_time is None:
            return None
        return time.time() - self._shutdown_start_time

    @abstractmethod
    def on_shutdown(self, shutdown_type: ShutdownType) -> None:
        """
        Handle shutdown.
        """
        ...

    @abstractmethod
    def on_timeout(self) -> None:
        """
        Handle timeout.
        """
        ...

    @abstractmethod
    def on_error(self, error: Exception) -> None:
        """
        Handle error.
        """
        ...