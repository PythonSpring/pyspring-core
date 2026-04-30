from abc import ABC
from inspect import isclass
from typing import (
    Annotated,
    Any,
    Callable,
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

import py_spring_core.core.utils as framework_utils
from py_spring_core.core.application.application_registry import ApplicationRegistry
from py_spring_core.core.application.commons import AppEntities
from py_spring_core.core.application.context.application_context_config import (
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection.bean_collection import (
    BeanCollection,
    BeanConflictError,
    BeanView,
    InvalidBeanError,
)
from py_spring_core.core.entities.component.component import Component, ComponentScope
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.starter.py_spring_starter import PySpringStarter
from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.entities.properties.properties_loader import _PropertiesLoader

T = TypeVar("T", bound=AppEntities)
BT = TypeVar("BT")
PT = TypeVar("PT", bound=Properties)


class ComponentNotFoundError(Exception):
    """Raised when a component is not found in the application context."""

    pass


class ComponentConflictError(Exception):
    """Raised when two different component classes are registered with the same name."""

    pass


class InvalidDependencyError(Exception):
    """Raised when a dependency is invalid or not found in the application context."""

    pass


class ApplicationContextView(BaseModel):
    """View model for application context state."""

    config: ApplicationContextConfig
    component_classes: list[str]
    component_instances: list[str]


class ContainerManager:
    """Manages containers for different types of entities in the application context."""

    def __init__(self):
        self.component_classes: dict[str, Type[Component]] = {}
        self.controller_classes: dict[str, Type[RestController]] = {}
        self.component_instances: dict[str, Component] = {}

        self.bean_collection_classes: dict[str, Type[BeanCollection]] = {}
        self.bean_instances: dict[str, object] = {}

        self.properties_classes: dict[str, Type[Properties]] = {}
        self.properties_instances: dict[str, Properties] = {}

    def is_entity_in_container(self, entity_cls: Type[AppEntities]) -> bool:
        """Check if an entity class is registered in any container."""
        cls_name = entity_cls.__name__
        return (
            cls_name in self.component_classes
            or cls_name in self.controller_classes
            or cls_name in self.bean_collection_classes
            or cls_name in self.properties_classes
        )


class DependencyInjector:
    """Handles dependency injection for entities in the application context."""

    def __init__(self, container_manager: ContainerManager):
        self.container_manager = container_manager
        self.primitive_types = (bool, str, int, float, type(None))
        self._app_context: Optional["ApplicationContext"] = None

    def _extract_qualifier_from_annotation(
        self, annotated_type: Type
    ) -> tuple[Type, Optional[str]]:
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
        target: object,
        attr_name: str,
        properties_cls: Type[Properties],
    ) -> bool:
        """Inject a properties dependency into a target instance."""
        if self._app_context is None:
            return False

        optional_properties = self._app_context.get_properties(properties_cls)
        if optional_properties is None:
            raise TypeError(
                f"[PROPERTIES INJECTION ERROR] Properties: {properties_cls.get_name()} "
                f"is not found in properties file for class: {properties_cls.get_name()} "
                f"with key: {properties_cls.get_key()}"
            )
        setattr(target, attr_name, optional_properties)
        return True

    def _collect_instances_by_type(self, element_cls: type) -> list[object]:
        """Collect all component and bean instances matching the given type."""
        collected: list[object] = []
        for instance in self.container_manager.component_instances.values():
            if isinstance(instance, element_cls):
                collected.append(instance)
        for instance in self.container_manager.bean_instances.values():
            if isinstance(instance, element_cls):
                collected.append(instance)
        return collected

    def _try_inject_collection_dependency(
        self,
        target: object,
        attr_name: str,
        entity_cls: type,
    ) -> bool:
        """Try to inject a collection (List[T], Set[T], Dict[str, T]) dependency."""
        origin = get_origin(entity_cls)
        if origin not in (list, set, dict):
            return False

        args = get_args(entity_cls)

        if origin in (list, set):
            if not args or not isclass(args[0]):
                return False
            element_cls = args[0]
            collected_instances = self._collect_instances_by_type(element_cls)
            value: Any = collected_instances if origin is list else set(collected_instances)
        else:
            if len(args) < 2 or args[0] is not str or not isclass(args[1]):
                return False
            element_cls = args[1]
            collected_instances = self._collect_instances_by_type(element_cls)
            value = {type(inst).__name__: inst for inst in collected_instances}

        setattr(target, attr_name, value)
        logger.success(
            f"[COLLECTION INJECTION SUCCESS] Injected {len(collected_instances)} instances "
            f"of {element_cls.__name__} as {origin.__name__} into {attr_name}"
        )
        return True

    def _try_inject_entity_dependency(
        self,
        target: object,
        attr_name: str,
        entity_cls: type,
        qualifier: Optional[str],
    ) -> bool:
        """Try to inject an entity dependency using available getters."""
        if self._app_context is None:
            return False

        entity_getters: list[Callable[..., Optional[object]]] = [
            self._app_context.get_component,
            self._app_context.get_bean,
        ]

        for getter in entity_getters:
            optional_entity = getter(entity_cls, qualifier)
            if optional_entity is not None:
                setattr(target, attr_name, optional_entity)
                logger.success(
                    f"[DEPENDENCY INJECTION SUCCESS] Inject dependency for {entity_cls.__name__} "
                    f"in attribute: {attr_name}"
                )
                return True
        return False

    def _has_default_value(self, target: object, attr_name: str) -> bool:
        """Check if an attribute has a default value on the class or instance."""
        target_cls = type(target) if not isinstance(target, type) else target
        if hasattr(target, attr_name):
            return True
        for cls in target_cls.__mro__:
            if attr_name in cls.__dict__:
                return True
        return False

    def inject_dependencies(self, target: object) -> None:
        """Inject dependencies into a target instance based on its class annotations."""
        target_cls = type(target) if not isinstance(target, type) else target
        for attr_name, annotated_type in target_cls.__annotations__.items():
            entity_cls, qualifier = self._extract_qualifier_from_annotation(
                annotated_type
            )

            # Skip primitive types
            if entity_cls in self.primitive_types:
                logger.warning(
                    f"[DEPENDENCY INJECTION SKIPPED] Skip inject dependency for attribute: {attr_name} "
                    f"with dependency: {entity_cls.__name__} because it is primitive type"
                )
                continue

            if not isclass(entity_cls):
                injected = self._try_inject_collection_dependency(target, attr_name, entity_cls)
                if not injected and not self._has_default_value(target, attr_name):
                    error_message = (
                        f"[DEPENDENCY INJECTION FAILED] Fail to inject dependency for attribute: {attr_name} "
                        f"with dependency: {entity_cls} with qualifier: {qualifier}, "
                        f"consider register such dependency with Component decorator"
                    )
                    logger.critical(error_message)
                    raise ValueError(error_message)
                continue

            # Handle Properties injection
            if issubclass(entity_cls, Properties):
                if self._inject_properties_dependency(target, attr_name, entity_cls):
                    continue

            # Try to inject entity dependency
            if self._try_inject_entity_dependency(
                target, attr_name, entity_cls, qualifier
            ):
                continue

            # If attribute has a default value, skip injection instead of failing
            if self._has_default_value(target, attr_name):
                logger.debug(
                    f"[DEPENDENCY INJECTION SKIPPED] Skipping injection for attribute: {attr_name} "
                    f"with type: {entity_cls.__name__} - has default value and is not an injectable type"
                )
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

    def __init__(
        self,
        container_manager: ContainerManager,
        dependency_injector: Optional["DependencyInjector"] = None,
    ):
        self.container_manager = container_manager
        self.dependency_injector = dependency_injector

    def _determine_target_cls_name(
        self, component_cls: type, qualifier: Optional[str]
    ) -> str:
        """
        Determine the target class name for a given component class.

        Args:
            component_cls: The component class to determine the name for
            qualifier: Optional qualifier to use directly

        Returns:
            The target class name

        Raises:
            ValueError: If abstract class has no subclasses or multiple
                        implementations exist without a qualifier
        """
        if qualifier is not None:
            return qualifier

        # If it's not an ABC, return its name directly
        if not issubclass(component_cls, ABC):
            return cast(Type[Component], component_cls).get_name()

        # If it's an ABC but has implementations, return its name directly
        if not component_cls.__abstractmethods__:
            return cast(Type[Component], component_cls).get_name()

        # For abstract classes that need implementations — search recursively
        def _collect_concrete_subclasses(cls: type) -> list[Type[Component]]:
            result: list[Type[Component]] = []
            for sc in cls.__subclasses__():
                if not issubclass(sc, Component):
                    continue
                if getattr(sc, "__abstractmethods__", frozenset()):
                    result.extend(_collect_concrete_subclasses(sc))
                else:
                    result.append(sc)
            return result

        subclasses = _collect_concrete_subclasses(component_cls)
        if len(subclasses) == 0:
            raise ValueError(
                f"[ABSTRACT CLASS ERROR] Abstract class {component_cls.__name__} has no subclasses"
            )

        if len(subclasses) > 1:
            names = [sc.get_name() for sc in subclasses]
            raise ValueError(
                f"[AMBIGUOUS DEPENDENCY] Abstract class {component_cls.__name__} "
                f"has multiple implementations: {names}. "
                f"Use Annotated[{component_cls.__name__}, '<qualifier>'] to specify which one."
            )

        return subclasses[0].get_name()

    def register_component(self, component_cls: Type[Component]) -> None:
        """Register a component class in the container."""
        if not issubclass(component_cls, Component):
            raise TypeError(
                f"[COMPONENT REGISTRATION ERROR] Component: {component_cls} "
                f"is not a subclass of Component"
            )

        component_cls_name = component_cls.get_name()
        existing_component = self.container_manager.component_classes.get(
            component_cls_name
        )

        if existing_component is not None:
            # Same class re-registered — skip
            if existing_component is component_cls:
                return

            # Different class, same name — error
            raise ComponentConflictError(
                f"[COMPONENT CONFLICT] Component name '{component_cls_name}' is already "
                f"registered by {existing_component.__name__}. "
                f"Cannot register {component_cls.__name__} with the same name."
            )

        self.container_manager.component_classes[component_cls_name] = (
            component_cls
        )

    def get_component(
        self, component_cls: Type[T], qualifier: Optional[str]
    ) -> Optional[T]:
        """Get a component instance by class and optional qualifier."""
        if not issubclass(component_cls, (Component, ABC)):
            return None

        target_cls_name = self._determine_target_cls_name(component_cls, qualifier)

        if target_cls_name not in self.container_manager.component_classes:
            return None

        target_cls = self.container_manager.component_classes[target_cls_name]

        if qualifier is not None and not issubclass(target_cls, component_cls):
            raise TypeError(
                f"[QUALIFIER TYPE ERROR] Resolved component '{target_cls_name}' "
                f"({target_cls.__name__}) is not a subclass of the declared type "
                f"{component_cls.__name__}"
            )

        scope = target_cls.get_scope()
        match scope:
            case ComponentScope.Singleton:
                return cast(
                    T,
                    self.container_manager.component_instances.get(
                        target_cls_name
                    ),
                )
            case ComponentScope.Prototype:
                instance = target_cls()
                if self.dependency_injector is not None:
                    self.dependency_injector.inject_dependencies(instance)
                instance.finish_initialization_cycle()
                return cast(T, instance)

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

    def _get_abstract_class_component_subclasses(
        self, component_cls: Type[ABC]
    ) -> list[Type[Component]]:
        """Get all concrete Component subclasses of an abstract class, recursively."""
        result: list[Type[Component]] = []
        for subclass in component_cls.__subclasses__():
            if not issubclass(subclass, Component):
                continue
            if getattr(subclass, "__abstractmethods__", frozenset()):
                result.extend(self._get_abstract_class_component_subclasses(subclass))
            else:
                result.append(subclass)
        return result

    def _init_abstract_component_subclasses(self, component_cls: Type[ABC]) -> None:
        """Initialize singleton instances for abstract component subclasses."""
        component_classes = self._get_abstract_class_component_subclasses(component_cls)

        if not component_classes:
            message = (
                f"[ABSTRACT CLASS ERROR] Abstract class {component_cls.__name__} "
                f"has no registered subclasses. Register at least one concrete "
                f"implementation as a Component."
            )
            logger.error(message)
            raise ValueError(message)

        for subclass_component_cls in component_classes:
            self.register_component(subclass_component_cls)

            # Check for unimplemented abstract methods
            unimplemented_methods = framework_utils.get_unimplemented_abstract_methods(
                subclass_component_cls
            )
            if unimplemented_methods:
                methods_str = ", ".join(unimplemented_methods)
                message = (
                    f"[ABSTRACT CLASS COMPONENT INITIALIZING SINGLETON COMPONENT] "
                    f"Unable to initialize singleton component: {subclass_component_cls.get_name()} "
                    f"because it has unimplemented abstract methods: {methods_str}"
                )
                logger.error(message)
                raise ValueError(message)

            if subclass_component_cls.get_scope() != ComponentScope.Singleton:
                logger.debug(
                    f"[ABSTRACT CLASS COMPONENT] Skipping non-singleton subclass: "
                    f"{subclass_component_cls.get_name()} (scope: {subclass_component_cls.get_scope()})"
                )
                continue

            subclass_name = subclass_component_cls.get_name()
            if subclass_name in self.container_manager.component_instances:
                continue

            logger.debug(
                f"[ABSTRACT CLASS COMPONENT INITIALIZING SINGLETON COMPONENT] "
                f"Init singleton component: {subclass_name}"
            )

            instance = self._init_singleton_component(
                subclass_component_cls, subclass_name
            )
            if instance is not None:
                self.container_manager.component_instances[subclass_name] = instance

    def init_singleton_components(self) -> None:
        """Initialize all singleton components in the container."""
        for (
            component_cls_name,
            component_cls,
        ) in list(self.container_manager.component_classes.items()):
            if component_cls.get_scope() != ComponentScope.Singleton:
                continue

            if issubclass(component_cls, ABC) and getattr(component_cls, "__abstractmethods__", frozenset()):
                self._init_abstract_component_subclasses(component_cls)
                continue

            if component_cls_name in self.container_manager.component_instances:
                continue

            logger.debug(
                f"[INITIALIZING SINGLETON COMPONENT] Init singleton component: {component_cls_name}"
            )

            instance = self._init_singleton_component(
                component_cls, component_cls_name
            )
            if instance is not None:
                self.container_manager.component_instances[
                    component_cls_name
                ] = instance


class BeanManager:
    """Manages bean collection registration and instantiation."""

    def __init__(
        self,
        container_manager: ContainerManager,
        dependency_injector: DependencyInjector,
    ):
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
        self.container_manager.bean_collection_classes[bean_name] = bean_cls

    def get_bean(
        self, object_cls: Type[BT], qualifier: Optional[str] = None
    ) -> Optional[BT]:
        """Get a bean instance by class and optional qualifier."""
        bean_name = qualifier if qualifier is not None else object_cls.__name__
        if bean_name not in self.container_manager.bean_instances:
            return None

        bean = self.container_manager.bean_instances[bean_name]
        if not isinstance(bean, object_cls):
            return None

        return bean

    def _inject_bean_collection_dependencies(
        self, bean_collection_cls: Type[BeanCollection]
    ) -> None:
        """Inject dependencies for a bean collection class.

        BeanCollection methods (scan_beans, create_*) are classmethods that
        access dependencies via ``cls``, so properties must be set on the
        class itself rather than on an instance.
        """
        logger.info(
            f"[BEAN COLLECTION DEPENDENCY INJECTION] Injecting dependencies for {bean_collection_cls.get_name()}"
        )
        self.dependency_injector.inject_dependencies(bean_collection_cls)

    def _validate_bean_view(self, view: BeanView, collection_name: str) -> None:
        """Validate a bean view before adding it to the container."""
        if view.bean_name in self.container_manager.bean_instances:
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
        for (
            bean_collection_cls_name,
            bean_collection_cls,
        ) in self.container_manager.bean_collection_classes.items():
            logger.debug(
                f"[INITIALIZING SINGLETON BEAN] Init singleton bean: {bean_collection_cls_name}"
            )

            self._inject_bean_collection_dependencies(bean_collection_cls)

            bean_views = bean_collection_cls.scan_beans()
            for view in bean_views:
                if view.bean_name in self.container_manager.bean_instances:
                    continue
                self._validate_bean_view(view, bean_collection_cls.get_name())
                self.container_manager.bean_instances[
                    view.bean_name
                ] = view.bean


class PropertiesManager:
    """Manages properties registration and loading."""

    def __init__(
        self, container_manager: ContainerManager, config: ApplicationContextConfig
    ):
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
        self.container_manager.properties_classes[properties_name] = (
            properties_cls
        )

    def get_properties(self, properties_cls: Type[PT]) -> Optional[PT]:
        """Get a properties instance by class."""
        properties_cls_name = properties_cls.get_key()
        if properties_cls_name not in self.container_manager.properties_classes:
            return None

        return cast(
            PT,
            self.container_manager.properties_instances.get(
                properties_cls_name
            ),
        )

    def _create_properties_loader(self) -> _PropertiesLoader:
        """Create a properties loader instance."""
        return _PropertiesLoader(
            self.config.properties_path,
            list(self.container_manager.properties_classes.values()),
        )

    def load_properties(self) -> None:
        """Load all registered properties from configuration files."""
        properties_loader = self._create_properties_loader()
        properties_instance_dict = properties_loader.load_properties()

        for (
            properties_key,
            properties_cls,
        ) in self.container_manager.properties_classes.items():
            if (
                properties_key
                in self.container_manager.properties_instances
            ):
                continue

            logger.debug(
                f"[INITIALIZING SINGLETON PROPERTIES] Init singleton properties: {properties_key}"
            )

            optional_properties = properties_instance_dict.get(properties_key)
            if optional_properties is None:
                raise TypeError(
                    f"[PROPERTIES INITIALIZATION ERROR] Properties: {properties_key} "
                    f"is not found in properties file for class: {properties_cls.get_name()} "
                    f"with key: {properties_cls.get_key()}"
                )

            self.container_manager.properties_instances[
                properties_key
            ] = optional_properties



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

    def __init__(
        self,
        config: ApplicationContextConfig,
        server: FastAPI,
        registry: Optional[ApplicationRegistry] = None,
    ) -> None:
        self.server = server
        self.config = config
        self.registry = registry or ApplicationRegistry()
        self.all_file_paths: set[str] = set()
        self.starters: list[PySpringStarter] = []

        # Initialize managers
        self.container_manager = ContainerManager()
        self.dependency_injector = DependencyInjector(self.container_manager)
        self.component_manager = ComponentManager(
            self.container_manager, self.dependency_injector
        )
        self.bean_manager = BeanManager(
            self.container_manager, self.dependency_injector
        )
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
            component_classes=list(
                self.container_manager.component_classes.keys()
            ),
            component_instances=list(
                self.container_manager.component_instances.keys()
            ),
        )

    # Component management methods
    def get_component(
        self, component_cls: Type[T], qualifier: Optional[str] = None
    ) -> Optional[T]:
        """Get a component instance by class and optional qualifier."""
        return self.component_manager.get_component(component_cls, qualifier)

    def must_get_component(
        self, component_cls: Type[T], qualifier: Optional[str] = None
    ) -> T:
        """Get a component instance, raising if not found."""
        result = self.get_component(component_cls, qualifier)
        if result is None:
            name = component_cls.__name__
            msg = f"Component {name} not found"
            if qualifier:
                msg += f" with qualifier '{qualifier}'"
            raise LookupError(msg)
        return result

    def register_component(self, component_cls: Type[Component]) -> None:
        """Register a component class in the application context."""
        self.component_manager.register_component(component_cls)

    # Bean management methods
    def get_bean(
        self, object_cls: Type[BT], qualifier: Optional[str] = None
    ) -> Optional[BT]:
        """Get a bean instance by class and optional qualifier."""
        return self.bean_manager.get_bean(object_cls, qualifier)

    def must_get_bean(
        self, object_cls: Type[BT], qualifier: Optional[str] = None
    ) -> BT:
        """Get a bean instance, raising if not found."""
        result = self.get_bean(object_cls, qualifier)
        if result is None:
            name = object_cls.__name__
            msg = f"Bean {name} not found"
            if qualifier:
                msg += f" with qualifier '{qualifier}'"
            raise LookupError(msg)
        return result

    def register_bean_collection(self, bean_cls: Type[BeanCollection]) -> None:
        """Register a bean collection class in the application context."""
        self.bean_manager.register_bean_collection(bean_cls)

    # Properties management methods
    def get_properties(self, properties_cls: Type[PT]) -> Optional[PT]:
        """Get a properties instance by class."""
        return self.properties_manager.get_properties(properties_cls)

    def must_get_properties(self, properties_cls: Type[PT]) -> PT:
        """Get a properties instance, raising if not found."""
        result = self.get_properties(properties_cls)
        if result is None:
            name = properties_cls.__name__
            raise LookupError(f"Properties {name} not found")
        return result

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
        self.container_manager.controller_classes[controller_cls_name] = (
            controller_cls
        )

    def get_controller_instances(self) -> list[RestController]:
        """Get all controller instances."""
        return [
            cls() for cls in self.container_manager.controller_classes.values()
        ]

    def get_singleton_component_instances(self) -> list[Component]:
        """Get all singleton component instances."""
        return list(
            self.container_manager.component_instances.values()
        )

    def get_singleton_bean_instances(self) -> list[object]:
        """Get all singleton bean instances."""
        return list(self.container_manager.bean_instances.values())

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

    def inject_dependencies_for_instance(self, instance: object) -> None:
        """Inject dependencies into a specific instance."""
        self.dependency_injector.inject_dependencies(instance)

    def inject_dependencies_for_external_object(self, target_cls: Type[Any]) -> None:
        """Inject dependencies for an external object (class-level, for middlewares etc.)."""
        self.dependency_injector.inject_dependencies(target_cls)

    def inject_dependencies_for_app_entities(self) -> None:
        """Inject dependencies for all registered singleton component instances."""
        for instance in self.container_manager.component_instances.values():
            self.dependency_injector.inject_dependencies(instance)

    def _validate_starter_dependencies(self, starter: PySpringStarter) -> None:
        """Validate dependencies for a single starter."""
        for dependency in starter.depends_on:
            if not issubclass(dependency, AppEntities):
                error = f"[INVALID DEPENDENCY] Invalid dependency {dependency.__name__} in {starter.__class__.__name__}"
                logger.error(error)
                raise InvalidDependencyError(error)

            if not self.is_within_context(dependency):
                error = f"[INVALID DEPENDENCY] Dependency {dependency.__name__} not found in the application context"
                logger.error(error)
                raise InvalidDependencyError(error)

    def validate_starters(self) -> None:
        """Validate all starters in the application context."""
        for starter in self.starters:
            self._validate_starter_dependencies(starter)
