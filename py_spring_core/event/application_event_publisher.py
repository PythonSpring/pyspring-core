from typing import TypeVar


from py_spring_core.core.entities.component import Component
from py_spring_core.event.application_event_handler_registry import ApplicationEvent, ApplicationEventHandlerRegistry
from py_spring_core.event.commons import EventMessageQueue

T = TypeVar("T", bound=ApplicationEvent)




class ApplicationEventPublisher(Component):
    def __init__(self):
        self.event_message_queue = EventMessageQueue.event_message_queue
        self.registry = ApplicationEventHandlerRegistry

    
    def publish(self, event: ApplicationEvent) -> None:
        self.event_message_queue.put(event)


    
            
            