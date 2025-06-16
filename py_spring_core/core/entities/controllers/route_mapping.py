from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Union

from pydantic import BaseModel


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RouteRegistration(BaseModel):
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
        if not isinstance(other, RouteRegistration):
            return False
        return self.method == other.method and self.path == other.path

    def __hash__(self) -> int:
        return hash((self.method, self.path))


class RouteMapping:
    routes: dict[str, set[RouteRegistration]] = {}

    @classmethod
    def register_route(cls, route_registration: RouteRegistration) -> None:
        optional_routes = cls.routes.get(route_registration.class_name, None)
        if optional_routes is None:
            cls.routes[route_registration.class_name] = set()
        cls.routes[route_registration.class_name].add(route_registration)


def _create_route_decorator(method: HTTPMethod):
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
        def decorator(func: Callable):
            class_name = func.__qualname__.split(".")[0]
            route_registration = RouteRegistration(
                class_name=class_name,
                method=method,
                path=path,
                func=func,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                dependencies=dependencies,
                summary=summary or func.__name__,
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


GetMapping = _create_route_decorator(HTTPMethod.GET)
PostMapping = _create_route_decorator(HTTPMethod.POST)
PutMapping = _create_route_decorator(HTTPMethod.PUT)
DeleteMapping = _create_route_decorator(HTTPMethod.DELETE)
PatchMapping = _create_route_decorator(HTTPMethod.PATCH)
