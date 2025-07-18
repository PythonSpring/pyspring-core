

from abc import ABC, abstractmethod
from typing import Type
from fastapi import FastAPI
from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.interfaces.single_inheritance_required import SingleInheritanceRequired




class MiddlewareRegistry(SingleInheritanceRequired["MiddlewareRegistry"], ABC):
    """
    Middleware registry for managing all middlewares
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