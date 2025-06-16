from fastapi import APIRouter, FastAPI
from functools import partial

from py_spring_core.core.entities.controllers.route_mapping import RouteRegistration


class RestController:
    """
    Provides a base class for REST API controllers in the application.

    The `RestController` class provides a set of common functionality for REST API controllers, including:

    - Registering routes and middleware for the controller
    - Providing access to the FastAPI `APIRouter` and `FastAPI` app instances
    - Exposing the controller's configuration, including the URL prefix

    Subclasses of `RestController` should override the `register_routes` and `register_middlewares` methods to add their own routes and middleware to the controller.
    """

    app: FastAPI
    router: APIRouter

    class Config:
        prefix: str = ""

    def _register_routes(self, routes: list[RouteRegistration]) -> None:
        for route in routes:
            bound_method = partial(route.func, self)
            self.router.add_api_route(
                route.path, 
                bound_method, methods=[route.method.value],
                description=route.func.__doc__,
                summary=route.func.__name__
            )

    def register_middlewares(self) -> None: ...

    def get_router(self) -> APIRouter:
        return self.router

    @classmethod
    def get_router_prefix(cls) -> str:
        return cls.Config.prefix

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__
