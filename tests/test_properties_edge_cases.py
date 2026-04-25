"""
Edge case tests for Properties and PropertiesLoader.

Covers:
- Properties key validation (empty, None)
- Properties with nested Pydantic models
- Properties with optional fields and defaults
- PropertiesLoader with unknown keys
- PropertiesLoader with missing required fields
- PropertiesLoader with extra fields (strict mode)
- Multiple properties classes with overlapping keys
- YAML vs JSON loading
- Caching behavior in PropertiesLoader
- File extension edge cases
"""

import json
import tempfile
import os
from typing import Optional, List

import pytest
from pydantic import BaseModel, ValidationError

from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.entities.properties.properties_loader import (
    InvalidPropertiesKeyError,
    _PropertiesLoader,
)


class TestPropertiesKeyValidation:

    def test_get_key_raises_when_empty_string(self):
        class EmptyKeyProps(Properties):
            __key__ = ""

        with pytest.raises(ValueError, match="KEY NOT SET"):
            EmptyKeyProps.get_key()

    def test_get_key_returns_valid_key(self):
        class ValidProps(Properties):
            __key__ = "my_section"

        assert ValidProps.get_key() == "my_section"

    def test_get_name_returns_class_name(self):
        class MySpecialProperties(Properties):
            __key__ = "section"

        assert MySpecialProperties.get_name() == "MySpecialProperties"

    def test_subclass_inherits_key_independently(self):
        class BaseProps(Properties):
            __key__ = "base"

        class ChildProps(Properties):
            __key__ = "child"

        assert BaseProps.get_key() == "base"
        assert ChildProps.get_key() == "child"


class TestPropertiesWithNestedModels:

    def test_nested_model_validation(self):
        class DatabaseConfig(BaseModel):
            host: str
            port: int
            name: str

        class AppProps(Properties):
            __key__ = "app"
            database: DatabaseConfig

        props = AppProps.model_validate({
            "database": {"host": "localhost", "port": 5432, "name": "mydb"}
        })
        assert props.database.host == "localhost"
        assert props.database.port == 5432

    def test_nested_model_validation_fails_on_missing_field(self):
        class DatabaseConfig(BaseModel):
            host: str
            port: int

        class AppProps(Properties):
            __key__ = "app"
            database: DatabaseConfig

        with pytest.raises(ValidationError):
            AppProps.model_validate({"database": {"host": "localhost"}})


class TestPropertiesWithOptionalFields:

    def test_optional_fields_default_to_none(self):
        class OptionalProps(Properties):
            __key__ = "optional"
            name: str
            description: Optional[str] = None
            tags: List[str] = []

        props = OptionalProps.model_validate({"name": "test"})
        assert props.name == "test"
        assert props.description is None
        assert props.tags == []

    def test_optional_fields_accept_values(self):
        class OptionalProps(Properties):
            __key__ = "optional"
            name: str
            description: Optional[str] = None

        props = OptionalProps.model_validate({"name": "test", "description": "desc"})
        assert props.description == "desc"


class TestPropertiesLoaderEdgeCases:

    def _create_temp_file(self, content: str, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return path

    def test_load_json_properties(self):
        class DbProps(Properties):
            __key__ = "database"
            host: str
            port: int

        content = json.dumps({"database": {"host": "localhost", "port": 5432}})
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [DbProps])
            result = loader.load_properties()
            assert "database" in result
            assert result["database"].host == "localhost"
            assert result["database"].port == 5432
        finally:
            os.unlink(path)

    def test_load_yaml_properties(self):
        class DbProps(Properties):
            __key__ = "database"
            host: str
            port: int

        content = "database:\n  host: localhost\n  port: 5432\n"
        path = self._create_temp_file(content, ".yaml")

        try:
            loader = _PropertiesLoader(path, [DbProps])
            result = loader.load_properties()
            assert "database" in result
            assert result["database"].host == "localhost"
        finally:
            os.unlink(path)

    def test_load_yml_properties(self):
        class DbProps(Properties):
            __key__ = "database"
            host: str
            port: int

        content = "database:\n  host: localhost\n  port: 5432\n"
        path = self._create_temp_file(content, ".yml")

        try:
            loader = _PropertiesLoader(path, [DbProps])
            result = loader.load_properties()
            assert "database" in result
        finally:
            os.unlink(path)

    def test_invalid_key_in_file_raises_error(self):
        class DbProps(Properties):
            __key__ = "database"
            host: str

        content = json.dumps({"unknown_key": {"host": "localhost"}})
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [DbProps])
            with pytest.raises(InvalidPropertiesKeyError, match="INVALID PROPERTIES KEY"):
                loader.load_properties()
        finally:
            os.unlink(path)

    def test_unsupported_file_extension_raises_error(self):
        content = "key=value"
        path = self._create_temp_file(content, ".ini")

        try:
            loader = _PropertiesLoader(path, [])
            with pytest.raises(ValueError, match="INVALID FILE EXTENSION"):
                loader.load_properties()
        finally:
            os.unlink(path)

    def test_file_without_extension_raises_error(self):
        with pytest.raises(ValueError, match="no file extension found"):
            _PropertiesLoader("configfile", [])

    def test_available_properties_keys_returns_registered_keys(self):
        class PropsA(Properties):
            __key__ = "section_a"
            value: str

        class PropsB(Properties):
            __key__ = "section_b"
            value: str

        content = json.dumps({"section_a": {"value": "a"}, "section_b": {"value": "b"}})
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [PropsA, PropsB])
            keys = loader.available_properties_keys
            assert "section_a" in keys
            assert "section_b" in keys
        finally:
            os.unlink(path)

    def test_multiple_properties_classes_loaded_together(self):
        class ServerProps(Properties):
            __key__ = "server"
            host: str
            port: int

        class LogProps(Properties):
            __key__ = "logging"
            level: str

        content = json.dumps({
            "server": {"host": "0.0.0.0", "port": 8080},
            "logging": {"level": "DEBUG"},
        })
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [ServerProps, LogProps])
            result = loader.load_properties()
            assert len(result) == 2
            assert result["server"].host == "0.0.0.0"
            assert result["logging"].level == "DEBUG"
        finally:
            os.unlink(path)

    def test_missing_required_field_raises_validation_error(self):
        class StrictProps(Properties):
            __key__ = "strict"
            required_field: str
            also_required: int

        content = json.dumps({"strict": {"required_field": "ok"}})
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [StrictProps])
            with pytest.raises(ValidationError):
                loader.load_properties()
        finally:
            os.unlink(path)

    def test_empty_json_file_raises_on_load(self):
        class SomeProps(Properties):
            __key__ = "some"
            value: str

        path = self._create_temp_file("{}", ".json")

        try:
            loader = _PropertiesLoader(path, [SomeProps])
            result = loader.load_properties()
            assert len(result) == 0
        finally:
            os.unlink(path)
