from typing import TypeVar


from py_spring_core.core.entities.component import Component
from py_spring_core.event.application_event_handler_registry import ApplicationEvent, ApplicationEventHandlerRegistry
from py_spring_core.event.commons import EventQueue

T = TypeVar("T", bound=ApplicationEvent)




class ApplicationEventPublisher(Component):
    """
    The ApplicationEventPublisher is a component that publishes application events.
    It is responsible for publishing application events to the event message queue.

    The class performs the following key tasks:
    - Publishes application events to the event message queue
    """
    def __init__(self):
        self.event_message_queue = EventQueue.queue
    
    def publish(self, event: ApplicationEvent) -> None:
        self.event_message_queue.put(event)


    
            
            