from abc import ABC
from typing import Any, Iterable, Type

from loguru import logger

from ..commons.module_importer import ModuleImporter

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
