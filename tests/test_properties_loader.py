import pytest
from pytest_mock import MockerFixture

from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.entities.properties.properties_loader import (
    InvalidPropertiesKeyError,
    _PropertiesLoader,
)


class TestPropertiesLoader:
    @pytest.fixture
    def mock_properties_classes(self) -> list[type[Properties]]:
        class MockProperties(Properties):
            __key__ = "mock_properties"
            attr: str

        return [MockProperties]

    def test_load_properties_from_valid_json_file(
        self, mocker: MockerFixture, mock_properties_classes: list[type[Properties]]
    ):
        mocker.patch(
            "builtins.open",
            mocker.mock_open(read_data='{"mock_properties": {"attr": "value"}}'),
        )
        mocker.patch("json.loads", return_value={"mock_properties": {"attr": "value"}})
        loader = _PropertiesLoader("test.json", mock_properties_classes)
        properties = loader.load_properties()

        assert "mock_properties" in properties
        assert isinstance(properties["mock_properties"], mock_properties_classes[-1])

    def test_load_properties_from_valid_yaml_file(
        self, mocker: MockerFixture, mock_properties_classes: list[type[Properties]]
    ):
        mocker.patch(
            "builtins.open",
            mocker.mock_open(read_data="mock_properties:\n  attr: value"),
        )
        mocker.patch("yaml.load", return_value={"mock_properties": {"attr": "value"}})
        loader = _PropertiesLoader("test.yaml", mock_properties_classes)
        properties = loader.load_properties()

        assert "mock_properties" in properties
        assert isinstance(properties["mock_properties"], mock_properties_classes[-1])

    def test_handle_valid_file_paths_with_correct_extensions(
        self, mocker: MockerFixture
    ):
        mocker.patch("builtins.open", mocker.mock_open(read_data=""))

        file_extensions = ["json", "yaml", "yml"]
        for extension in file_extensions:
            loader = _PropertiesLoader(f"test.{extension}", [])
            assert loader.file_extension == extension

    def test_load_properties_from_file_without_extension(self):
        with pytest.raises(ValueError, match="no file extension found"):
            _PropertiesLoader("testfile", [])

    def test_load_properties_from_unsupported_extension(self, mocker: MockerFixture):
        mocker.patch("builtins.open", mocker.mock_open(read_data="{}"))
        with pytest.raises(ValueError, match="Unsupported file extension"):
            loader = _PropertiesLoader("test.txt", [])
            loader._load_properties_dict_from_file_content(
                loader.file_extension, loader.properties_file_content
            )

    def test_load_properties_with_invalid_keys(self, mocker: MockerFixture):
        mocker.patch(
            "builtins.open",
            mocker.mock_open(read_data='{"invalid_key": {"attr": "value"}}'),
        )
        mocker.patch("json.loads", return_value={"invalid_key": {"attr": "value"}})
        properties_classes = [mocker.Mock(spec=Properties, __key__="valid_key")]
        loader = _PropertiesLoader("test.json", properties_classes)
        with pytest.raises(InvalidPropertiesKeyError, match="Invalid properties key"):
            loader.load_properties()

    def test_handle_empty_properties_file_content(self, mocker: MockerFixture):
        mocker.patch("builtins.open", mocker.mock_open(read_data=""))
        mocker.patch("json.loads", return_value={})
        loader = _PropertiesLoader("test.json", [])
        properties = loader.load_properties()
        assert properties == {}


import json
import os
import tempfile


class TestPropertiesLoaderEnvVarResolution:
    def _create_temp_file(self, content: str, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_env_vars_resolved_in_yaml(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TEST_DB_HOST", "prod-server")
        monkeypatch.setenv("TEST_DB_PORT", "3306")

        class DbProps(Properties):
            __key__ = "database"
            host: str
            port: int

        content = "database:\n  host: ${TEST_DB_HOST}\n  port: ${TEST_DB_PORT}\n"
        path = self._create_temp_file(content, ".yaml")

        try:
            loader = _PropertiesLoader(path, [DbProps])
            result = loader.load_properties()
            assert result["database"].host == "prod-server"
            assert result["database"].port == 3306
        finally:
            os.unlink(path)

    def test_env_vars_with_defaults_in_json(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("OPTIONAL_HOST", raising=False)

        class ServerProps(Properties):
            __key__ = "server"
            host: str
            port: int

        content = json.dumps({
            "server": {"host": "${OPTIONAL_HOST:localhost}", "port": 8080}
        })
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [ServerProps])
            result = loader.load_properties()
            assert result["server"].host == "localhost"
            assert result["server"].port == 8080
        finally:
            os.unlink(path)

    def test_missing_env_var_raises_in_loader(self, monkeypatch: pytest.MonkeyPatch):
        from py_spring_core.core.entities.properties.env_var_resolver import (
            EnvVarNotFoundError,
        )

        monkeypatch.delenv("REQUIRED_SECRET", raising=False)

        class SecretProps(Properties):
            __key__ = "secrets"
            api_key: str

        content = json.dumps({"secrets": {"api_key": "${REQUIRED_SECRET}"}})
        path = self._create_temp_file(content, ".json")

        try:
            loader = _PropertiesLoader(path, [SecretProps])
            with pytest.raises(EnvVarNotFoundError, match="REQUIRED_SECRET"):
                loader.load_properties()
        finally:
            os.unlink(path)
