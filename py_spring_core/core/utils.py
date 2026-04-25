import importlib
import inspect
import pkgutil
from abc import ABC
from types import ModuleType
from typing import Any, Iterable, Type

from loguru import logger

from ..commons.module_importer import ModuleImporter
from ..core.starter.py_spring_starter import PySpringStarter

# Global module importer instance
_module_importer = ModuleImporter()


def dynamically_import_modules(
    module_paths: Iterable[str],
    target_subclasses: Iterable[Type[object]] = [],
) -> set[Type[object]]:
    """
    Dynamically imports modules from the specified file paths.

    Args:
        module_paths (Iterable[str]): The file paths of the modules to import.
        is_ignore_error (bool, optional): Whether to ignore any errors that occur during the import process. Defaults to True.
        target_subclasses (Iterable[Type[object]], optional): Target subclasses to filter. Defaults to [].

    Raises:
        Exception: If an error occurs during the import process and `is_ignore_error` is False.
    """
    return _module_importer.import_classes_from_paths(
        file_paths=module_paths,
        target_subclasses=target_subclasses,
    )


def clear_module_cache() -> None:
    """Clear the global module cache. Useful for testing or when you need to force re-import."""
    _module_importer.clear_cache()


def get_unimplemented_abstract_methods(cls: Type[Any]) -> set[str]:
    """
    Returns a set of abstract method names not implemented in the given class.
    Args:
        cls (Type[Any]): A subclass of abc.ABC

    Returns:
        set[str]: A set of method names that are abstract but not yet implemented
    """
    if not isinstance(cls, type):
        raise TypeError("Expected a class type.")

    if not issubclass(cls, ABC):
        raise TypeError("Expected a subclass of abc.ABC.")

    abstract_methods: set[str] = set()
    for base in cls.__mro__:
        base_abstracts = getattr(base, "__abstractmethods__", set())
        abstract_methods = abstract_methods.union(base_abstracts)

    implemented_methods: set[str] = {
        attr
        for attr in dir(cls)
        if callable(getattr(cls, attr))
        and not getattr(getattr(cls, attr), "__isabstractmethod__", False)
    }

    return abstract_methods.difference(implemented_methods)


def discover_starters_from_packages(
    package_names: Iterable[str],
) -> list[Type[PySpringStarter]]:
    """
    Dynamically import packages by name and discover all PySpringStarter subclasses.

    Recursively walks each package's sub-modules, inspects every class, and
    collects concrete PySpringStarter subclasses.

    Args:
        package_names: Dotted package names to scan (e.g. ["my_starter_pkg"]).

    Returns:
        A list of PySpringStarter subclasses found across all packages.
    """
    discovered: list[Type[PySpringStarter]] = []
    seen: set[Type[PySpringStarter]] = set()

    for package_name in package_names:
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.warning(
                f"[STARTER DISCOVERY] Failed to import package: {package_name}"
            )
            continue

        modules_to_inspect: list[ModuleType] = [package]

        # Walk sub-modules if the package has a __path__
        package_path = getattr(package, "__path__", None)
        if package_path is not None:
            for _importer, module_name, _is_pkg in pkgutil.walk_packages(
                package_path, prefix=package.__name__ + "."
            ):
                try:
                    sub_module = importlib.import_module(module_name)
                    modules_to_inspect.append(sub_module)
                except Exception as e:
                    logger.warning(
                        f"[STARTER DISCOVERY] Failed to import sub-module {module_name}: {e}"
                    )
                    continue

        for module in modules_to_inspect:
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, PySpringStarter)
                    and obj is not PySpringStarter
                    and obj not in seen
                ):
                    seen.add(obj)
                    discovered.append(obj)

    return discovered
