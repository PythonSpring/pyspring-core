from threading import Thread
from typing import TypeVar
from queue import Queue

from loguru import logger

from py_spring_core.core.entities.component import Component
from py_spring_core.core.interfaces.application_context_required import ApplicationContextRequired
from py_spring_core.event.application_event_handler_registry import ApplicationEvent, ApplicationEventHandlerRegistry

T = TypeVar("T", bound=ApplicationEvent)

class ApplicationEventPublisher(Component, ApplicationContextRequired):
    def __init__(self):
        self.event_message_queue: Queue[ApplicationEvent] = Queue()
        self.registry = ApplicationEventHandlerRegistry

    def post_construct(self) -> None:
        logger.info("Starting event message handler thread...")
        Thread(target= self._handle_messages).start()

    def publish(self, event: ApplicationEvent) -> None:
        self.event_message_queue.put(event)


    def _handle_messages(self) -> None:
        logger.info("Event message handler thread started...")
        while True:
            message = self.event_message_queue.get()
            for handler in self.registry.get_event_handlers(message.__class__):
                try:
                    handler(message)
                except Exception as error:
                    logger.error(f"Error handling event: {error}")
            
            
            