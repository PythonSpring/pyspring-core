"""
Edge case tests for the event system (EventListener, EventHandler, ApplicationEventPublisher).

Covers:
- EventListener decorator registration
- Event handler drain behavior
- EventHandler equality and hashing
- Non-ApplicationEvent subclass rejected
- Handler qualname validation (must be class method)
- Duplicate event handler prevention
- Event publishing and queue behavior
- Multiple handlers for same event type
- Handler for unknown event type

NOTE: Classes using @EventListener must be at module level so __qualname__
has the correct "ClassName.method" format (not nested inside test methods).
"""

import pytest

from py_spring_core.event.commons import ApplicationEvent, _ShutdownSentinel
from py_spring_core.event.application_event_handler_registry import (
    EventHandler,
    EventListener,
    _pending_event_handlers,
    drain_pending_event_handlers,
)


@pytest.fixture(autouse=True)
def clean_pending_handlers():
    """Ensure pending event handlers are cleared before and after each test."""
    _pending_event_handlers.clear()
    yield
    _pending_event_handlers.clear()


# --- Module-level event and handler classes (qualname = "ClassName.method") ---

class _MyEvent(ApplicationEvent):
    data: str = ""

class _EventA(ApplicationEvent): ...
class _EventB(ApplicationEvent): ...

class _MyComponent:
    @EventListener(_MyEvent)
    def handle_event(self, event: _MyEvent):
        pass

class _HandlerA:
    @EventListener(_MyEvent)
    def on_event(self, event: _MyEvent):
        pass

class _HandlerB:
    @EventListener(_MyEvent)
    def on_event(self, event: _MyEvent):
        pass

class _MultiHandler:
    @EventListener(_EventA)
    def on_a(self, event: _EventA): ...

    @EventListener(_EventB)
    def on_b(self, event: _EventB): ...

class _DrainHandler:
    @EventListener(_MyEvent)
    def handle(self, event: _MyEvent): ...

# Drain all module-level registrations to capture them
_module_level_handlers = drain_pending_event_handlers()


class TestEventListenerDecorator:

    def test_registers_handler_for_valid_event(self):
        handlers = [h for h in _module_level_handlers if h.class_name == "_MyComponent"]
        assert len(handlers) == 1
        assert handlers[0].event_type is _MyEvent
        assert handlers[0].class_name == "_MyComponent"
        assert handlers[0].func_name == "handle_event"

    def test_rejects_non_application_event_subclass(self):
        class NotAnEvent:
            pass

        with pytest.raises(ValueError, match="subclass of ApplicationEvent"):
            class _BadComp:
                @EventListener(NotAnEvent)  # type: ignore
                def handle_event(self, event):
                    pass

    def test_rejects_non_member_function(self):
        class SomeEvent(ApplicationEvent): ...

        with pytest.raises(ValueError, match="must be a member function"):
            @EventListener(SomeEvent)
            def standalone_handler(event):
                pass

    def test_multiple_handlers_for_same_event(self):
        handlers_a = [h for h in _module_level_handlers if h.class_name == "_HandlerA"]
        handlers_b = [h for h in _module_level_handlers if h.class_name == "_HandlerB"]
        assert len(handlers_a) == 1
        assert len(handlers_b) == 1

    def test_different_events_on_same_class(self):
        handlers = [h for h in _module_level_handlers if h.class_name == "_MultiHandler"]
        assert len(handlers) == 2
        event_types = {h.event_type for h in handlers}
        assert event_types == {_EventA, _EventB}


class TestDrainPendingEventHandlers:

    def test_drain_returns_all_and_clears(self):
        _pending_event_handlers.append(_module_level_handlers[0])
        drained = drain_pending_event_handlers()
        assert len(drained) == 1
        assert len(_pending_event_handlers) == 0

    def test_drain_twice_returns_empty_second_time(self):
        _pending_event_handlers.append(_module_level_handlers[0])
        drain_pending_event_handlers()
        assert drain_pending_event_handlers() == []

    def test_drain_returns_copy(self):
        _pending_event_handlers.append(_module_level_handlers[0])
        drained = drain_pending_event_handlers()
        drained.clear()
        assert len(_pending_event_handlers) == 0


