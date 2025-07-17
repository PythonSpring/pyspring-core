import py_spring_core.core.utils as framework_utils

from abc import ABC
from inspect import isclass
from typing import (
    Annotated,
    Callable,
    Mapping,
    Optional,
    Type,
    TypeVar,
    cast,
    get_args,
    get_origin,
)

from fastapi import FastAPI
from loguru import logger
from pydantic import BaseModel

from py_spring_core.core.application.commons import AppEntities
from py_spring_core.core.application.context.application_context_config import (
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection import (
    BeanCollection,
    BeanConflictError,
    BeanView,
    InvalidBeanError,
)
from py_spring_core.core.entities.component import Component, ComponentScope
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.entity_provider import EntityProvider
from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.entities.properties.properties_loader import _PropertiesLoader

T = TypeVar("T", bound=AppEntities)
PT = TypeVar("PT", bound=Properties)


class ComponentNotFoundError(Exception):
    """Raised when a component is not found in the application context."""
    pass


class InvalidDependencyError(Exception):
    """Raised when a dependency is invalid or not found in the application context."""
    pass


class ApplicationContextView(BaseModel):
    """View model for application context state."""
    config: ApplicationContextConfig
    component_cls_container: list[str]
    singleton_component_instance_container: list[str]


class ContainerManager:
    """Manages containers for different types of entities in the application context."""
    
    def __init__(self):
        self.component_cls_container: dict[str, Type[Component]] = {}
        self.controller_cls_container: dict[str, Type[RestController]] = {}
        self.singleton_component_instance_container: dict[str, Component] = {}
        
        self.bean_collection_cls_container: dict[str, Type[BeanCollection]] = {}
        self.singleton_bean_instance_container: dict[str, object] = {}
        
        self.properties_cls_container: dict[str, Type[Properties]] = {}
        self.singleton_properties_instance_container: dict[str, Properties] = {}
    
    def is_entity_in_container(self, entity_cls: Type[AppEntities]) -> bool:
        """Check if an entity class is registered in any container."""
        cls_name = entity_cls.__name__
        return (
            cls_name in self.component_cls_container
            or cls_name in self.controller_cls_container
            or cls_name in self.bean_collection_cls_container
            or cls_name in self.properties_cls_container
        )


class DependencyInjector:
    """Handles dependency injection for entities in the application context."""
    
    def __init__(self, container_manager: ContainerManager):
        self.container_manager = container_manager
        self.primitive_types = (bool, str, int, float, type(None))
        self._app_context: Optional['ApplicationContext'] = None
    
    def _extract_qualifier_from_annotation(self, annotated_type: Type) -> tuple[Type, Optional[str]]:
        """Extract the actual type and qualifier from an Annotated type."""
        qualifier = None
        if get_origin(annotated_type) is Annotated:
            type_args = get_args(annotated_type)
            annotated_type = type_args[0]
            if len(type_args) > 1:
                qualifier = type_args[1]
        return annotated_type, qualifier
    
    def _inject_properties_dependency(
        self, 
        entity: Type[AppEntities], 
        attr_name: str, 
        properties_cls: Type[Properties]
    ) -> bool:
        """Inject a properties dependency into an entity."""
        if self._app_context is None:
            return False
            
        optional_properties = self._app_context.get_properties(properties_cls)
        if optional_properties is None:
            raise TypeError(
                f"[PROPERTIES INJECTION ERROR] Properties: {properties_cls.get_name()} "
                f"is not found in properties file for class: {properties_cls.get_name()} "
                f"with key: {properties_cls.get_key()}"
            )
        setattr(entity, attr_name, optional_properties)
        return True
    
    def _try_inject_entity_dependency(
        self, 
        entity: Type[AppEntities], 
        attr_name: str, 
        entity_cls: Type[AppEntities], 
        qualifier: Optional[str]
    ) -> bool:
        """Try to inject an entity dependency using available getters."""
        if self._app_context is None:
            return False
            
        entity_getters: list[Callable[[Type[AppEntities], Optional[str]], Optional[AppEntities]]] = [
            self._app_context.get_component, 
            self._app_context.get_bean
        ]
        
        for getter in entity_getters:
            optional_entity = getter(entity_cls, qualifier)
            if optional_entity is not None:
                setattr(entity, attr_name, optional_entity)
                logger.success(
                    f"[DEPENDENCY INJECTION SUCCESS] Inject dependency for {entity_cls.__name__} "
                    f"in attribute: {attr_name}"
                )
                return True
        return False
    
    def inject_dependencies(self, entity: Type[AppEntities]) -> None:
        """Inject dependencies for a given entity based on its annotations."""
        for attr_name, annotated_type in entity.__annotations__.items():
            entity_cls, qualifier = self._extract_qualifier_from_annotation(annotated_type)
            
            # Skip primitive types
            if entity_cls in self.primitive_types:
                logger.warning(
                    f"[DEPENDENCY INJECTION SKIPPED] Skip inject dependency for attribute: {attr_name} "
                    f"with dependency: {entity_cls.__name__} because it is primitive type"
                )
                continue
            
            # Skip non-class types
            if not isclass(entity_cls):
                continue
            
            # Handle Properties injection
            if issubclass(entity_cls, Properties):
                if self._inject_properties_dependency(entity, attr_name, entity_cls):
                    continue
            
            # Try to inject entity dependency
            if self._try_inject_entity_dependency(entity, attr_name, entity_cls, qualifier):
                continue
            
            # If we get here, injection failed
            error_message = (
                f"[DEPENDENCY INJECTION FAILED] Fail to inject dependency for attribute: {attr_name} "
                f"with dependency: {entity_cls.__name__} with qualifier: {qualifier}, "
                f"consider register such dependency with Component decorator"
            )
            logger.critical(error_message)
            raise ValueError(error_message)


class ComponentManager:
    """Manages component registration and instantiation."""
    
    def __init__(self, container_manager: ContainerManager):
        self.container_manager = container_manager
    
    def _determine_target_cls_name(
        self, component_cls: Type[T], qualifier: Optional[str]
    ) -> str:
        """
        Determine the target class name for a given component class.
        
        Args:
            component_cls: The component class to determine the name for
            qualifier: Optional qualifier to use directly
            
        Returns:
            The target class name
            
        Raises:
            ValueError: If abstract class has no subclasses
        """
        if qualifier is not None:
            return qualifier
        
        # If it's not an ABC, return its name directly
        if not issubclass(component_cls, ABC):
            return component_cls.get_name()
        
        # If it's an ABC but has implementations, return its name directly
        if not component_cls.__abstractmethods__:
            return component_cls.get_name()
        
        # For abstract classes that need implementations
        subclasses = component_cls.__subclasses__()
        if len(subclasses) == 0:
            raise ValueError(
                f"[ABSTRACT CLASS ERROR] Abstract class {component_cls.__name__} has no subclasses"
            )
        
        # Fall back to first subclass if no primary component exists
        return subclasses[0].get_name()
    
    def register_component(self, component_cls: Type[Component]) -> None:
        """Register a component class in the container."""
        if not issubclass(component_cls, Component):
            raise TypeError(
                f"[COMPONENT REGISTRATION ERROR] Component: {component_cls} "
                f"is not a subclass of Component"
            )
        
        component_cls_name = component_cls.get_name()
        existing_component = self.container_manager.component_cls_container.get(component_cls_name)
        
        # Check if it's the same component to avoid duplicate registration
        if (existing_component and 
            existing_component.__name__ == component_cls.__name__ and
            existing_component == component_cls):
            return
        
        self.container_manager.component_cls_container[component_cls_name] = component_cls
    
    def get_component(self, component_cls: Type[T], qualifier: Optional[str]) -> Optional[T]:
        """Get a component instance by class and optional qualifier."""
        if not issubclass(component_cls, (Component, ABC)):
            return None
        
        target_cls_name = self._determine_target_cls_name(component_cls, qualifier)
        
        if target_cls_name not in self.container_manager.component_cls_container:
            return None
        
        scope = component_cls.get_scope()
        match scope:
            case ComponentScope.Singleton:
                return cast(T, self.container_manager.singleton_component_instance_container.get(target_cls_name))
            case ComponentScope.Prototype:
                return cast(T, component_cls())
    
    def _init_singleton_component(
        self, component_cls: Type[Component], component_cls_name: str
    ) -> Optional[Component]:
        """Initialize a singleton component instance."""
        try:
            return component_cls()
        except Exception as error:
            if "Can't instantiate abstract class" in str(error):
                logger.warning(
                    f"[INITIALIZING SINGLETON COMPONENT ERROR] Skip initializing singleton component: "
                    f"{component_cls_name} because it is an abstract class"
                )
                return None
            logger.error(
                f"[INITIALIZING SINGLETON COMPONENT ERROR] Error initializing singleton component: "
                f"{component_cls_name} with error: {error}"
            )
            raise error
    
    def _get_abstract_class_component_subclasses(self, component_cls: Type[ABC]) -> list[Type[Component]]:
        """Get all Component subclasses of an abstract class."""
        return [
            subclass for subclass in component_cls.__subclasses__() 
            if issubclass(subclass, Component)
        ]
    
    def _init_abstract_component_subclasses(self, component_cls: Type[ABC]) -> None:
        """Initialize singleton instances for abstract component subclasses."""
        component_classes = self._get_abstract_class_component_subclasses(component_cls)
        
        for subclass_component_cls in component_classes:
            self.register_component(subclass_component_cls)
            
            # Check for unimplemented abstract methods
            unimplemented_methods = framework_utils.get_unimplemented_abstract_methods(subclass_component_cls)
            if unimplemented_methods:
                methods_str = ", ".join(unimplemented_methods)
                message = (
                    f"[ABSTRACT CLASS COMPONENT INITIALIZING SINGLETON COMPONENT] "
                    f"Unable to initialize singleton component: {subclass_component_cls.get_name()} "
                    f"because it has unimplemented abstract methods: {methods_str}"
                )
                logger.error(message)
                raise ValueError(message)
            
            logger.debug(
                f"[ABSTRACT CLASS COMPONENT INITIALIZING SINGLETON COMPONENT] "
                f"Init singleton component: {subclass_component_cls.get_name()}"
            )
            
            instance = self._init_singleton_component(subclass_component_cls, subclass_component_cls.get_name())
            if instance is not None:
                self.container_manager.singleton_component_instance_container[subclass_component_cls.get_name()] = instance
    
    def init_singleton_components(self) -> None:
        """Initialize all singleton components in the container."""
        for component_cls_name, component_cls in self.container_manager.component_cls_container.items():
            if component_cls.get_scope() != ComponentScope.Singleton:
                continue
            
            logger.debug(f"[INITIALIZING SINGLETON COMPONENT] Init singleton component: {component_cls_name}")
            
            if issubclass(component_cls, ABC):
                self._init_abstract_component_subclasses(component_cls)
            else:
                instance = self._init_singleton_component(component_cls, component_cls_name)
                if instance is not None:
                    self.container_manager.singleton_component_instance_container[component_cls_name] = instance


class BeanManager:
    """Manages bean collection registration and instantiation."""
    
    def __init__(self, container_manager: ContainerManager, dependency_injector: DependencyInjector):
        self.container_manager = container_manager
        self.dependency_injector = dependency_injector
    
    def register_bean_collection(self, bean_cls: Type[BeanCollection]) -> None:
        """Register a bean collection class in the container."""
        if not issubclass(bean_cls, BeanCollection):
            raise TypeError(
                f"[BEAN COLLECTION REGISTRATION ERROR] BeanCollection: {bean_cls} "
                f"is not a subclass of BeanCollection"
            )
        
        bean_name = bean_cls.get_name()
        self.container_manager.bean_collection_cls_container[bean_name] = bean_cls
    
    def get_bean(self, object_cls: Type[T], qualifier: Optional[str] = None) -> Optional[T]:
        """Get a bean instance by class and optional qualifier."""
        bean_name = object_cls.__name__
        if bean_name not in self.container_manager.singleton_bean_instance_container:
            return None
        
        return cast(T, self.container_manager.singleton_bean_instance_container.get(bean_name))
    
    def _inject_bean_collection_dependencies(self, bean_collection_cls: Type[BeanCollection]) -> None:
        """Inject dependencies for a bean collection."""
        logger.info(
            f"[BEAN COLLECTION DEPENDENCY INJECTION] Injecting dependencies for {bean_collection_cls.get_name()}"
        )
        self.dependency_injector.inject_dependencies(bean_collection_cls)
    
    def _validate_bean_view(self, view: BeanView, collection_name: str) -> None:
        """Validate a bean view before adding it to the container."""
        if view.bean_name in self.container_manager.singleton_bean_instance_container:
            raise BeanConflictError(
                f"[BEAN CONFLICTS] Bean: {view.bean_name} already exists under collection: {collection_name}"
            )
        
        if not view.is_valid_bean():
            raise InvalidBeanError(
                f"[INVALID BEAN] Bean name from bean creation func return type: {view.bean_name} "
                f"does not match the bean object class name: {view.bean.__class__.__name__}"
            )
    
    def init_singleton_beans(self) -> None:
        """Initialize all singleton beans from registered bean collections."""
        for bean_collection_cls_name, bean_collection_cls in self.container_manager.bean_collection_cls_container.items():
            logger.debug(f"[INITIALIZING SINGLETON BEAN] Init singleton bean: {bean_collection_cls_name}")
            
            collection = bean_collection_cls()
            self._inject_bean_collection_dependencies(bean_collection_cls)
            
            bean_views = collection.scan_beans()
            for view in bean_views:
                self._validate_bean_view(view, collection.get_name())
                self.container_manager.singleton_bean_instance_container[view.bean_name] = view.bean


class PropertiesManager:
    """Manages properties registration and loading."""
    
    def __init__(self, container_manager: ContainerManager, config: ApplicationContextConfig):
        self.container_manager = container_manager
        self.config = config
    
    def register_properties(self, properties_cls: Type[Properties]) -> None:
        """Register a properties class in the container."""
        if not issubclass(properties_cls, Properties):
            raise TypeError(
                f"[PROPERTIES REGISTRATION ERROR] Properties: {properties_cls} "
                f"is not a subclass of Properties"
            )
        
        properties_name = properties_cls.get_key()
        self.container_manager.properties_cls_container[properties_name] = properties_cls
    
    def get_properties(self, properties_cls: Type[PT]) -> Optional[PT]:
        """Get a properties instance by class."""
        properties_cls_name = properties_cls.get_key()
        if properties_cls_name not in self.container_manager.properties_cls_container:
            return None
        
        return cast(PT, self.container_manager.singleton_properties_instance_container.get(properties_cls_name))
    
    def _create_properties_loader(self) -> _PropertiesLoader:
        """Create a properties loader instance."""
        return _PropertiesLoader(
            self.config.properties_path, 
            list(self.container_manager.properties_cls_container.values())
        )
    
    def load_properties(self) -> None:
        """Load all registered properties from configuration files."""
        properties_loader = self._create_properties_loader()
        properties_instance_dict = properties_loader.load_properties()
        
        for properties_key, properties_cls in self.container_manager.properties_cls_container.items():
            if properties_key in self.container_manager.singleton_properties_instance_container:
                continue
            
            logger.debug(f"[INITIALIZING SINGLETON PROPERTIES] Init singleton properties: {properties_key}")
            
            optional_properties = properties_instance_dict.get(properties_key)
            if optional_properties is None:
                raise TypeError(
                    f"[PROPERTIES INITIALIZATION ERROR] Properties: {properties_key} "
                    f"is not found in properties file for class: {properties_cls.get_name()} "
                    f"with key: {properties_cls.get_key()}"
                )
            
            self.container_manager.singleton_properties_instance_container[properties_key] = optional_properties
        
        # Update the global properties loader reference
        _PropertiesLoader.optional_loaded_properties = self.container_manager.singleton_properties_instance_container


class ApplicationContext:
    """
    The main entry point for the application's context management.
    
    This class is responsible for:
    1. Registering and managing the lifecycle of components, controllers, bean collections, and properties.
    2. Providing methods to retrieve instances of registered components, beans, and properties.
    3. Initializing the Inversion of Control (IoC) container by creating singleton instances of registered components.
    4. Injecting dependencies for registered components and controllers.
    
    The ApplicationContext class is designed to follow the Singleton design pattern, ensuring that there is 
    a single instance of the application context throughout the application's lifetime.
    """

    def __init__(self, config: ApplicationContextConfig, server: FastAPI) -> None:
        self.server = server
        self.config = config
        self.all_file_paths: set[str] = set()
        self.providers: list[EntityProvider] = []
        
        # Initialize managers
        self.container_manager = ContainerManager()
        self.dependency_injector = DependencyInjector(self.container_manager)
        self.component_manager = ComponentManager(self.container_manager)
        self.bean_manager = BeanManager(self.container_manager, self.dependency_injector)
        self.properties_manager = PropertiesManager(self.container_manager, config)
        
        # Set app context reference for dependency injection
        self.dependency_injector._app_context = self

    def set_all_file_paths(self, all_file_paths: set[str]) -> None:
        """Set the collection of all file paths in the application."""
        self.all_file_paths = all_file_paths

    def as_view(self) -> ApplicationContextView:
        """Create a view model of the application context state."""
        return ApplicationContextView(
            config=self.config,
            component_cls_container=list(self.container_manager.component_cls_container.keys()),
            singleton_component_instance_container=list(
                self.container_manager.singleton_component_instance_container.keys()
            ),
        )

    # Component management methods
    def get_component(self, component_cls: Type[T], qualifier: Optional[str] = None) -> Optional[T]:
        """Get a component instance by class and optional qualifier."""
        return self.component_manager.get_component(component_cls, qualifier)

    def register_component(self, component_cls: Type[Component]) -> None:
        """Register a component class in the application context."""
        self.component_manager.register_component(component_cls)

    # Bean management methods
    def get_bean(self, object_cls: Type[T], qualifier: Optional[str] = None) -> Optional[T]:
        """Get a bean instance by class and optional qualifier."""
        return self.bean_manager.get_bean(object_cls, qualifier)

    def register_bean_collection(self, bean_cls: Type[BeanCollection]) -> None:
        """Register a bean collection class in the application context."""
        self.bean_manager.register_bean_collection(bean_cls)

    # Properties management methods
    def get_properties(self, properties_cls: Type[PT]) -> Optional[PT]:
        """Get a properties instance by class."""
        return self.properties_manager.get_properties(properties_cls)

    def register_properties(self, properties_cls: Type[Properties]) -> None:
        """Register a properties class in the application context."""
        self.properties_manager.register_properties(properties_cls)

    def load_properties(self) -> None:
        """Load all registered properties from configuration files."""
        self.properties_manager.load_properties()

    # Controller management methods
    def register_controller(self, controller_cls: Type[RestController]) -> None:
        """Register a controller class in the application context."""
        if not issubclass(controller_cls, RestController):
            raise TypeError(
                f"[CONTROLLER REGISTRATION ERROR] Controller: {controller_cls} "
                f"is not a subclass of RestController"
            )
        
        controller_cls_name = controller_cls.get_name()
        self.container_manager.controller_cls_container[controller_cls_name] = controller_cls

    def get_controller_instances(self) -> list[RestController]:
        """Get all controller instances."""
        return [cls() for cls in self.container_manager.controller_cls_container.values()]

    def get_singleton_component_instances(self) -> list[Component]:
        """Get all singleton component instances."""
        return list(self.container_manager.singleton_component_instance_container.values())

    def get_singleton_bean_instances(self) -> list[object]:
        """Get all singleton bean instances."""
        return list(self.container_manager.singleton_bean_instance_container.values())

    def is_within_context(self, entity_cls: Type[AppEntities]) -> bool:
        """Check if an entity class is registered in the application context."""
        return self.container_manager.is_entity_in_container(entity_cls)

    def init_ioc_container(self) -> None:
        """
        Initialize the IoC (Inversion of Control) container.
        
        This method creates singleton instances of all registered components and beans,
        ensuring that subsequent calls to get_component() for singleton components 
        will return the same instance, as required by the Singleton design pattern.
        """
        # Initialize singleton components
        self.component_manager.init_singleton_components()
        
        # Initialize singleton beans
        self.bean_manager.init_singleton_beans()

    def inject_dependencies_for_app_entities(self) -> None:
        """Inject dependencies for all registered app entities."""
        containers: list[Mapping[str, Type[AppEntities]]] = [
            self.container_manager.component_cls_container,
            self.container_manager.controller_cls_container,
        ]

        for container in containers:
            for cls_name, cls in container.items():
                self.dependency_injector.inject_dependencies(cls)

    def _validate_entity_provider_dependencies(self, provider: EntityProvider) -> None:
        """Validate dependencies for a single entity provider."""
        for dependency in provider.depends_on:
            if not issubclass(dependency, AppEntities):
                error = f"[INVALID DEPENDENCY] Invalid dependency {dependency.__name__} in {provider.__class__.__name__}"
                logger.error(error)
                raise InvalidDependencyError(error)
            
            if not self.is_within_context(dependency):
                error = f"[INVALID DEPENDENCY] Dependency {dependency.__name__} not found in the application context"
                logger.error(error)
                raise InvalidDependencyError(error)

    def validate_entity_providers(self) -> None:
        """Validate all entity providers in the application context."""
        for provider in self.providers:
            self._validate_entity_provider_dependencies(provider)
