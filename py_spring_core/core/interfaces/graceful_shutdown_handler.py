

from abc import ABC, abstractmethod
from enum import Enum, auto
import signal
import threading
from types import FrameType
from typing import Optional

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

    def __init__(self) -> None:
        self._shutdown_event = threading.Event()
        self._shutdown_type: Optional[ShutdownType] = None

        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigint(self, signum: int, frame: Optional[FrameType]) -> None:
        try:
            print("[Signal] SIGINT received")
            self._shutdown_type = ShutdownType.MANUAL
            self._shutdown_event.set()
            self.on_shutdown(ShutdownType.MANUAL)
        except Exception as error:
            self.on_error(error)

    def _handle_sigterm(self, signum: int, frame: Optional[FrameType]) -> None:
        try:
            print("[Signal] SIGTERM received")
            self._shutdown_type = ShutdownType.SIGTERM
            self._shutdown_event.set()
            self.on_shutdown(ShutdownType.SIGTERM)
        except Exception as error:
            self.on_error(error)
    

    def is_shutdown(self) -> bool:
        return self._shutdown_event.is_set()

    def get_type(self) -> Optional[ShutdownType]:
        return self._shutdown_type

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