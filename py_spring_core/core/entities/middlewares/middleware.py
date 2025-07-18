from abc import abstractmethod
from typing import Awaitable, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware



class Middleware(BaseHTTPMiddleware):
    """
    Middleware base class, inherits from FastAPI's BaseHTTPMiddleware
    Simpler to use, only need to implement the process_request method
    """
    
    @abstractmethod
    async def process_request(self, request: Request) -> Response | None:
        """
        Method to process requests
        
        Args:
            request: FastAPI request object
            
        Returns:
            Response | None: If Response is returned, it will be directly returned to the client
                           If None is returned, continue to execute the next middleware or route handler
        """
        pass
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """
        Middleware dispatch method, automatically called by FastAPI
        """
        # First execute custom request processing logic
        response = await self.process_request(request)
        
        # If a response is returned, return it directly
        if response is not None:
            return response
            
        # Otherwise continue to execute the next middleware or route handler
        return await call_next(request)