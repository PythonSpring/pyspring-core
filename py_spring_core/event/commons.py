from queue import Queue

from pydantic import BaseModel


class ApplicationEvent(BaseModel): ...


class _ShutdownSentinel(ApplicationEvent): ...


class EventQueue:
    queue: Queue[ApplicationEvent] = Queue()