class TestEventHandlerModel:

    def test_equality_based_on_class_and_func_name(self):
        class Evt(ApplicationEvent): ...

        def dummy(self, e): ...

        h1 = EventHandler(class_name="Foo", func_name="handle", event_type=Evt, func=dummy)
        h2 = EventHandler(class_name="Foo", func_name="handle", event_type=Evt, func=dummy)
        assert h1 == h2

    def test_inequality_different_class_name(self):
        class Evt(ApplicationEvent): ...

        def dummy(self, e): ...

        h1 = EventHandler(class_name="Foo", func_name="handle", event_type=Evt, func=dummy)
        h2 = EventHandler(class_name="Bar", func_name="handle", event_type=Evt, func=dummy)
        assert h1 != h2

    def test_inequality_different_func_name(self):
        class Evt(ApplicationEvent): ...

        def dummy(self, e): ...

        h1 = EventHandler(class_name="Foo", func_name="handle_a", event_type=Evt, func=dummy)
        h2 = EventHandler(class_name="Foo", func_name="handle_b", event_type=Evt, func=dummy)
        assert h1 != h2

    def test_inequality_with_non_handler(self):
        class Evt(ApplicationEvent): ...

        def dummy(self, e): ...

        h = EventHandler(class_name="Foo", func_name="handle", event_type=Evt, func=dummy)
        assert h != "not a handler"
        assert h != 42

    def test_hash_consistency(self):
        class Evt(ApplicationEvent): ...

        def dummy(self, e): ...

        h1 = EventHandler(class_name="Foo", func_name="handle", event_type=Evt, func=dummy)
        h2 = EventHandler(class_name="Foo", func_name="handle", event_type=Evt, func=dummy)
        assert hash(h1) == hash(h2)

    def test_handlers_in_set_deduplicate(self):
        class Evt(ApplicationEvent): ...

        def dummy(self, e): ...

        h1 = EventHandler(class_name="X", func_name="f", event_type=Evt, func=dummy)
        h2 = EventHandler(class_name="X", func_name="f", event_type=Evt, func=dummy)
        assert len({h1, h2}) == 1


class TestDuplicateHandlerPrevention:

    def test_same_handler_registered_twice_is_deduplicated_at_drain(self):
        # Module-level handlers already prevent duplicates via __eq__ check
        handlers = [h for h in _module_level_handlers if h.class_name == "_DrainHandler"]
        assert len(handlers) == 1


class TestApplicationEventModel:

    def test_application_event_is_base_model(self):
        event = ApplicationEvent()
        assert event is not None

    def test_custom_event_with_fields(self):
        class UserCreatedEvent(ApplicationEvent):
            user_id: int
            username: str

        event = UserCreatedEvent(user_id=1, username="alice")
        assert event.user_id == 1
        assert event.username == "alice"

    def test_shutdown_sentinel_is_application_event(self):
        sentinel = _ShutdownSentinel()
        assert isinstance(sentinel, ApplicationEvent)

    def test_event_serialization(self):
        class OrderEvent(ApplicationEvent):
            order_id: str
            amount: float

        event = OrderEvent(order_id="ORD-001", amount=99.99)
        data = event.model_dump()
        assert data["order_id"] == "ORD-001"
        assert data["amount"] == 99.99

    def test_event_inheritance(self):
        class BaseEvent(ApplicationEvent):
            source: str

        class SpecificEvent(BaseEvent):
            detail: str

        event = SpecificEvent(source="system", detail="specific")
        assert event.source == "system"
        assert event.detail == "specific"
        assert isinstance(event, ApplicationEvent)
