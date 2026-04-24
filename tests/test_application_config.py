import pytest
from pydantic import ValidationError

from py_spring_core.core.application.application_config import (
    ApplicationConfig,
    ShutdownConfig,
    ServerConfig,
    LoguruConfig,
)
from py_spring_core.core.application.loguru_config import LogLevel


class TestShutdownConfig:
    """Test suite for the ShutdownConfig class."""

    def test_shutdown_config_defaults(self):
        """Test that ShutdownConfig has correct default values."""
        config = ShutdownConfig()
        
        assert config.timeout_seconds == 30.0
        assert config.enabled is True

    def test_shutdown_config_custom_values(self):
        """Test ShutdownConfig with custom values."""
        config = ShutdownConfig(timeout_seconds=60.0, enabled=False)
        
        assert config.timeout_seconds == 60.0
        assert config.enabled is False

    def test_shutdown_config_validation(self):
        """Test ShutdownConfig validation."""
        # Valid timeout values
        config = ShutdownConfig(timeout_seconds=0.1)
        assert config.timeout_seconds == 0.1
        
        config = ShutdownConfig(timeout_seconds=1000.0)
        assert config.timeout_seconds == 1000.0

    def test_shutdown_config_type_validation(self):
        """Test that ShutdownConfig validates types correctly."""
        # Should accept float or int for timeout_seconds
        config = ShutdownConfig(timeout_seconds=30)
        assert config.timeout_seconds == 30.0
        
        config = ShutdownConfig(timeout_seconds=30.5)
        assert config.timeout_seconds == 30.5
        
        # Should accept boolean for enabled
        config = ShutdownConfig(enabled=True)
        assert config.enabled is True
        
        config = ShutdownConfig(enabled=False)
        assert config.enabled is False

    def test_shutdown_config_serialization(self):
        """Test that ShutdownConfig can be serialized/deserialized."""
        config = ShutdownConfig(timeout_seconds=45.0, enabled=True)
        
        # Test model dump
        config_dict = config.model_dump()
        expected = {"timeout_seconds": 45.0, "enabled": True}
        assert config_dict == expected
        
        # Test reconstruction from dict
        new_config = ShutdownConfig(**config_dict)
        assert new_config.timeout_seconds == 45.0
        assert new_config.enabled is True


class TestApplicationConfigWithShutdown:
    """Test suite for ApplicationConfig with shutdown configuration."""

    def test_application_config_with_default_shutdown(self):
        """Test that ApplicationConfig includes default shutdown config."""
        config = ApplicationConfig(
            app_src_target_dir="./src",
            server_config=ServerConfig(host="localhost", port=8000),
            properties_file_path="./app.properties",
            loguru_config=LoguruConfig(log_file_path="./logs/app.log")
        )
        
        # Should have default shutdown config
        assert config.shutdown_config is not None
        assert config.shutdown_config.timeout_seconds == 30.0
        assert config.shutdown_config.enabled is True

    def test_application_config_with_custom_shutdown(self):
        """Test ApplicationConfig with custom shutdown configuration."""
        custom_shutdown = ShutdownConfig(timeout_seconds=60.0, enabled=False)
        
        config = ApplicationConfig(
            app_src_target_dir="./src",
            server_config=ServerConfig(host="localhost", port=8000),
            properties_file_path="./app.properties",
            loguru_config=LoguruConfig(log_file_path="./logs/app.log"),
            shutdown_config=custom_shutdown
        )
        
        assert config.shutdown_config.timeout_seconds == 60.0
        assert config.shutdown_config.enabled is False

    def test_application_config_serialization_with_shutdown(self):
        """Test ApplicationConfig serialization includes shutdown config."""
        config = ApplicationConfig(
            app_src_target_dir="./src",
            server_config=ServerConfig(host="localhost", port=8000),
            properties_file_path="./app.properties",
            loguru_config=LoguruConfig(log_file_path="./logs/app.log"),
            shutdown_config=ShutdownConfig(timeout_seconds=45.0, enabled=True)
        )
        
        config_dict = config.model_dump()
        
        assert "shutdown_config" in config_dict
        assert config_dict["shutdown_config"]["timeout_seconds"] == 45.0
        assert config_dict["shutdown_config"]["enabled"] is True

    def test_application_config_from_dict_with_shutdown(self):
        """Test ApplicationConfig reconstruction from dict with shutdown config."""
        config = ApplicationConfig(
            app_src_target_dir="./src",
            server_config=ServerConfig(host="localhost", port=8000),
            properties_file_path="./app.properties",
            loguru_config=LoguruConfig(log_file_path="./logs/app.log", log_level=LogLevel.INFO),
            shutdown_config=ShutdownConfig(timeout_seconds=25.0, enabled=False),
        )

        assert config.app_src_target_dir == "./src"
        assert config.shutdown_config.timeout_seconds == 25.0
        assert config.shutdown_config.enabled is False

    def test_application_config_without_shutdown_config_in_dict(self):
        """Test that ApplicationConfig uses default shutdown when not provided."""
        config = ApplicationConfig(
            app_src_target_dir="./src",
            server_config=ServerConfig(host="localhost", port=8000),
            properties_file_path="./app.properties",
            loguru_config=LoguruConfig(log_file_path="./logs/app.log", log_level=LogLevel.INFO),
        )
        
        # Should use default shutdown config
        assert config.shutdown_config.timeout_seconds == 30.0
        assert config.shutdown_config.enabled is True 