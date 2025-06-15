import json
from typing import Any, Callable, Optional, Type

import cachetools
import yaml

from py_spring_core.core.entities.properties.properties import Properties


class InvalidPropertiesKeyError(Exception): ...


class _PropertiesLoader:
    """
    Provides a utility class `_PropertiesLoader` to load and validate properties from a file.
    The `_PropertiesLoader` class is responsible for loading properties from a file, validating them against a set of known `Properties` classes, and providing access to the loaded properties.
    The class supports loading properties from JSON or YAML files, and raises appropriate errors if the file extension is unsupported or the properties keys are invalid.
    The `load_properties` method returns a dictionary of `Properties` instances, where the keys match the keys in the properties file.
    The `get_properties` method provides a way to retrieve a specific `Properties` instance by its key, if it has been previously loaded.
    """

    optional_loaded_properties: dict[str, Properties] = {}

    def __init__(
        self, properties_path: str, properties_classes: list[Type[Properties]]
    ) -> None:
        self.properties_path = properties_path
        self.file_extension = self._get_file_extension(properties_path)
        self.properties_file_content = self._read_properties_file_content(
            self.properties_path
        )
        self.properties_classes = properties_classes
        self.properties_class_map = self._load_classes_as_map()

        self.extension_loader_lookup: dict[str, Callable[[str], dict[str, Any]]] = {
            "json": json.loads,
            "yaml": yaml.safe_load,
            "yml": yaml.safe_load,
        }

    def _get_file_extension(self, file_path: str) -> str:
        _id = "."
        if _id not in file_path:
            raise ValueError(
                f"[UNABLE TO LOAD PROPERTIES] Invalid file path: {file_path}, no file extension found"
            )

        return file_path.split(_id)[-1]

    def _read_properties_file_content(self, file_path: str) -> str:
        with open(file_path, "r") as file:
            return file.read()

    def _load_classes_as_map(self) -> dict[str, Type[Properties]]:
        return {_cls.get_key(): _cls for _cls in self.properties_classes}

    @cachetools.cached(cache={})
    def _load_properties_dict_from_file_content(
        self, file_extension: str, file_content: str
    ) -> dict[str, dict]:
        for extension, loader_func in self.extension_loader_lookup.items():
            if file_extension != extension:
                continue
            return loader_func(file_content)
        raise ValueError(
            f"[INVALID FILE EXTENSION] Unsupported file extension: {file_extension}"
        )

    @property
    def available_properties_keys(self) -> list[str]:
        return list(map(str, self.properties_class_map.keys()))

    def load_properties(self) -> dict[str, Properties]:
        properties_dict = self._load_properties_dict_from_file_content(
            self.file_extension, self.properties_file_content
        )
        properties: dict[str, Properties] = {}
        for key, value in properties_dict.items():
            if key not in self.properties_class_map.keys():
                raise InvalidPropertiesKeyError(
                    f"[INVALID PROPERTIES KEY] Invalid properties key: {key}, please enter one of the following [{','.join(self.available_properties_keys)}]"
                )
            properties_cls = self.properties_class_map[key]
            properties[key] = properties_cls.model_validate(value)
        return properties

    @classmethod
    def get_properties(cls, _key: str) -> Optional[Properties]:
        if cls.optional_loaded_properties is None:
            raise ValueError("[PROPERTIES NOT LOADED] Properties not loaded yet")
        return cls.optional_loaded_properties.get(_key)
