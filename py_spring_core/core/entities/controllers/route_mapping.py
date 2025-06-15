from enum import Enum
from functools import wraps
from typing import Any, Callable

from pydantic import BaseModel


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RouteRegistration(BaseModel):
    method: HTTPMethod
    path: str
    func: Callable

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, RouteRegistration):
            return False
        return self.method == other.method and self.path == other.path


class RouteMapping:
    routes: dict[str, list[RouteRegistration]] = {}


def _create_route_decorator(method: HTTPMethod):
    def decorator_factory(path: str):
        def decorator(func: Callable):
            class_name = func.__qualname__.split(".")[0]
            optional_routes = RouteMapping.routes.get(class_name, None)
            if optional_routes is None:
                RouteMapping.routes[class_name] = list()
            route_registration = RouteRegistration(method=method, path=path, func=func)
            if route_registration not in RouteMapping.routes[class_name]:
                RouteMapping.routes[class_name].append(route_registration)

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
