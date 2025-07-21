from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from py_spring_core.commons.json_config_repository import JsonConfigRepository
from py_spring_core.core.application.loguru_config import LoguruConfig


class ServerConfig(BaseModel):
    """
    Represents the configuration for the application server.

    Attributes:
        host: The host address for the server.
        port: The port number for the server.
        enabled: A boolean flag indicating whether the server is enabled.
    """

    host: str
    port: int
    enabled: bool = Field(default=True)


class ShutdownConfig(BaseModel):
    """
    Represents the configuration for graceful shutdown.

    Attributes:
        timeout_seconds: The maximum time in seconds to wait for graceful shutdown before forcing termination.
        enabled: A boolean flag indicating whether graceful shutdown timeout is enabled.
    """

    timeout_seconds: float = Field(default=30.0, description="Timeout in seconds for graceful shutdown")
    enabled: bool = Field(default=True, description="Whether graceful shutdown timeout is enabled")


class ApplicationConfig(BaseModel):
    """
    Represents the configuration for the application.

    Attributes:
        app_src_target_dir: The directory where the application source code is located.
        server_config: The configuration for the application server.
        sqlalchemy_database_uri: The URI for the SQLAlchemy database connection.
        properties_file_path: The file path for the application properties.
        model_file_postfix_patterns: A list of file name patterns for model (for table creation) files.
        shutdown_config: The configuration for graceful shutdown.
    """

    model_config = ConfigDict(protected_namespaces=())

    app_src_target_dir: str
    exclude_file_patterns: list[str] = Field(default_factory=lambda: [r".*/models\.py$"])
    server_config: ServerConfig
    properties_file_path: str
    loguru_config: LoguruConfig
    shutdown_config: ShutdownConfig = Field(default_factory=ShutdownConfig)


class ApplicationConfigRepository(JsonConfigRepository[ApplicationConfig]):
    """
    Represents a repository for managing the application configuration, which is stored in a JSON file.
    """

    ...
