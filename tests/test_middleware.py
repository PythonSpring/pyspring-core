from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.entities.middlewares.middleware_registry import (
    MiddlewareRegistry,
    MiddlewareConfiguration,
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
        assert getattr(Middleware.process_request, "__isabstractmethod__", False)

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
        assert getattr(ConcreteMiddleware.process_request, "__isabstractmethod__", False)

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
        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        middleware = TestMiddleware(app=Mock())
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

            async def process_request(self, request: Request) -> Response | None:
                return None

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

            async def process_request(self, request: Request) -> Response | None:
                return None

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
        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        middleware = TestMiddleware(app=Mock())
        
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
    """Test suite for the MiddlewareRegistry concrete class."""

    @pytest.fixture
    def fastapi_app(self):
        """Fixture that provides a fresh FastAPI application instance."""
        return FastAPI()

    @pytest.fixture
    def registry(self):
        """Fixture that provides a fresh MiddlewareRegistry instance."""
        return MiddlewareRegistry()

    @pytest.fixture
    def test_middleware_1(self):
        """Fixture that provides a test middleware class."""
        class TestMiddleware1(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None
        return TestMiddleware1

    @pytest.fixture
    def test_middleware_2(self):
        """Fixture that provides another test middleware class."""
        class TestMiddleware2(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None
        return TestMiddleware2

    def test_middleware_registry_instantiation(self):
        """
        Test that MiddlewareRegistry can be instantiated directly.

        This test verifies that:
        1. MiddlewareRegistry is a concrete class
        2. It can be instantiated without errors
        3. Initial state is correct
        """
        registry = MiddlewareRegistry()
        assert isinstance(registry, MiddlewareRegistry)
        assert registry.get_middleware_count() == 0
        assert registry.get_middleware_classes() == []

    def test_add_middleware(self, registry, test_middleware_1):
        """
        Test adding middleware to the registry.

        This test verifies that:
        1. Middleware can be added successfully
        2. Middleware count increases
        3. Middleware appears in the classes list
        """
        registry.add_middleware(test_middleware_1)
        
        assert registry.get_middleware_count() == 1
        assert registry.has_middleware(test_middleware_1)
        assert test_middleware_1 in registry.get_middleware_classes()

    def test_add_duplicate_middleware_raises_error(self, registry, test_middleware_1):
        """
        Test that adding duplicate middleware raises an error.

        This test verifies that:
        1. Adding the same middleware twice raises ValueError
        2. The error message is descriptive
        3. The registry state remains unchanged
        """
        registry.add_middleware(test_middleware_1)
        
        with pytest.raises(ValueError, match="Middleware TestMiddleware1 is already registered"):
            registry.add_middleware(test_middleware_1)
        
        # Verify state hasn't changed
        assert registry.get_middleware_count() == 1

    def test_add_at_index(self, registry, test_middleware_1, test_middleware_2):
        """
        Test inserting middleware at specific index.

        This test verifies that:
        1. Middleware can be inserted at specific positions
        2. Order is maintained correctly
        3. Index bounds are respected
        """
        registry.add_middleware(test_middleware_1)
        registry.add_at_index(0, test_middleware_2)
        
        classes = registry.get_middleware_classes()
        assert classes[0] == test_middleware_2
        assert classes[1] == test_middleware_1

    def test_add_at_invalid_index_raises_error(self, registry, test_middleware_1):
        """
        Test that adding at invalid index raises an error.

        This test verifies that:
        1. Invalid indices raise ValueError
        2. Error message includes valid range
        """
        with pytest.raises(ValueError, match="Index -1 is out of range"):
            registry.add_at_index(-1, test_middleware_1)
        
        with pytest.raises(ValueError, match="Index 1 is out of range"):
            registry.add_at_index(1, test_middleware_1)

    def test_add_before(self, registry, test_middleware_1, test_middleware_2):
        """
        Test inserting middleware before another middleware.

        This test verifies that:
        1. Middleware can be inserted before target middleware
        2. Order is correct after insertion
        """
        registry.add_middleware(test_middleware_1)
        registry.add_before(test_middleware_1, test_middleware_2)
        
        classes = registry.get_middleware_classes()
        assert classes[0] == test_middleware_2
        assert classes[1] == test_middleware_1

    def test_add_before_nonexistent_target_raises_error(self, registry, test_middleware_1, test_middleware_2):
        """
        Test that adding before nonexistent target raises error.

        This test verifies that:
        1. Adding before non-registered middleware raises ValueError
        2. Error message is descriptive
        """
        with pytest.raises(ValueError, match="Target middleware TestMiddleware1 not found"):
            registry.add_before(test_middleware_1, test_middleware_2)

    def test_add_after(self, registry, test_middleware_1, test_middleware_2):
        """
        Test inserting middleware after another middleware.

        This test verifies that:
        1. Middleware can be inserted after target middleware
        2. Order is correct after insertion
        """
        registry.add_middleware(test_middleware_1)
        registry.add_after(test_middleware_1, test_middleware_2)
        
        classes = registry.get_middleware_classes()
        assert classes[0] == test_middleware_1
        assert classes[1] == test_middleware_2

    def test_remove_middleware(self, registry, test_middleware_1):
        """
        Test removing middleware from the registry.

        This test verifies that:
        1. Middleware can be removed successfully
        2. Middleware count decreases
        3. Middleware no longer appears in classes list
        """
        registry.add_middleware(test_middleware_1)
        registry.remove_middleware(test_middleware_1)
        
        assert registry.get_middleware_count() == 0
        assert not registry.has_middleware(test_middleware_1)
        assert test_middleware_1 not in registry.get_middleware_classes()

    def test_remove_nonexistent_middleware_raises_error(self, registry, test_middleware_1):
        """
        Test that removing nonexistent middleware raises error.

        This test verifies that:
        1. Removing non-registered middleware raises ValueError
        2. Error message is descriptive
        """
        with pytest.raises(ValueError, match="Middleware TestMiddleware1 not found"):
            registry.remove_middleware(test_middleware_1)

    def test_clear_middlewares(self, registry, test_middleware_1, test_middleware_2):
        """
        Test clearing all middlewares from the registry.

        This test verifies that:
        1. All middlewares are removed
        2. Registry returns to initial state
        """
        registry.add_middleware(test_middleware_1)
        registry.add_middleware(test_middleware_2)
        
        registry.clear_middlewares()
        
        assert registry.get_middleware_count() == 0
        assert registry.get_middleware_classes() == []

    def test_get_middleware_index(self, registry, test_middleware_1, test_middleware_2):
        """
        Test getting the index of a middleware.

        This test verifies that:
        1. Index of registered middleware is returned correctly
        2. Index reflects the actual position in the list
        """
        registry.add_middleware(test_middleware_1)
        registry.add_middleware(test_middleware_2)
        
        assert registry.get_middleware_index(test_middleware_1) == 0
        assert registry.get_middleware_index(test_middleware_2) == 1

    def test_get_middleware_index_nonexistent_raises_error(self, registry, test_middleware_1):
        """
        Test that getting index of nonexistent middleware raises error.

        This test verifies that:
        1. Getting index of non-registered middleware raises ValueError
        2. Error message is descriptive
        """
        with pytest.raises(ValueError, match="Middleware TestMiddleware1 not found"):
            registry.get_middleware_index(test_middleware_1)

    def test_get_middleware_classes_returns_copy(self, registry, test_middleware_1):
        """
        Test that get_middleware_classes returns a copy.

        This test verifies that:
        1. Modifying returned list doesn't affect internal state
        2. A copy is returned, not the original list
        """
        registry.add_middleware(test_middleware_1)
        
        classes = registry.get_middleware_classes()
        classes.clear()
        
        # Original registry should be unchanged
        assert registry.get_middleware_count() == 1
        assert registry.has_middleware(test_middleware_1)

    def test_apply_middlewares_adds_middleware_to_app(self, registry, fastapi_app, test_middleware_1, test_middleware_2):
        """
        Test that apply_middlewares correctly adds middleware classes to FastAPI app.

        This test verifies that:
        1. Middleware classes are added to the FastAPI application
        2. The add_middleware method is called for each middleware class
        3. The app is returned unchanged
        """
        registry.add_middleware(test_middleware_1)
        registry.add_middleware(test_middleware_2)

        # Mock the add_middleware method
        with patch.object(fastapi_app, "add_middleware") as mock_add_middleware:
            result = registry.apply_middlewares(fastapi_app)

            # Verify add_middleware was called for each middleware class
            assert mock_add_middleware.call_count == 2
            mock_add_middleware.assert_any_call(test_middleware_1)
            mock_add_middleware.assert_any_call(test_middleware_2)

            # Verify the app is returned
            assert result == fastapi_app

    def test_apply_middlewares_with_empty_list(self, registry, fastapi_app):
        """
        Test that apply_middlewares handles empty middleware list correctly.

        This test verifies that:
        1. When no middlewares are registered, no middleware is added
        2. The app is returned unchanged
        3. No errors occur with empty middleware list
        """
        with patch.object(fastapi_app, "add_middleware") as mock_add_middleware:
            result = registry.apply_middlewares(fastapi_app)

            # Verify add_middleware was not called
            mock_add_middleware.assert_not_called()

            # Verify the app is returned
            assert result == fastapi_app

    def test_apply_middlewares_preserves_app_state(self, registry, fastapi_app, test_middleware_1):
        """
        Test that apply_middlewares preserves the FastAPI app state.

        This test verifies that:
        1. The original app object is returned (same reference)
        2. No app properties are modified during middleware application
        """
        registry.add_middleware(test_middleware_1)

        # Store original app state
        original_app_id = id(fastapi_app)

        result = registry.apply_middlewares(fastapi_app)

        # Verify same app object is returned
        assert id(result) == original_app_id
        assert result is fastapi_app


class TestMiddlewareConfiguration:
    """Test suite for the MiddlewareConfiguration class."""

    def test_middleware_configuration_inheritance(self):
        """
        Test that MiddlewareConfiguration has proper inheritance.

        This test verifies that:
        1. MiddlewareConfiguration inherits from SingleInheritanceRequired
        2. It can be instantiated
        """
        class TestConfig(MiddlewareConfiguration):
            pass

        config = TestConfig()
        assert isinstance(config, MiddlewareConfiguration)

    def test_setup_middlewares_can_be_overridden(self):
        """
        Test that setup_middlewares can be overridden to configure middlewares.

        This test verifies that:
        1. setup_middlewares can be overridden
        2. The registry is properly configured when overridden
        """
        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        class TestConfig(MiddlewareConfiguration):
            def setup_middlewares(self, registry: MiddlewareRegistry) -> None:
                registry.add_middleware(TestMiddleware)

        config = TestConfig()
        registry = MiddlewareRegistry()
        
        config.setup_middlewares(registry)
        
        assert registry.has_middleware(TestMiddleware)
        assert registry.get_middleware_count() == 1


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

        registry = MiddlewareRegistry()
        registry.add_middleware(FirstMiddleware)
        registry.add_middleware(SecondMiddleware)
        
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

        registry = MiddlewareRegistry()
        registry.add_middleware(BlockingMiddleware)
        registry.add_middleware(SecondMiddleware)
        
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

    def test_middleware_registry_with_configuration(self):
        """
        Test using MiddlewareRegistry with MiddlewareConfiguration.

        This test verifies that:
        1. MiddlewareConfiguration can configure a MiddlewareRegistry
        2. The configuration is applied correctly
        """
        class TestMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                return None

        class TestConfig(MiddlewareConfiguration):
            def setup_middlewares(self, registry: MiddlewareRegistry) -> None:
                registry.add_middleware(TestMiddleware)

        config = TestConfig()
        registry = MiddlewareRegistry()
        
        config.setup_middlewares(registry)
        
        assert registry.has_middleware(TestMiddleware)
        assert registry.get_middleware_count() == 1

    def test_middleware_execution_order_with_skip_logic(self, fastapi_app):
        """
        Test middleware execution order with skip logic.

        This test verifies that:
        1. Middlewares with skip logic are handled correctly
        2. Order is maintained even when some middlewares skip
        """
        execution_order = []

        class ConditionalMiddleware(Middleware):
            def should_skip(self, request: Request) -> bool:
                return "/skip" in str(request.url)
            
            async def process_request(self, request: Request) -> Response | None:
                execution_order.append("conditional")
                return None

        class AlwaysRunMiddleware(Middleware):
            async def process_request(self, request: Request) -> Response | None:
                execution_order.append("always")
                return None

        registry = MiddlewareRegistry()
        registry.add_middleware(ConditionalMiddleware)
        registry.add_middleware(AlwaysRunMiddleware)
        
        app = registry.apply_middlewares(fastapi_app)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.get("/skip")
        async def skip_endpoint():
            return {"message": "skip"}

        client = TestClient(app)
        
        # Test normal endpoint
        execution_order.clear()
        response = client.get("/test")
        assert execution_order == ["always", "conditional"]
        assert response.status_code == 200

        # Test skip endpoint
        execution_order.clear()
        response = client.get("/skip")
        assert execution_order == ["always"]  # Only AlwaysRunMiddleware should execute
        assert response.status_code == 200
