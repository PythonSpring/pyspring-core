from queue import Queue

from pydantic import BaseModel

class ApplicationEvent(BaseModel): ...
class EventMessageQueue:
    event_message_queue: Queue[ApplicationEvent] = Queue()