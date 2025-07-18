from abc import ABC, abstractmethod
from typing import Type

from fastapi import FastAPI

from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.interfaces.single_inheritance_required import (
    SingleInheritanceRequired,
)


class MiddlewareRegistry(SingleInheritanceRequired["MiddlewareRegistry"], ABC):
    """
    Middleware registry for managing all middlewares

    This registry pattern eliminates the need for manual middleware registration.
    The framework automatically handles middleware registration and execution order.

    Multiple middleware execution order:
    When multiple middlewares are registered through this registry, they are automatically
    applied to the FastAPI application in the order they are returned by get_middleware_classes().
    Each middleware wraps the application, forming a stack. The last middleware added is the outermost,
    and the first is the innermost.

    On the request path, the outermost middleware runs first.
    On the response path, it runs last.

    For example, if get_middleware_classes() returns [MiddlewareA, MiddlewareB]
    This results in the following execution order:
    Request: MiddlewareB → MiddlewareA → route
    Response: route → MiddlewareA → MiddlewareB
    This stacking behavior ensures that middlewares are executed in a predictable and controllable order.
    """

    @abstractmethod
    def get_middleware_classes(self) -> list[Type[Middleware]]:
        """
        Get all registered middleware classes

        Returns:
            List[Type[Middleware]]: List of middleware classes
        """
        pass

    def apply_middlewares(self, app: FastAPI) -> FastAPI:
        """
        Apply middlewares to FastAPI application

        Args:
            app: FastAPI application instance

        Returns:
            FastAPI: FastAPI instance with applied middlewares
        """
        for middleware_class in self.get_middleware_classes():
            app.add_middleware(middleware_class)
        return app
