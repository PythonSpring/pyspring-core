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
    class_name: str
    method: HTTPMethod
    path: str
    func: Callable

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
    def decorator_factory(path: str):
        def decorator(func: Callable):
            class_name = func.__qualname__.split(".")[0]
            route_registration = RouteRegistration(class_name=class_name, method=method, path=path, func=func)
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
