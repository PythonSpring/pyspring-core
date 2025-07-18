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
        loader = _PropertiesLoader("test.json", mock_properties_classes)  # type: ignore
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
        loader = _PropertiesLoader("test.yaml", mock_properties_classes)  # type: ignore
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
