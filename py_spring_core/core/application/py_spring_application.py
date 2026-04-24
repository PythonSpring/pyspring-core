import logging
import os
from typing import Any, Callable, Iterable, Optional, Type, TypeVar

import uvicorn
from fastapi import APIRouter, FastAPI
from loguru import logger

from py_spring_core.commons.class_scanner import ClassScanner
from py_spring_core.commons.config_file_template_generator.config_file_template_generator import (
    ConfigFileTemplateGenerator,
)
from py_spring_core.commons.file_path_scanner import FilePathScanner
from py_spring_core.commons.type_checking_service import TypeCheckingService
from py_spring_core.core.application.application_config import (
    ApplicationConfigRepository,
)
from py_spring_core.core.application.application_registry import ApplicationRegistry
from py_spring_core.core.application.commons import AppEntities
from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
)
from py_spring_core.core.application.context.application_context_config import (
    ApplicationContextConfig,
)
from py_spring_core.core.application.loguru_config import LogFormat
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component, ComponentLifeCycle
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.entity_provider.entity_provider import EntityProvider
from py_spring_core.core.entities.middlewares.middleware import Middleware
from py_spring_core.core.entities.middlewares.middleware_registry import (
    MiddlewareConfiguration,
    MiddlewareRegistry,
)
from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.interfaces.application_context_required import (
    ApplicationContextRequired,
)
from py_spring_core.core.interfaces.graceful_shutdown_handler import GracefulShutdownHandler
from py_spring_core.core.interfaces.single_inheritance_required import SingleInheritanceRequired
from py_spring_core.event.application_event_handler_registry import (
    ApplicationEventHandlerRegistry,
)
from py_spring_core.event.application_event_publisher import ApplicationEventPublisher

import py_spring_core.core.utils as framework_utils


