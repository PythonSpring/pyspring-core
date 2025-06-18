from typing import Optional

from py_spring_core.core.application.context.application_context import ApplicationContext


class ApplicationContextRequired:
    """
    A mixin class that provides access to the ApplicationContext for classes that need it.
    
    This class serves as a base for components that require access to the ApplicationContext.
    It provides class-level methods to set and retrieve the ApplicationContext instance.
    
    Usage:
        class MyComponent(ApplicationContextRequired):
            def some_method(self):
                context = self.get_application_context()
                # Use the context...
    
    Note:
        The ApplicationContext must be set before attempting to retrieve it,
        otherwise a RuntimeError will be raised.
    """
    _app_context: Optional[ApplicationContext] = None


    @classmethod
    def set_application_context(cls, application_context: ApplicationContext) -> None:
        cls._app_context = application_context

    @classmethod
    def get_application_context(cls) -> ApplicationContext:
        if cls._app_context is None:
            raise RuntimeError("ApplicationContext is not set")
        return cls._app_context