from abc import ABC, abstractmethod
from typing import Type

from fastapi import FastAPI

from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.interfaces.single_inheritance_required import (
    SingleInheritanceRequired,
)


class MiddlewareRegistry:
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
    
    def __init__(self):
        """
        Initialize the middleware registry.
        """
        self._middlewares: list[Type[Middleware]] = []
    
    def add_middleware(self, middleware_class: Type[Middleware]) -> None:
        """
        Add middleware to the end of the list.
        
        Args:
            middleware_class: The middleware class to add
            
        Raises:
            ValueError: If middleware is already registered
        """
        if middleware_class in self._middlewares:
            raise ValueError(f"Middleware {middleware_class.__name__} is already registered")
        self._middlewares.append(middleware_class)
    
    def add_at_index(self, index: int, middleware_class: Type[Middleware]) -> None:
        """
        Insert middleware at a specific index position.
        
        Args:
            index: The position to insert at (0-based)
            middleware_class: The middleware class to add
            
        Raises:
            ValueError: If middleware is already registered or index is invalid
        """
        if middleware_class in self._middlewares:
            raise ValueError(f"Middleware {middleware_class.__name__} is already registered")
        if index < 0 or index > len(self._middlewares):
            raise ValueError(f"Index {index} is out of range (0-{len(self._middlewares)})")
        self._middlewares.insert(index, middleware_class)
    
    def add_before(self, target_middleware: Type[Middleware], middleware_class: Type[Middleware]) -> None:
        """
        Insert middleware before the target middleware.
        
        Args:
            target_middleware: The middleware to insert before
            middleware_class: The middleware class to add
            
        Raises:
            ValueError: If middleware is already registered or target not found
        """
        if middleware_class in self._middlewares:
            raise ValueError(f"Middleware {middleware_class.__name__} is already registered")
        if target_middleware not in self._middlewares:
            raise ValueError(f"Target middleware {target_middleware.__name__} not found")
        index = self._middlewares.index(target_middleware)
        self._middlewares.insert(index, middleware_class)
    
    def add_after(self, target_middleware: Type[Middleware], middleware_class: Type[Middleware]) -> None:
        """
        Insert middleware after the target middleware.
        
        Args:
            target_middleware: The middleware to insert after
            middleware_class: The middleware class to add
            
        Raises:
            ValueError: If middleware is already registered or target not found
        """
        if middleware_class in self._middlewares:
            raise ValueError(f"Middleware {middleware_class.__name__} is already registered")
        if target_middleware not in self._middlewares:
            raise ValueError(f"Target middleware {target_middleware.__name__} not found")
        index = self._middlewares.index(target_middleware)
        self._middlewares.insert(index + 1, middleware_class)
    
    def remove_middleware(self, middleware_class: Type[Middleware]) -> None:
        """
        Remove a middleware from the registry.
        
        Args:
            middleware_class: The middleware class to remove
            
        Raises:
            ValueError: If middleware is not found
        """
        if middleware_class not in self._middlewares:
            raise ValueError(f"Middleware {middleware_class.__name__} not found")
        self._middlewares.remove(middleware_class)
    
    def clear_middlewares(self) -> None:
        """Remove all middlewares from the registry."""
        self._middlewares.clear()
    
    def has_middleware(self, middleware_class: Type[Middleware]) -> bool:
        """
        Check if a middleware is registered.
        
        Args:
            middleware_class: The middleware class to check
            
        Returns:
            bool: True if middleware is registered, False otherwise
        """
        return middleware_class in self._middlewares
    
    def get_middleware_count(self) -> int:
        """
        Get the number of registered middlewares.
        
        Returns:
            int: Number of registered middlewares
        """
        return len(self._middlewares)
    
    def get_middleware_index(self, middleware_class: Type[Middleware]) -> int:
        """
        Get the index of a middleware in the registry.
        
        Args:
            middleware_class: The middleware class to find
            
        Returns:
            int: The index of the middleware
            
        Raises:
            ValueError: If middleware is not found
        """
        if middleware_class not in self._middlewares:
            raise ValueError(f"Middleware {middleware_class.__name__} not found")
        return self._middlewares.index(middleware_class)
        
    
    
    def get_middleware_classes(self) -> list[Type[Middleware]]:
        """
        Get all registered middleware classes.
        
        Returns:
            List[Type[Middleware]]: List of middleware classes in registration order
        """
        return self._middlewares.copy()
    
    def apply_middlewares(self, app: FastAPI) -> FastAPI:
        """
        Apply middlewares to FastAPI application.
        
        Iterates through all registered middlewares and applies them to the FastAPI
        application instance in the order they were registered.

        Args:
            app: FastAPI application instance

        Returns:
            FastAPI: FastAPI instance with applied middlewares
        """
        for middleware_class in self.get_middleware_classes():
            app.add_middleware(middleware_class)
        return app



class MiddlewareConfiguration(SingleInheritanceRequired["MiddlewareConfiguration"]):
    """
    Middleware configuration for managing middleware registration and execution order.
    """
    
    def configure_middlewares(self, registry: MiddlewareRegistry) -> None:
        """
        Setup middlewares for the registry.
        """
        pass