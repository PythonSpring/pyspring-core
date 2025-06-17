from queue import Queue

from pydantic import BaseModel

class ApplicationEvent(BaseModel): ...
class EventQueue:
    queue: Queue[ApplicationEvent] = Queue()