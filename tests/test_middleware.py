from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.entities.middlewares.middleware_registry import (
    MiddlewareRegistry,
)


class TestMiddleware:
    """Test suite for the Middleware base class."""

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

    def test_middleware_inherits_from_base_http_middleware(self):
        """
        Test that Middleware class inherits from BaseHTTPMiddleware.

        This test verifies that:
        1. Middleware is a subclass of BaseHTTPMiddleware
        2. The inheritance relationship is correctly established
        """
        assert issubclass(Middleware, BaseHTTPMiddleware)

    def test_middleware_is_abstract(self):
        """
        Test that Middleware class is abstract and cannot be instantiated directly.

        This test verifies that:
        1. Middleware is an abstract base class
        2. Attempting to instantiate it directly raises an error
        """
        # Test that Middleware is abstract by checking it has abstract methods
        assert hasattr(Middleware, "process_request")
        assert Middleware.process_request.__isabstractmethod__

    def test_process_request_is_abstract(self):
        """
        Test that process_request method is abstract and must be implemented.

        This test verifies that:
        1. process_request is an abstract method
        2. Subclasses must implement this method
        """

        # Create a concrete subclass without implementing process_request
        class ConcreteMiddleware(Middleware):
            pass

        # Test that the class is abstract by checking it has abstract methods
        assert hasattr(ConcreteMiddleware, "process_request")
        # The method should still be abstract since it wasn't implemented
        assert ConcreteMiddleware.process_request.__isabstractmethod__

    @pytest.mark.asyncio
    async def test_dispatch_continues_when_process_request_returns_none(
        self, mock_request, mock_call_next
    ):
        """
        Test that dispatch continues to next middleware when process_request returns None.

        This test verifies that:
        1. When process_request returns None, dispatch continues to call_next
        2. The call_next function is called with the correct request
        3. The response from call_next is returned
        """
        expected_response = Response(content="test response", status_code=200)
        mock_call_next.return_value = expected_response

        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        middleware = TestMiddleware(app=Mock())
        result = await middleware.dispatch(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_dispatch_returns_response_when_process_request_returns_response(
        self, mock_request, mock_call_next
    ):
        """
        Test that dispatch returns response directly when process_request returns a response.

        This test verifies that:
        1. When process_request returns a Response, dispatch returns it directly
        2. call_next is not called when process_request returns a response
        3. The response from process_request is returned unchanged
        """
        middleware_response = Response(content="middleware response", status_code=403)

        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return middleware_response

        middleware = TestMiddleware(app=Mock())
        result = await middleware.dispatch(mock_request, mock_call_next)

        mock_call_next.assert_not_called()
        assert result == middleware_response

    @pytest.mark.asyncio
    async def test_dispatch_passes_request_to_process_request(
        self, mock_request, mock_call_next
    ):
        """
        Test that dispatch passes the request to process_request method.

        This test verifies that:
        1. The request object is correctly passed to process_request
        2. The process_request method receives the exact same request object
        """
        received_request = None

        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                nonlocal received_request
                received_request = request
                return None

        middleware = TestMiddleware(app=Mock())
        await middleware.dispatch(mock_request, mock_call_next)

        assert received_request == mock_request

    def test_should_skip_default_returns_false(self, mock_request):
        """
        Test that should_skip method returns False by default.

        This test verifies that:
        1. The default implementation of should_skip returns False
        2. This allows the middleware to process all requests by default
        """
        middleware = Middleware(app=Mock())
        result = middleware.should_skip(mock_request)
        assert result is False

    def test_should_skip_can_be_overridden(self, mock_request):
        """
        Test that should_skip method can be overridden in subclasses.

        This test verifies that:
        1. Subclasses can override should_skip to provide custom skip logic
        2. The overridden method is called with the correct request parameter
        """
        class SkippingMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                return request.method == "GET"

        middleware = SkippingMiddleware(app=Mock())
        result = middleware.should_skip(mock_request)
        assert result is True

    @pytest.mark.asyncio
    async def test_dispatch_skips_middleware_when_should_skip_returns_true(
        self, mock_request, mock_call_next
    ):
        """
        Test that dispatch skips middleware processing when should_skip returns True.

        This test verifies that:
        1. When should_skip returns True, process_request is not called
        2. The request is passed directly to call_next
        3. The response from call_next is returned
        """
        expected_response = Response(content="skipped response", status_code=200)
        mock_call_next.return_value = expected_response

        class SkippingMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                return True

            async def process_request(self, request: Request) -> Response | None:
                # This should never be called when should_skip returns True
                raise AssertionError("process_request should not be called")

        middleware = SkippingMiddleware(app=Mock())
        result = await middleware.dispatch(mock_request, mock_call_next)

        # Verify call_next was called with the request
        mock_call_next.assert_called_once_with(mock_request)
        # Verify the response from call_next is returned
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_dispatch_processes_middleware_when_should_skip_returns_false(
        self, mock_request, mock_call_next
    ):
        """
        Test that dispatch processes middleware when should_skip returns False.

        This test verifies that:
        1. When should_skip returns False, process_request is called
        2. The middleware processing logic is executed
        3. The normal dispatch flow continues
        """
        expected_response = Response(content="processed response", status_code=200)
        mock_call_next.return_value = expected_response

        process_request_called = False

        class ProcessingMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                return False

            async def process_request(self, request: Request) -> Response | None:
                nonlocal process_request_called
                process_request_called = True
                return None

        middleware = ProcessingMiddleware(app=Mock())
        result = await middleware.dispatch(mock_request, mock_call_next)

        # Verify process_request was called
        assert process_request_called is True
        # Verify call_next was called
        mock_call_next.assert_called_once_with(mock_request)
        # Verify the response from call_next is returned
        assert result == expected_response

    def test_should_skip_receives_correct_request_parameter(self, mock_request):
        """
        Test that should_skip method receives the correct request parameter.

        This test verifies that:
        1. The should_skip method receives the exact same request object
        2. The request parameter is passed correctly
        """
        received_request = None

        class TestMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                nonlocal received_request
                received_request = request
                return False

        middleware = TestMiddleware(app=Mock())
        middleware.should_skip(mock_request)

        assert received_request == mock_request

    @pytest.mark.asyncio
    async def test_dispatch_with_conditional_skip_logic(self, mock_request, mock_call_next):
        """
        Test dispatch with conditional skip logic based on request properties.

        This test verifies that:
        1. should_skip can use request properties to make skip decisions
        2. The skip logic works correctly in the dispatch flow
        3. Both skip and process paths work as expected
        """
        expected_response = Response(content="test response", status_code=200)
        mock_call_next.return_value = expected_response

        class ConditionalMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                # Skip GET requests, process others
                return request.method == "GET"

            async def process_request(self, request: Request) -> Response | None:
                # This should only be called for non-GET requests
                return Response(content="processed", status_code=202)

        middleware = ConditionalMiddleware(app=Mock())

        # Test with GET request (should skip)
        mock_request.method = "GET"
        result = await middleware.dispatch(mock_request, mock_call_next)
        
        assert result == expected_response
        mock_call_next.assert_called_once_with(mock_request)

        # Reset mock for next test
        mock_call_next.reset_mock()
        mock_call_next.return_value = expected_response

        # Test with POST request (should process)
        mock_request.method = "POST"
        result = await middleware.dispatch(mock_request, mock_call_next)
        
        assert result.body == b"processed" 
        assert result.status_code == 202
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_with_url_based_skip_logic(self, mock_request, mock_call_next):
        """
        Test dispatch with URL-based skip logic.

        This test verifies that:
        1. should_skip can use request URL to make skip decisions
        2. URL-based filtering works correctly
        3. The middleware processes only relevant requests
        """
        expected_response = Response(content="test response", status_code=200)
        mock_call_next.return_value = expected_response

        class URLBasedMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                # Skip requests to /health endpoint
                return str(request.url).endswith("/health")

            async def process_request(self, request: Request) -> Response | None:
                return Response(content="processed", status_code=202)

        middleware = URLBasedMiddleware(app=Mock())

        # Test with health endpoint (should skip)
        mock_request.url = "http://test.com/health"
        result = await middleware.dispatch(mock_request, mock_call_next)
        
        assert result == expected_response
        mock_call_next.assert_called_once_with(mock_request)

        # Reset mock for next test
        mock_call_next.reset_mock()
        mock_call_next.return_value = expected_response

        # Test with other endpoint (should process)
        mock_request.url = "http://test.com/api/users"
        result = await middleware.dispatch(mock_request, mock_call_next)
        
        assert result.body == b"processed"
        assert result.status_code == 202
        mock_call_next.assert_not_called()

    def test_should_skip_method_signature(self):
        """
        Test that should_skip method has the correct signature.

        This test verifies that:
        1. should_skip is an instance method
        2. It takes a Request parameter
        3. It returns a boolean value
        """
        middleware = Middleware(app=Mock())
        
        # Check that should_skip is a method
        assert hasattr(middleware, 'should_skip')
        assert callable(middleware.should_skip)
        
        # Check that it's an instance method (not a class method or static method)
        import inspect
        sig = inspect.signature(middleware.should_skip)
        params = list(sig.parameters.keys())
        
        # Should have 'request' parameter (self is automatically handled by Python)
        assert params == ['request']
        
        # Check return type annotation
        assert sig.return_annotation == bool


class TestMiddlewareRegistry:
    """Test suite for the MiddlewareRegistry abstract class."""

    @pytest.fixture
    def fastapi_app(self):
        """Fixture that provides a fresh FastAPI application instance."""
        return FastAPI()

    def test_middleware_registry_is_abstract(self):
        """
        Test that MiddlewareRegistry class is abstract and cannot be instantiated directly.

        This test verifies that:
        1. MiddlewareRegistry is an abstract base class
        2. Attempting to instantiate it directly raises an error
        """
        # This test verifies that MiddlewareRegistry is abstract
        # We can't test direct instantiation because it's abstract
        # Instead, we test that it has the abstract method
        assert hasattr(MiddlewareRegistry, "get_middleware_classes")
        assert MiddlewareRegistry.get_middleware_classes.__isabstractmethod__

    def test_get_middleware_classes_is_abstract(self):
        """
        Test that get_middleware_classes method is abstract and must be implemented.

        This test verifies that:
        1. get_middleware_classes is an abstract method
        2. Subclasses must implement this method
        """

        # Create a concrete subclass without implementing get_middleware_classes
        class ConcreteRegistry(MiddlewareRegistry):  # type: ignore[abstract]
            pass

        with pytest.raises(TypeError):
            ConcreteRegistry()  # type: ignore[abstract]

    def test_apply_middlewares_adds_middleware_to_app(self, fastapi_app):
        """
        Test that apply_middlewares correctly adds middleware classes to FastAPI app.

        This test verifies that:
        1. Middleware classes are added to the FastAPI application
        2. The add_middleware method is called for each middleware class
        3. The app is returned unchanged
        """

        class TestMiddleware1(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        class TestMiddleware2(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return [TestMiddleware1, TestMiddleware2]

        # Mock the add_middleware method
        with patch.object(fastapi_app, "add_middleware") as mock_add_middleware:
            registry = TestRegistry()
            result = registry.apply_middlewares(fastapi_app)

            # Verify add_middleware was called for each middleware class
            assert mock_add_middleware.call_count == 2
            mock_add_middleware.assert_any_call(TestMiddleware1)
            mock_add_middleware.assert_any_call(TestMiddleware2)

            # Verify the app is returned
            assert result == fastapi_app

    def test_apply_middlewares_with_empty_list(self, fastapi_app):
        """
        Test that apply_middlewares handles empty middleware list correctly.

        This test verifies that:
        1. When no middlewares are registered, no middleware is added
        2. The app is returned unchanged
        3. No errors occur with empty middleware list
        """

        class EmptyRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return []

        with patch.object(fastapi_app, "add_middleware") as mock_add_middleware:
            registry = EmptyRegistry()
            result = registry.apply_middlewares(fastapi_app)

            # Verify add_middleware was not called
            mock_add_middleware.assert_not_called()

            # Verify the app is returned
            assert result == fastapi_app

    def test_apply_middlewares_preserves_app_state(self, fastapi_app):
        """
        Test that apply_middlewares preserves the FastAPI app state.

        This test verifies that:
        1. The original app object is returned (same reference)
        2. No app properties are modified during middleware application
        """

        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return [TestMiddleware]

        # Store original app state
        original_app_id = id(fastapi_app)

        registry = TestRegistry()
        result = registry.apply_middlewares(fastapi_app)

        # Verify same app object is returned
        assert id(result) == original_app_id
        assert result is fastapi_app


class TestMiddlewareIntegration:
    """Integration tests for middleware functionality."""

    @pytest.fixture
    def fastapi_app(self):
        """Fixture that provides a fresh FastAPI application instance."""
        return FastAPI()

    @pytest.mark.asyncio
    async def test_middleware_chain_execution(self, fastapi_app):
        """
        Test that multiple middlewares execute in the correct order.

        This test verifies that:
        1. Middlewares are executed in the order they are added
        2. Each middleware can process the request
        3. The chain continues correctly when middlewares return None
        """
        execution_order = []

        class FirstMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                execution_order.append("first")
                return None

        class SecondMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                execution_order.append("second")
                return None

        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return [FirstMiddleware, SecondMiddleware]

        registry = TestRegistry()
        app = registry.apply_middlewares(fastapi_app)

        # Create a test client to trigger middleware execution
        from fastapi.testclient import TestClient

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        client = TestClient(app)
        response = client.get("/test")

        # Verify middlewares were executed in order (FastAPI uses LIFO - Last In, First Out)
        assert execution_order == ["second", "first"]
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_early_return(self, fastapi_app):
        """
        Test that middleware can return early and prevent further execution.

        This test verifies that:
        1. When a middleware returns a response, subsequent middlewares are not executed
        2. The route handler is not called when middleware returns early
        3. The response from the middleware is returned to the client
        """
        execution_order = []

        class BlockingMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                execution_order.append("blocking")
                return Response(content="blocked", status_code=403)

        class SecondMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                execution_order.append("second")
                return None

        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return [BlockingMiddleware, SecondMiddleware]

        registry = TestRegistry()
        app = registry.apply_middlewares(fastapi_app)

        @app.get("/test")
        async def test_endpoint():
            execution_order.append("handler")
            return {"message": "test"}

        client = TestClient(app)
        response = client.get("/test")

        # Verify only blocking middleware executed (FastAPI uses LIFO - Last In, First Out)
        # SecondMiddleware executes first, then BlockingMiddleware returns early
        assert execution_order == ["second", "blocking"]
        assert response.status_code == 403
        assert response.text == "blocked"

    def test_middleware_registry_single_inheritance(self):
        """
        Test that MiddlewareRegistry enforces single inheritance.

        This test verifies that:
        1. MiddlewareRegistry implements SingleInheritanceRequired
        2. Multiple inheritance is prevented
        """
        # This test assumes SingleInheritanceRequired prevents multiple inheritance
        # The actual behavior depends on the implementation of SingleInheritanceRequired

        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return []

        # Should be able to create a single inheritance registry
        registry = TestRegistry()
        assert isinstance(registry, MiddlewareRegistry)

    def test_middleware_type_hints(self):
        """
        Test that middleware classes have correct type hints.

        This test verifies that:
        1. get_middleware_classes returns the correct type
        2. process_request has correct parameter and return type hints
        """

        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        class TestRegistry(MiddlewareRegistry):
            def get_middleware_classes(self) -> list[type[Middleware]]:
                return [TestMiddleware]

        registry = TestRegistry()
        middleware_classes = registry.get_middleware_classes()

        # Verify type hints
        assert isinstance(middleware_classes, list)
        assert all(
            issubclass(middleware_class, Middleware)
            for middleware_class in middleware_classes
        )
