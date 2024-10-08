import os
from typing import Any, Callable, Iterable, Type

import uvicorn
from fastapi import APIRouter, FastAPI
from loguru import logger
from pydantic import BaseModel, ConfigDict

from py_spring_core.commons.type_checking_service import TypeCheckingService
from py_spring_core.core.application.commons import AppEntities
from py_spring_core.core.entities.entity_provider import EntityProvider
from py_spring_core.commons.class_scanner import ClassScanner
from py_spring_core.commons.config_file_template_generator.config_file_template_generator import (
    ConfigFileTemplateGenerator,
)
from py_spring_core.commons.file_path_scanner import FilePathScanner
from py_spring_core.core.application.application_config import ApplicationConfigRepository, TypeCheckingMode
from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
)
from py_spring_core.core.application.context.application_context_config import (
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection import BeanCollection
from py_spring_core.core.entities.component import Component, ComponentLifeCycle
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.properties.properties import Properties


class ApplicationFileGroups(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    class_files: set[str]
    model_files: set[str]


class PySpringApplication:
    """
    The PySpringApplication class is the main entry point for the PySpring application.
    It is responsible for initializing the application, registering application entities, and running the FastAPI server.

    The class performs the following key tasks:
    - Initializes the application from a configuration file path
    - Scans the application source directory for Python files and groups them into class files and model files
    - Dynamically imports the model modules and creates SQLModel tables
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
        self, app_config_path: str, entity_providers: Iterable[EntityProvider] = list()
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
        self.app_context = ApplicationContext(config=self.app_context_config)
        self.fastapi = FastAPI()

        self.classes_with_handlers: dict[
            Type[AppEntities], Callable[[Type[Any]], None]
        ] = {
            Component: self._handle_register_component,
            RestController: self._handle_register_rest_controller,
            BeanCollection: self._handle_register_bean_collection,
            Properties: self._handle_register_properties,
        }
        self.type_checking_service = TypeCheckingService(self.app_config.app_src_target_dir)

    def __configure_logging(self):
        """Applies the logging configuration using Loguru."""
        config = self.app_config.loguru_config
        if not config.log_file_path:
            return

        logger.add(
            config.log_file_path,
            format=config.log_format,
            level=config.log_level,
            rotation=config.log_rotation,
            retention=config.log_retention,
        )

    def _scan_classes_for_project(self) -> None:
        self.app_class_scanner.scan_classes_for_file_paths()
        self.scanned_classes = self.app_class_scanner.get_classes()

    def _register_all_entities_from_providers(self) -> None:
        for provider in self.entity_providers:
            entities = provider.get_entities()
            self._register_app_entities(entities)

    def _register_app_entities(self, classes: Iterable[Type[object]]) -> None:
        for _cls in classes:
            for _target_cls, handler in self.classes_with_handlers.items():
                if not issubclass(_cls, _target_cls):
                    continue
                handler(_cls)

    def _register_entity_providers(
        self, entity_providers: Iterable[EntityProvider]
    ) -> None:
        for provider in entity_providers:
            self.app_context.register_entity_provider(provider)
            provider.set_context(self.app_context)

    def _handle_register_component(self, _cls: Type[Component]) -> None:
        self.app_context.register_component(_cls)

    def _handle_register_rest_controller(self, _cls: Type[RestController]) -> None:
        logger.debug(
            f"[REST CONTROLLER INIT] Register router for controller: {_cls.__name__}"
        )
        self.app_context.register_controller(_cls)
        _cls.app = self.fastapi
        router_prefix = _cls.get_router_prefix()
        logger.debug(
            f"[REST CONTROLLER INIT] Register router with prefix: {router_prefix}"
        )
        _cls.router = APIRouter(prefix=router_prefix)

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

    def __init_app(self) -> None:
        self._scan_classes_for_project()
        self._register_all_entities_from_providers()
        self._register_app_entities(self.scanned_classes)
        self._register_entity_providers(self.entity_providers)
        self._type_checking()
        self.app_context.load_properties()
        self.app_context.init_ioc_container()
        self.app_context.inject_dependencies_for_app_entities()
        self.app_context.set_all_file_paths(self.target_dir_absolute_file_paths)
        self.app_context.validate_entity_providers()
        # after injecting all deps, lifecycle (init) can be called

        self._init_providers(self.entity_providers)
        self._handle_singleton_components_life_cycle(ComponentLifeCycle.Init)

    def _type_checking(self) -> None:
        optional_error = self.type_checking_service.type_checking()
        if optional_error is not None:
            match (self.app_config.type_checking_mode):
                case TypeCheckingMode.Strict:
                    raise optional_error
                case TypeCheckingMode.Basic:
                    logger.warning(optional_error)

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

    def __init_controllers(self) -> None:
        controllers = self.app_context.get_controller_instances()
        for controller in controllers:
            controller.register_routes()
            router = controller.get_router()
            self.fastapi.include_router(router)
            controller.register_middlewares()

    def __run_server(self) -> None:
        uvicorn.run(
            self.fastapi,
            host=self.app_config.server_config.host,
            port=self.app_config.server_config.port,
        )

    def run(self) -> None:
        try:
            self.__configure_logging()
            self.__init_app()
            self.__init_controllers()
            if self.app_config.server_config.enabled:
                self.__run_server()
        finally:
            self._handle_singleton_components_life_cycle(ComponentLifeCycle.Destruction)
