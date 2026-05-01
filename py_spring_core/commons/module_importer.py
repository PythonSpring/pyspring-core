import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, Iterable, Type, Optional

from loguru import logger


class ModuleImporter:
    """
    A class that handles dynamic module importing with caching capabilities.
    Provides functionality to import modules from file paths and extract classes from them.
    """

    def __init__(self) -> None:
        # Module cache to prevent duplicate imports
        self._module_cache: dict[str, Any] = {}
        # Track module names registered in sys.modules so clear_cache can clean them up
        self._registered_module_names: set[str] = set()

    def import_module_from_path(self, file_path: str) -> Optional[Any]:
        """
        Import a module from a file path with caching.
        
        Args:
            file_path (str): The file path of the module to import.
            
        Returns:
            Optional[Any]: The imported module or None if import fails.
        """
        resolved_path = Path(file_path).resolve()
        cache_key = str(resolved_path)
        module_name = resolved_path.stem
        
        # Check if module is already cached
        if cache_key in self._module_cache:
            logger.debug(f"[MODULE CACHE] Using cached module: {module_name}")
            return self._module_cache[cache_key]

        # Check if already imported by Python's standard import system
        # (e.g., triggered by another module's "from X import Y" statement)
        if module_name in sys.modules:
            logger.debug(f"[MODULE CACHE] Using sys.modules entry for: {module_name}")
            module = sys.modules[module_name]
            self._module_cache[cache_key] = module
            self._registered_module_names.add(module_name)
            return module

        logger.info(f"[MODULE IMPORT] Import module path: {resolved_path}")
        
        # Create a module specification
        spec = importlib.util.spec_from_file_location(module_name, resolved_path)
        if spec is None:
            logger.warning(f"[MODULE IMPORT] Could not create spec for {module_name}")
            return None

        # Create a new module based on the specification
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            logger.warning(f"[MODULE IMPORT] No loader found for {module_name}")
            return None

        # Register in sys.modules BEFORE exec_module so that circular
        # imports within the module resolve to this same object.
        sys.modules[module_name] = module
        self._registered_module_names.add(module_name)

        # Execute the module in its own namespace
        logger.info(f"[MODULE IMPORT] Import module: {module_name}")
        try:
            spec.loader.exec_module(module)
            logger.success(f"[MODULE IMPORT] Successfully imported {module_name}")
            # Cache the module
            self._module_cache[cache_key] = module
            return module
        except Exception as error:
            # Remove from sys.modules on failure to avoid leaving a broken module
            sys.modules.pop(module_name, None)
            self._registered_module_names.discard(module_name)
            logger.warning(f"[MODULE IMPORT] Failed to import {module_name}: {error}")
            raise error

    def extract_classes_from_module(self, module: Any) -> list[Type[object]]:
        """
        Extract all classes from a module.
        
        Args:
            module (Any): The module to extract classes from.
            
        Returns:
            list[Type[object]]: List of classes found in the module.
        """
        loaded_classes = []
        for attr in dir(module):
            obj = getattr(module, attr)
            if attr.startswith("__"):
                continue
            if not inspect.isclass(obj):
                continue
            loaded_classes.append(obj)
        return loaded_classes

    def import_classes_from_paths(
        self, 
        file_paths: Iterable[str], 
        target_subclasses: Iterable[Type[object]] = []
    ) -> set[Type[object]]:
        """
        Import classes from multiple file paths with optional filtering.
        
        Args:
            file_paths (Iterable[str]): The file paths of the modules to import.
            target_subclasses (Iterable[Type[object]], optional): Target subclasses to filter. Defaults to [].
            
        Returns:
            set[Type[object]]: Set of imported classes.
        """
        all_loaded_classes: list[Type[object]] = []

        for file_path in file_paths:
            module = self.import_module_from_path(file_path)
            if module is None:
                raise ImportError(f"Failed to import module from {file_path}")
                
            loaded_classes = self.extract_classes_from_module(module)
            all_loaded_classes.extend(loaded_classes)

        returned_target_classes: set[Type[object]] = set()
        
        # If no target subclasses specified, return all loaded classes
        if not target_subclasses:
            returned_target_classes = set(all_loaded_classes)
        else:
            # Filter classes based on target subclasses
            for target_cls in target_subclasses:
                for loaded_class in all_loaded_classes:
                    if loaded_class in target_subclasses:
                        continue
                    if issubclass(loaded_class, target_cls):
                        returned_target_classes.add(loaded_class)

        return returned_target_classes

    def clear_cache(self) -> None:
        """Clear the module cache and remove registered entries from sys.modules."""
        for module_name in self._registered_module_names:
            sys.modules.pop(module_name, None)
        self._registered_module_names.clear()
        self._module_cache.clear()

    def get_cache_size(self) -> int:
        """Get the number of cached modules."""
        return len(self._module_cache) 