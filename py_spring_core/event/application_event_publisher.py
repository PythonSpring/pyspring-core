from py_spring_core.core.entities.component.component import Component
from py_spring_core.core.interfaces.application_context_required import (
    ApplicationContextRequired,
)
from py_spring_core.event.commons import ApplicationEvent


class ApplicationEventPublisher(Component, ApplicationContextRequired):
    """
    The ApplicationEventPublisher is a component that publishes application events.
    It is responsible for publishing application events to the event message queue.

    The class performs the following key tasks:
    - Publishes application events to the event message queue
    """

    def publish(self, event: ApplicationEvent) -> None:
        app_context = self.get_application_context()
        app_context.registry.event_queue.put(event)
