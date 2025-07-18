import ast
from typing import Any, Iterable, Type

from loguru import logger

from .module_importer import ModuleImporter


class ClassScanner:
    """
    A class that scans Python files and extracts the classes defined within them.
    The `ClassScanner` class provides methods to scan a set of file paths, extract the classes defined in those files, and retrieve the extracted classes.
    The main functionality is provided by the `scan_classes_for_file_paths()` method, which scans the specified file paths and stores the extracted classes in the `scanned_classes` attribute.
    The `get_classes()` method can then be used to retrieve all the extracted classes.
    The `extract_classes_from_file()` method is responsible for extracting the classes from a single file, and the `import_class_from_file()` method is used to import a class from a file.
    """

    def __init__(self, file_paths: Iterable[str]) -> None:
        self.file_paths = file_paths
        self.scanned_classes: dict[str, dict[str, Type[object]]] = {}
        # Use ModuleImporter for handling module imports
        self._module_importer = ModuleImporter()

    def extract_classes_from_file(self, file_path: str) -> dict[str, Type[object]]:
        with open(file_path, "r") as file:
            file_content: str = file.read()
            return self._extract_classes_from_file_content(file_path, file_content)

    def _extract_classes_from_file_content(
        self, file_path: str, file_content: str
    ) -> dict[str, Type[object]]:
        class_objects: dict[str, Type[object]] = {}
        tree = ast.parse(file_content)
        class_names: list[str] = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for class_name in class_names:
            if class_name in class_objects:
                logger.warning(
                    f"[DUPLICATED CLASS IMPORT] Duplicate class name found in file {file_path}: {class_name}"
                )
                continue

            class_obj = self.import_class_from_file(file_path, class_name)
            if class_obj:
                class_objects[class_name] = class_obj

        return class_objects

    def scan_classes_for_file_paths(self) -> None:
        for file_path in self.file_paths:
            object_cls_dict: dict[str, Type[object]] = self.extract_classes_from_file(
                file_path
            )
            self.scanned_classes[file_path] = object_cls_dict

    def import_class_from_file(
        self, file_path: str, class_name: str
    ) -> Type[object] | None:
        # Use ModuleImporter to handle module import
        module = self._module_importer.import_module_from_path(file_path)
        if module is None:
            return None
            
        cls = getattr(module, class_name, None)
        return cls

    def get_classes(self) -> Iterable[Type[object]]:
        classes: list[Type[object]] = []
        for file_path, class_dict in self.scanned_classes.items():
            for object_cls in class_dict.values():
                classes.append(object_cls)
        return classes

    def display_classes(self) -> None:
        repr = "\n"
        for file_path, class_dict in self.scanned_classes.items():
            repr += f"File: {file_path}\n"
            for class_name in class_dict:
                repr += f"  Class: {class_name}\n"

        logger.debug(repr)

    def clear_module_cache(self) -> None:
        """Clear the module cache. Useful for testing or when you need to force re-import."""
        self._module_importer.clear_cache()

    def get_cache_size(self) -> int:
        """Get the number of cached modules."""
        return self._module_importer.get_cache_size()
