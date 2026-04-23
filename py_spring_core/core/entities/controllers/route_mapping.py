from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Union

from pydantic import BaseModel


class HTTPMethod(str, Enum):
    """HTTP methods enumeration for route definitions.
    
    This enum defines the supported HTTP methods that can be used
    with route decorators in the PySpring framework.
    """
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RouteRegistration(BaseModel):
    """Model representing a route registration with all FastAPI-compatible parameters.
    
    This class encapsulates all the information needed to register a route,
    including the HTTP method, path, handler function, and various FastAPI
    configuration options.
    
    Attributes:
        class_name (str): Name of the controller class containing the route
        method (HTTPMethod): HTTP method for the route
        path (str): URL path pattern for the route
        func (Callable): The handler function for the route
        response_model (Any, optional): Pydantic model for response serialization
        status_code (int, optional): Default HTTP status code for successful responses
        tags (List[Union[str, Enum]], optional): OpenAPI tags for documentation
        dependencies (List[Any], optional): FastAPI dependencies
        summary (str, optional): Short summary for OpenAPI documentation
        description (str, optional): Detailed description for OpenAPI documentation
        response_description (str): Description of successful response
        responses (Dict[Union[int, str], Dict[str, Any]], optional): Additional response definitions
        deprecated (bool, optional): Whether the endpoint is deprecated
        operation_id (str, optional): Unique operation ID for OpenAPI
        response_model_include (Set[str], optional): Fields to include in response model
        response_model_exclude (Set[str], optional): Fields to exclude from response model
        response_model_by_alias (bool): Whether to use field aliases in response
        response_model_exclude_unset (bool): Whether to exclude unset fields
        response_model_exclude_defaults (bool): Whether to exclude default values
        response_model_exclude_none (bool): Whether to exclude None values
        include_in_schema (bool): Whether to include in OpenAPI schema
        name (str, optional): Custom name for the route
    """
    class_name: str
    method: HTTPMethod
    path: str
    func: Callable
    response_model: Any = None
    status_code: Optional[int] = None
    tags: Optional[List[Union[str, Enum]]] = None
    dependencies: Optional[List[Any]] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    response_description: str = "Successful Response"
    responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None
    deprecated: Optional[bool] = None
    operation_id: Optional[str] = None
    response_model_include: Optional[Set[str]] = None
    response_model_exclude: Optional[Set[str]] = None
    response_model_by_alias: bool = True
    response_model_exclude_unset: bool = False
    response_model_exclude_defaults: bool = False
    response_model_exclude_none: bool = False
    include_in_schema: bool = True
    name: Optional[str] = None

    def __eq__(self, other: Any) -> bool:
        """Check equality based on HTTP method and path.
        
        Two route registrations are considered equal if they have
        the same HTTP method and path, regardless of other attributes.
        
        Args:
            other (Any): Object to compare with
            
        Returns:
            bool: True if equal, False otherwise
        """
        if not isinstance(other, RouteRegistration):
            return False
        return self.method == other.method and self.path == other.path

    def __hash__(self) -> int:
        """Generate hash based on HTTP method and path.
        
        This allows RouteRegistration objects to be used in sets
        and as dictionary keys.
        
        Returns:
            int: Hash value based on method and path
        """
        return hash((self.method, self.path))


class RouteMapping:
    """Registry for storing and managing route registrations by controller class.
    
    This class maintains a mapping of controller class names to their
    associated route registrations, enabling efficient route lookup
    and management within the PySpring framework.
    
    Attributes:
        routes (dict[str, set[RouteRegistration]]): Mapping of class names to route sets
    """
    routes: dict[str, set[RouteRegistration]] = {}

    @classmethod
    def register_route(cls, route_registration: RouteRegistration) -> None:
        """Register a route for a specific controller class.
        
        Adds the given route registration to the routes mapping,
        creating a new set for the class if it doesn't exist.
        
        Args:
            route_registration (RouteRegistration): The route to register
        """
        optional_routes = cls.routes.get(route_registration.class_name, None)
        if optional_routes is None:
            cls.routes[route_registration.class_name] = set()
        cls.routes[route_registration.class_name].add(route_registration)


