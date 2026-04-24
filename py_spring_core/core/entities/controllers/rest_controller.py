from functools import partial
from typing import Iterable, Optional

from fastapi import APIRouter, FastAPI

from py_spring_core.core.entities.controllers.route_mapping import RouteRegistration
from py_spring_core.core.entities.middlewares.middleware import Middleware


class RestController:
    """
    Provides a base class for REST API controllers in the application.

    The `RestController` class provides a set of common functionality for REST API controllers, including:

    - Registering routes and middleware for the controller
    - Providing access to the FastAPI `APIRouter` and `FastAPI` app instances
    - Exposing the controller's configuration, including the URL prefix

    Subclasses of `RestController` should override the `register_routes` methods to add their own routes and middleware to the controller.
    """

    def __init__(self) -> None:
        self.app: Optional[FastAPI] = None
        self.router: Optional[APIRouter] = None

    class Config:
        prefix: str = ""

    def post_construct(self) -> None: ...

    def _register_decorated_routes(self, routes: Iterable[RouteRegistration]) -> None:
        if self.router is None:
            raise RuntimeError("Router not initialized; cannot register routes")
        for route in routes:
            bound_method = partial(route.func, self)
            self.router.add_api_route(
                path=route.path,
                endpoint=bound_method,
                methods=[route.method.value],
                response_model=route.response_model,
                status_code=route.status_code,
                tags=route.tags,
                dependencies=route.dependencies,
                summary=route.summary,
                description=route.description,
                response_description=route.response_description,
                responses=route.responses,
                deprecated=route.deprecated,
                operation_id=route.operation_id,
                response_model_include=route.response_model_include,
                response_model_exclude=route.response_model_exclude,
                response_model_by_alias=route.response_model_by_alias,
                response_model_exclude_unset=route.response_model_exclude_unset,
                response_model_exclude_defaults=route.response_model_exclude_defaults,
                response_model_exclude_none=route.response_model_exclude_none,
                include_in_schema=route.include_in_schema,
                name=route.name,
            )

    def get_router(self) -> Optional[APIRouter]:
        return self.router

    def must_get_router(self) -> APIRouter:
        """Get the router, raising if not initialized."""
        if self.router is None:
            raise LookupError(
                f"Router not initialized for controller {self.get_name()}"
            )
        return self.router

    @classmethod
    def get_router_prefix(cls) -> str:
        return cls.Config.prefix

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__