SingleInheritanceRequiredT = TypeVar("SingleInheritanceRequiredT", bound=SingleInheritanceRequired)
class PySpringApplication:
    """
    The PySpringApplication class is the main entry point for the PySpring application.
    It is responsible for initializing the application, registering application entities, and running the FastAPI server.

    The class performs the following key tasks:
    - Initializes the application from a configuration file path
    - Registers application entities (components, controllers, bean collections, properties) with the application context
    - Initializes the application context and injects dependencies
    - Handles the lifecycle of singleton components
    - Registers the controllers with the FastAPI application
    - Enables any configured framework modules
    - Runs the FastAPI server if the server configuration is enabled

    The PySpringApplication class provides a high-level interface for bootstrapping and running the PySpring application.
    """

    PY_FILE_EXTENSION = ".py"

    def __init__(
        self, app_config_path: str, entity_providers: Iterable[EntityProvider] = ()
    ) -> None:
        self.entity_providers = entity_providers
        logger.debug(
            f"[APP INIT] Initialize the app from config path: {app_config_path}"
        )
        runtime_dir = os.path.dirname(app_config_path)
        self._template_generator = ConfigFileTemplateGenerator(runtime_dir)
        self._template_generator.generate_app_config_file_template_if_not_exists()
        self._template_generator.generate_app_properties_file_template_if_not_exists()

        self._model_classes: set[type[object]] = set()
        self.app_config_repo = ApplicationConfigRepository(app_config_path)
        self.app_config = self.app_config_repo.get_config()
        self.file_path_scanner = FilePathScanner(
            target_dirs=[self.app_config.app_src_target_dir],
            target_extensions=[self.PY_FILE_EXTENSION],
        )
        self.target_dir_absolute_file_paths = (
            self.file_path_scanner.scan_file_paths_under_directory()
        )
        self.app_class_scanner = ClassScanner(self.target_dir_absolute_file_paths)
        self.app_context_config = ApplicationContextConfig(
            properties_path=self.app_config.properties_file_path
        )
        self.fastapi = FastAPI()
        self.registry = ApplicationRegistry()
        self.app_context = ApplicationContext(
            config=self.app_context_config,
            server=self.fastapi,
            registry=self.registry,
        )

        self.classes_with_handlers: dict[
            Type[AppEntities], Callable[[Type[Any]], None]
        ] = {
            Component: self._handle_register_component,
            RestController: self._handle_register_rest_controller,
            BeanCollection: self._handle_register_bean_collection,
            Properties: self._handle_register_properties,
        }
        self.type_checking_service = TypeCheckingService(
            self.app_config.app_src_target_dir
        )
        self.shutdown_handler: Optional[GracefulShutdownHandler] = None

    def _configure_logging(self):
        """Applies the logging configuration using Loguru."""
        config = self.app_config.loguru_config
        if not config.log_file_path:
            return

        # Use the format field from config which contains the actual format string
        logger.add(
            config.log_file_path,
            level=config.log_level,
            rotation=config.log_rotation,
            retention=config.log_retention,
            serialize=config.format == LogFormat.JSON,
        )
        self._configure_uvicorn_logging()

    def _get_system_managed_classes(self) -> Iterable[Type[Component]]:
        return [ApplicationEventPublisher, ApplicationEventHandlerRegistry]

    def _scan_classes_for_project(self) -> Iterable[Type[object]]:
        self.app_class_scanner.scan_classes_for_file_paths(
            self.app_config.exclude_file_patterns
        )
        return self.app_class_scanner.get_classes()

    def _register_app_entities(self, classes: Iterable[Type[object]]) -> None:
        for _cls in classes:
            for _target_cls, handler in self.classes_with_handlers.items():
                if not issubclass(_cls, _target_cls):
                    continue
                handler(_cls)

    def _get_all_entities_from_entity_providers(
        self, entity_providers: Iterable[EntityProvider]
    ) -> Iterable[Type[AppEntities]]:
        entities: list[Type[AppEntities]] = []
        for provider in entity_providers:
            entities.extend(provider.get_entities())

        return entities

    def _handle_register_component(self, _cls: Type[Component]) -> None:
        self.app_context.register_component(_cls)

    def _handle_register_rest_controller(self, _cls: Type[RestController]) -> None:
        logger.debug(
            f"[REST CONTROLLER INIT] Register router for controller: {_cls.__name__}"
        )
        self.app_context.register_controller(_cls)

    def _handle_register_bean_collection(self, _cls: Type[BeanCollection]) -> None:
        logger.debug(
            f"[BEAN COLLECTION INIT] Register bean collection: {_cls.__name__}"
        )
        self.app_context.register_bean_collection(_cls)

    def _handle_register_properties(self, _cls: Type[Properties]) -> None:
        logger.debug(f"[PROPERTIES INIT] Register properties: {_cls.__name__}")
        self.app_context.register_properties(_cls)

    def _init_providers(self, providers: Iterable[EntityProvider]) -> None:
        for provider in providers:
            provider.provider_init()

    def _inject_application_context_to_context_required(
        self, classes: Iterable[Type[object]]
    ) -> None:
        for cls in classes:
            if not issubclass(cls, ApplicationContextRequired):
                continue
            cls.set_application_context(self.app_context)

    def _prepare_injected_classes(self) -> Iterable[Type[object]]:
        scanned_classes = self._scan_classes_for_project()
        system_managed_classes = self._get_system_managed_classes()
        provider_entities = self._get_all_entities_from_entity_providers(
            self.entity_providers
        )
        provider_classes = [provider.__class__ for provider in self.entity_providers]
        # providers typically requires app context, so add to classess to inject
        classes_to_inject = [
            *scanned_classes,
            *system_managed_classes,
            *provider_entities,
            *provider_classes,
        ]
        return classes_to_inject

    def _drain_pending_registrations(self) -> None:
        """Move import-time decorator registrations into this app's registry."""
        from py_spring_core.core.entities.controllers.route_mapping import (
            drain_pending_routes,
        )
        from py_spring_core.event.application_event_handler_registry import (
            drain_pending_event_handlers,
        )
        from py_spring_core.exception_handler.exception_handler_registry import (
            drain_pending_exception_handlers,
        )

        for route in drain_pending_routes():
            self.registry.routes.setdefault(route.class_name, set()).add(route)

        for handler in drain_pending_event_handlers():
            event_name = handler.event_type.__name__
            self.registry.event_handlers.setdefault(event_name, [])
            if handler not in self.registry.event_handlers[event_name]:
                self.registry.event_handlers[event_name].append(handler)

        for exc_name, handler_func in drain_pending_exception_handlers():
            self.registry.exception_handlers[exc_name] = handler_func

    def _init_app(self) -> None:
        self._drain_pending_registrations()
        classes_to_inject = self._prepare_injected_classes()
        self._inject_application_context_to_context_required(classes_to_inject)
        self._register_app_entities(classes_to_inject)
        self.app_context.load_properties()
        self.app_context.init_ioc_container()
        self.app_context.inject_dependencies_for_app_entities()
        self.app_context.set_all_file_paths(self.target_dir_absolute_file_paths)
        self.app_context.validate_entity_providers()
        # after injecting all deps, lifecycle (init) can be called
        self._init_providers(self.entity_providers)
        self._handle_singleton_components_life_cycle(ComponentLifeCycle.Init)

    def _handle_singleton_components_life_cycle(
        self, life_cycle: ComponentLifeCycle
    ) -> None:
        components = self.app_context.get_singleton_component_instances()
        for component in components:
            match life_cycle:
                case ComponentLifeCycle.Init:
                    component.finish_initialization_cycle()
                case ComponentLifeCycle.Destruction:
                    component.finish_destruction_cycle()

    def _init_controllers(self) -> None:
        controllers = self.app_context.get_controller_instances()
        for controller in controllers:
            name = controller.__class__.__name__
            router_prefix = controller.get_router_prefix()
            controller.app = self.fastapi
            controller.router = APIRouter(prefix=router_prefix)
            self.app_context.inject_dependencies_for_instance(controller)
            routes = self.registry.routes.get(name, set())
            controller.post_construct()
            controller._register_decorated_routes(routes)
            router = controller.get_router()
            self.fastapi.include_router(router)
            logger.debug(f"[CONTROLLER INIT] Controller {name} initialized")

    def _init_external_handler(self, base_class: Type[SingleInheritanceRequiredT]) -> Type[SingleInheritanceRequiredT] | None:
        """Initialize an external handler (middleware registry or graceful shutdown handler).
        
        Args:
            base_class: The base class to get subclass from
            
        Returns:
            The initialized handler class or None if no handler is found
        
        Raises:
            RuntimeError: If the handler has unimplemented abstract methods
        """
        handler_type = base_class.__name__
        handler_cls = base_class.get_subclass()
        if handler_cls is None:
            logger.debug(f"[{handler_type} INIT] No self defined {handler_type.lower()} class found")
            return None

        unimplemented_abstract_methods = framework_utils.get_unimplemented_abstract_methods(handler_cls)
        if len(unimplemented_abstract_methods) > 0:
            error_message = f"[{handler_type} INIT] Self defined {handler_type.lower()} class: {handler_cls.__name__} has unimplemented abstract methods: {unimplemented_abstract_methods}"
            logger.error(error_message)
            raise RuntimeError(error_message)

        logger.debug(
            f"[{handler_type} INIT] Self defined {handler_type.lower()} class: {handler_cls.__name__}"
        )
        logger.debug(
            f"[{handler_type} INIT] Inject dependencies for external object: {handler_cls.__name__}"
        )
        self.app_context.inject_dependencies_for_external_object(handler_cls)
        return handler_cls

    def _init_middlewares(self) -> None:
        handler_type = MiddlewareRegistry.__name__
        logger.debug(f"[{handler_type} INIT] Initialize middlewares...")
        middleware_config_cls = self._init_external_handler(MiddlewareConfiguration)
        if middleware_config_cls is None:
            return
        registry = MiddlewareRegistry()
        logger.info(f"[{handler_type} INIT] Setup middlewares for registry: {registry.__class__.__name__}")
        middleware_config_cls().configure_middlewares(registry)
        logger.info(f"[{handler_type} INIT] Middlewares setup for registry: {registry.__class__.__name__} completed")
        middleware_classes: list[Type[Middleware]] = registry.get_middleware_classes()
        logger.info(f"[{handler_type} INIT] Middleware classes: {', '.join([middleware_class.__name__ for middleware_class in middleware_classes])}")
        for middleware_class in middleware_classes:
            logger.debug(
                f"[{handler_type} INIT] Inject dependencies for middleware: {middleware_class.__name__}"
            )
            self.app_context.inject_dependencies_for_external_object(middleware_class)
        registry.apply_middlewares(self.fastapi)
        logger.debug(f"[{handler_type} INIT] Middlewares initialized")

    def _init_graceful_shutdown(self) -> None:
        handler_type = GracefulShutdownHandler.__name__
        logger.debug(f"[{handler_type} INIT] Initialize graceful shutdown...")
        handler_cls: Optional[Type[GracefulShutdownHandler]] = self._init_external_handler(GracefulShutdownHandler)
        if handler_cls is None:
            return
        
        # Get shutdown configuration
        shutdown_config = self.app_config.shutdown_config
        logger.debug(f"[{handler_type} INIT] Shutdown timeout: {shutdown_config.timeout_seconds}s, enabled: {shutdown_config.enabled}")
        
        # Initialize handler with timeout configuration
        self.shutdown_handler = handler_cls(
            timeout_seconds=shutdown_config.timeout_seconds,
            timeout_enabled=shutdown_config.enabled
        )
        logger.debug(f"[{handler_type} INIT] Graceful shutdown initialized")

    def _configure_uvicorn_logging(self):
        """Configure Uvicorn to use Loguru instead of default logging."""

        # Configure Uvicorn to use Loguru
        # Intercept standard logging and redirect to loguru
        class InterceptHandler(logging.Handler):
            def emit(self, record):
                # Get corresponding Loguru level if it exists
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno

                # Find caller from where originated the logged message
                frame, depth = logging.currentframe(), 2
                while frame and frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1

                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, record.getMessage()
                )

        # Remove default uvicorn logger and add intercept handler
        log_level = self.app_config.loguru_config.log_level.value
        logging.basicConfig(handlers=[InterceptHandler()], level=log_level, force=True)

    def _run_server(self) -> None:
        # Run uvicorn server
        uvicorn.run(
            self.fastapi,
            host=self.app_config.server_config.host,
            port=self.app_config.server_config.port,
            log_config=None,  # Disable uvicorn's default logging
        )

    def run(self) -> None:
        try:
            self._configure_logging()
            self._init_app()
            self._init_controllers()
            self._init_middlewares()
            self._init_graceful_shutdown()
            if self.app_config.server_config.enabled:
                self._run_server()
        finally:
            # Handle component lifecycle destruction
            self._handle_singleton_components_life_cycle(ComponentLifeCycle.Destruction)
            # Handle graceful shutdown completion
            if self.shutdown_handler:
                self.shutdown_handler.complete_shutdown()
            
            