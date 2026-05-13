"""
Tests for starters exposing derived objects via BeanCollection.

Scenario: A starter (e.g., pyspring-model) accepts user-input Properties
(like database host/port) and exposes a derived object (like DataSourceConfig)
that other Components can inject — without the user needing to define that
derived object themselves.
"""

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection.bean_collection import BeanCollection
from py_spring_core.core.entities.component.component import Component
from py_spring_core.core.entities.properties.properties import Properties
from py_spring_core.core.starter.py_spring_starter import PySpringStarter


# --- Domain types ---


class DatabaseProperties(Properties):
    __key__ = "database"
    host: str = "localhost"
    port: int = 5432
    db_name: str = "test_db"


class DataSourceConfig:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string


class DataSourceBeanCollection(BeanCollection):
    db_props: DatabaseProperties

    @classmethod
    def create_data_source_config(cls) -> DataSourceConfig:
        props = cls.db_props
        conn_str = f"postgresql://{props.host}:{props.port}/{props.db_name}"
        return DataSourceConfig(connection_string=conn_str)


class DatabaseStarter(PySpringStarter):
    def on_configure(self) -> None:
        self.properties_classes.append(DatabaseProperties)
        self.bean_collection_classes.append(DataSourceBeanCollection)


class UserRepository(Component):
    data_source: DataSourceConfig


# --- Fixtures ---


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI) -> ApplicationContext:
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server)


# --- Tests ---


class TestStarterExposedBeans:
    """Starter registers Properties + BeanCollection; derived bean is injectable."""

    def test_starter_bean_collection_produces_injectable_bean(
        self, app_context: ApplicationContext
    ):
        starter = DatabaseStarter()
        starter.on_configure()

        props = DatabaseProperties(host="db.example.com", port=3306, db_name="mydb")
        app_context.container_manager.properties_classes["database"] = DatabaseProperties
        app_context.container_manager.properties_instances["database"] = props

        app_context.register_bean_collection(DataSourceBeanCollection)
        app_context.register_component(UserRepository)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        repo = app_context.get_component(UserRepository)
        assert repo is not None
        assert repo.data_source.connection_string == "postgresql://db.example.com:3306/mydb"

    def test_derived_bean_uses_default_properties(
        self, app_context: ApplicationContext
    ):
        props = DatabaseProperties()
        app_context.container_manager.properties_classes["database"] = DatabaseProperties
        app_context.container_manager.properties_instances["database"] = props

        app_context.register_bean_collection(DataSourceBeanCollection)
        app_context.init_ioc_container()

        bean = app_context.get_bean(DataSourceConfig)
        assert bean is not None
        assert bean.connection_string == "postgresql://localhost:5432/test_db"

    def test_multiple_components_share_same_derived_bean(
        self, app_context: ApplicationContext
    ):
        class AnotherRepo(Component):
            data_source: DataSourceConfig

        props = DatabaseProperties(host="shared-host", port=5432, db_name="shared_db")
        app_context.container_manager.properties_classes["database"] = DatabaseProperties
        app_context.container_manager.properties_instances["database"] = props

        app_context.register_bean_collection(DataSourceBeanCollection)
        app_context.register_component(UserRepository)
        app_context.register_component(AnotherRepo)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        repo1 = app_context.get_component(UserRepository)
        repo2 = app_context.get_component(AnotherRepo)
        assert repo1 is not None
        assert repo2 is not None
        assert repo1.data_source is repo2.data_source

    def test_get_entities_includes_properties_and_bean_collection(self):
        starter = DatabaseStarter()
        starter.on_configure()
        entities = starter.get_entities()
        assert DatabaseProperties in entities
        assert DataSourceBeanCollection in entities

    def test_starter_on_configure_registers_both_types(self):
        starter = DatabaseStarter()
        assert len(starter.properties_classes) == 0
        assert len(starter.bean_collection_classes) == 0

        starter.on_configure()

        assert DatabaseProperties in starter.properties_classes
        assert DataSourceBeanCollection in starter.bean_collection_classes
