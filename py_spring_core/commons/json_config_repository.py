import json
from typing import Generic, Optional, Type, TypeVar, get_args

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JsonConfigRepository(Generic[T]):
    """
    A repository for managing JSON-based configuration files. This class provides methods to load, get, and save configuration data from a JSON file.

    The `JsonConfigRepository` class is a generic class that takes a `pydantic.BaseModel` subclass as its type parameter `T`.
    This allows the repository to work with any Pydantic model for the configuration data.

    The class has the following methods:

    - `__init__(self, file_path: str, target_key: Optional[str] = None)`: Initializes the repository with the file path and an optional target key.
    - `_get_model_cls(cls) -> Type[T]`: A class method that returns the Pydantic model class associated with the repository.
    - `get_config(self) -> T`: Returns the current configuration data.
    - `reload_config(self) -> None`: Reloads the configuration data from the file.
    - `save_config(self) -> None`: Saves the current configuration data to the file.
    - `_load_config(self) -> T`: Loads the configuration data from the file.
    """

    def __init__(self, file_path: str, target_key: Optional[str] = None) -> None:
        self.base_model_cls: Type[T] = self.__class__._get_model_cls()
        self.file_path = file_path
        self.target_key = target_key
        self._config: T = self._load_config()

    @classmethod
    def _get_model_cls(cls) -> Type[T]:
        return get_args(cls.__orig_bases__[0])[0]  # type: ignore

    def get_config(self) -> T:
        return self._config

    def reload_config(self) -> None:
        self._config = self._load_config()

    def save_config(self) -> None:
        is_the_same_class = (
            self._config.__class__.__name__ == self.base_model_cls.__name__
        )
        if not is_the_same_class:
            raise TypeError(
                f"[BASE MODEL CLASS TYPE MISMATCH] Base model class of current repository: {self.base_model_cls.__name__} mismatch with config class: {self._config.__class__.__name__}"
            )
        with open(self.file_path, "w") as file:
            file.write(self._config.model_dump_json(indent=4))

    def save_config_to_target_path(self, file_path: str) -> None:
        with open(file_path, "w") as file:
            file.write(self._config.model_dump_json(indent=4))

    def _load_config(self) -> T:
        with open(self.file_path, "r") as file:
            if BaseModel not in self.base_model_cls.__mro__:
                raise TypeError(
                    "[BASE MODEL INHERITANCE REQUIRED] JsonConfigRepository required model class being inherited from pydantic.BaseModel for marshalling JSON into python object."
                )

            if self.target_key is None:
                return self.base_model_cls.model_validate_json(file.read())
            target_py_object = json.loads(file.read())
            if self.target_key not in target_py_object:
                raise ValueError(
                    f"[TARGET KEY NOT FOUND] Target key: {self.target_key} not found"
                )
            return self.base_model_cls.model_validate(target_py_object[self.target_key])