def _create_route_decorator(method: HTTPMethod):
    """Create a route decorator factory for a specific HTTP method.
    
    This function generates decorator factories that can be used to create
    route decorators with FastAPI-compatible parameters.
    
    Args:
        method (HTTPMethod): The HTTP method for routes created by this decorator
        
    Returns:
        Callable: A decorator factory function that accepts route parameters
    """
    def decorator_factory(
        path: str,
        *,
        response_model: Any = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        dependencies: Optional[List[Any]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[Set[str]] = None,
        response_model_exclude: Optional[Set[str]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: Optional[str] = None,
    ):
        """Create a route decorator with the specified parameters.
        
        Args:
            path (str): URL path pattern for the route
            response_model (Any, optional): Pydantic model for response serialization
            status_code (int, optional): Default HTTP status code
            tags (List[Union[str, Enum]], optional): OpenAPI tags
            dependencies (List[Any], optional): FastAPI dependencies
            summary (str, optional): Route summary for documentation
            description (str, optional): Route description for documentation
            response_description (str): Description of successful response
            responses (Dict[Union[int, str], Dict[str, Any]], optional): Additional responses
            deprecated (bool, optional): Whether the endpoint is deprecated
            operation_id (str, optional): Unique operation ID
            response_model_include (Set[str], optional): Fields to include in response
            response_model_exclude (Set[str], optional): Fields to exclude from response
            response_model_by_alias (bool): Whether to use field aliases
            response_model_exclude_unset (bool): Whether to exclude unset fields
            response_model_exclude_defaults (bool): Whether to exclude defaults
            response_model_exclude_none (bool): Whether to exclude None values
            include_in_schema (bool): Whether to include in OpenAPI schema
            name (str, optional): Custom name for the route
            
        Returns:
            Callable: A decorator function that registers the route
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            """Decorate a function to register it as a route.

            Args:
                func: The handler function to decorate

            Returns:
                The wrapped function
            """
            qualname: str = getattr(func, "__qualname__", "")
            class_name = qualname.split(".")[0]
            route_registration = RouteRegistration(
                class_name=class_name,
                method=method,
                path=path,
                func=func,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                dependencies=dependencies,
                summary=summary or getattr(func, "__name__", ""),
                description=description or func.__doc__,
                response_description=response_description,
                responses=responses,
                deprecated=deprecated,
                operation_id=operation_id,
                response_model_include=response_model_include,
                response_model_exclude=response_model_exclude,
                response_model_by_alias=response_model_by_alias,
                response_model_exclude_unset=response_model_exclude_unset,
                response_model_exclude_defaults=response_model_exclude_defaults,
                response_model_exclude_none=response_model_exclude_none,
                include_in_schema=include_in_schema,
                name=name,
            )
            RouteMapping.register_route(route_registration)

            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    return decorator_factory


# Route decorator factories for different HTTP methods
GetMapping = _create_route_decorator(HTTPMethod.GET)
"""Decorator factory for creating GET route handlers.

Example:
    @GetMapping("/users")
    def get_users(self):
        return {"users": []}
"""

PostMapping = _create_route_decorator(HTTPMethod.POST)
"""Decorator factory for creating POST route handlers.

Example:
    @PostMapping("/users", response_model=UserResponse)
    def create_user(self, user: UserCreate):
        return create_new_user(user)
"""

PutMapping = _create_route_decorator(HTTPMethod.PUT)
"""Decorator factory for creating PUT route handlers.

Example:
    @PutMapping("/users/{user_id}")
    def update_user(self, user_id: int, user: UserUpdate):
        return update_existing_user(user_id, user)
"""

DeleteMapping = _create_route_decorator(HTTPMethod.DELETE)
"""Decorator factory for creating DELETE route handlers.

Example:
    @DeleteMapping("/users/{user_id}")
    def delete_user(self, user_id: int):
        delete_existing_user(user_id)
        return {"message": "User deleted"}
"""

PatchMapping = _create_route_decorator(HTTPMethod.PATCH)
"""Decorator factory for creating PATCH route handlers.

Example:
    @PatchMapping("/users/{user_id}")
    def partial_update_user(self, user_id: int, user: UserPatch):
        return patch_existing_user(user_id, user)
"""
