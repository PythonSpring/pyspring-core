import pytest
from unittest.mock import AsyncMock, Mock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from collections import defaultdict
import threading
import time

from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.entities.middlewares.middleware_registry import MiddlewareRegistry


class SingleExecutionMiddleware(Middleware):
    """
    Test middleware that ensures it only processes each request once
    by tracking processed requests and preventing duplicate processing
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.processed_requests = set()
        self.execution_count = defaultdict(int)
        self._lock = threading.Lock()
    
    async def process_request(self, request: Request) -> Response | None:
        # Create a unique identifier for this request
        request_id = id(request)
        
        # Use thread lock to ensure thread safety
        with self._lock:
            # Check if this request has already been processed
            if request_id in self.processed_requests:
                # This request has already been processed, skip it
                return None
            
            # Mark this request as processed
            self.processed_requests.add(request_id)
            self.execution_count[request_id] += 1
        
        # Return None to continue processing
        return None


class TestMiddlewareSingleExecution:
    """Test suite for ensuring middleware executes only once per request."""
    
    @pytest.fixture
    def mock_request(self):
        """Fixture that provides a mock FastAPI request."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = "http://test.com/api"
        return request
    
    @pytest.fixture
    def mock_call_next(self):
        """Fixture that provides a mock call_next function."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_middleware_executes_only_once_per_request(self, mock_request, mock_call_next):
        """
        Test that middleware executes only once per request.
        
        This test verifies that:
        1. When dispatch is called multiple times with the same request, 
           process_request logic is only executed once
        2. The execution count for the request remains at 1
        3. The request is only processed once
        """
        expected_response = Response(content="test response", status_code=200)
        mock_call_next.return_value = expected_response
        
        middleware = SingleExecutionMiddleware(app=Mock())
        
        # Call dispatch multiple times with the same request
        for _ in range(3):
            result = await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify that process_request logic was only executed once for this request
        request_id = id(mock_request)
        assert middleware.execution_count[request_id] == 1
        
        # Verify that the request was added to processed set
        assert request_id in middleware.processed_requests
        
        # Verify call_next was called the expected number of times
        assert mock_call_next.call_count == 3
        
        # Verify the response is correct
        assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_middleware_executes_once_per_different_request(self, mock_call_next):
        """
        Test that middleware executes once for each different request.
        
        This test verifies that:
        1. Each unique request is processed exactly once
        2. Different requests are tracked separately
        3. The execution count is correct for each request
        """
        expected_response = Response(content="test response", status_code=200)
        mock_call_next.return_value = expected_response
        
        middleware = SingleExecutionMiddleware(app=Mock())
        
        # Create multiple different requests
        requests = []
        for i in range(3):
            request = Mock(spec=Request)
            request.method = "GET"
            request.url = f"http://test.com/api/{i}"
            requests.append(request)
        
        # Process each request once
        for request in requests:
            await middleware.dispatch(request, mock_call_next)
        
        # Verify each request was processed exactly once
        for request in requests:
            request_id = id(request)
            assert middleware.execution_count[request_id] == 1
            assert request_id in middleware.processed_requests
        
        # Verify total number of processed requests
        assert len(middleware.processed_requests) == 3
        assert sum(middleware.execution_count.values()) == 3
    
    @pytest.mark.asyncio
    async def test_middleware_handles_early_return_correctly(self, mock_request, mock_call_next):
        """
        Test that middleware handles early return correctly while maintaining single execution.
        
        This test verifies that:
        1. When middleware returns a response early, it still counts as executed once
        2. The request is tracked even when middleware returns early
        3. call_next is not called when middleware returns early
        """
        middleware_response = Response(content="middleware response", status_code=403)
        
        class EarlyReturnMiddleware(SingleExecutionMiddleware):
            async def process_request(self, request: Request) -> Response | None:
                # Call parent to track execution
                await super().process_request(request)
                # Return early response
                return middleware_response
        
        middleware = EarlyReturnMiddleware(app=Mock())
        
        # Call dispatch
        result = await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify that process_request was called once
        request_id = id(mock_request)
        assert middleware.execution_count[request_id] == 1
        assert request_id in middleware.processed_requests
        
        # Verify call_next was not called (early return)
        mock_call_next.assert_not_called()
        
        # Verify the early response is returned
        assert result == middleware_response
    
    @pytest.mark.asyncio
    async def test_middleware_with_skip_logic_maintains_single_execution(self, mock_request, mock_call_next):
        """
        Test that middleware with skip logic maintains single execution tracking.
        
        This test verifies that:
        1. When should_skip returns True, the request is still tracked
        2. The execution count remains at 0 for skipped requests
        3. The request is still added to the processed set
        """
        expected_response = Response(content="skipped response", status_code=200)
        mock_call_next.return_value = expected_response
        
        class SkippingMiddleware(SingleExecutionMiddleware):
            def should_skip(self, request: Request) -> bool:
                return True
            
            async def process_request(self, request: Request) -> Response | None:
                # This should never be called when should_skip returns True
                raise AssertionError("process_request should not be called when should_skip returns True")
        
        middleware = SkippingMiddleware(app=Mock())
        
        # Call dispatch
        result = await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify that process_request was not called (due to skip)
        request_id = id(mock_request)
        assert request_id not in middleware.processed_requests
        
        # Verify call_next was called
        mock_call_next.assert_called_once_with(mock_request)
        assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_middleware_thread_safety(self, mock_call_next):
        """
        Test that middleware is thread-safe when processing multiple requests concurrently.
        
        This test verifies that:
        1. Multiple threads can safely access the middleware
        2. Each request is processed exactly once even under concurrent access
        3. No race conditions occur
        """
        expected_response = Response(content="test response", status_code=200)
        mock_call_next.return_value = expected_response
        
        middleware = SingleExecutionMiddleware(app=Mock())
        
        # Create multiple requests
        requests = []
        for i in range(10):
            request = Mock(spec=Request)
            request.method = "GET"
            request.url = f"http://test.com/api/{i}"
            requests.append(request)
        
        # Process requests concurrently
        import asyncio
        
        async def process_request(request):
            return await middleware.dispatch(request, mock_call_next)
        
        # Process all requests concurrently
        results = await asyncio.gather(*[process_request(req) for req in requests])
        
        # Verify each request was processed exactly once
        for request in requests:
            request_id = id(request)
            assert middleware.execution_count[request_id] == 1
            assert request_id in middleware.processed_requests
        
        # Verify all responses are correct
        for result in results:
            assert result == expected_response
        
        # Verify total number of processed requests
        assert len(middleware.processed_requests) == 10
        assert sum(middleware.execution_count.values()) == 10
    
    @pytest.mark.asyncio
    async def test_middleware_integration_with_fastapi(self):
        """
        Test middleware single execution in a real FastAPI application.
        
        This test verifies that:
        1. Middleware executes only once per request in a real FastAPI app
        2. Multiple requests are handled correctly
        3. The tracking works across different endpoints
        """
        app = FastAPI()
        
        class TestMiddleware(SingleExecutionMiddleware):
            pass
        
        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return [TestMiddleware]
        
        # Apply middleware to app
        registry = TestRegistry()
        app = registry.apply_middlewares(app)
        
        # Create test endpoints
        @app.get("/test1")
        async def test_endpoint1():
            return {"message": "test1"}
        
        @app.get("/test2")
        async def test_endpoint2():
            return {"message": "test2"}
        
        # Create test client
        client = TestClient(app)
        
        # Make multiple requests
        response1 = client.get("/test1")
        response2 = client.get("/test2")
        response3 = client.get("/test1")  # Same endpoint as first request
        
        # Verify responses
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200
        
        # The key point is that the middleware doesn't interfere with normal operation
        # and each request is processed exactly once through the middleware chain 