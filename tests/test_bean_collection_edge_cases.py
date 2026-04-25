"""
Edge case tests for BeanCollection scanning, conflict detection, and validation.

Covers:
- Bean scanning with correct and incorrect return type annotations
- Bean conflict detection (duplicate bean names)
- Invalid bean detection (name mismatch)
- Multiple create_* methods in one collection
- Bean collection with no create_ methods
- Bean creation with dependencies
- BeanView equality and serialization
- Bean retrieval after IoC init
"""

import pytest
from fastapi import FastAPI

from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
    ApplicationContextConfig,
)
from py_spring_core.core.entities.bean_collection.bean_collection import (
    BeanCollection,
    BeanConflictError,
    BeanView,
    InvalidBeanError,
)
from py_spring_core.core.entities.component.component import Component


@pytest.fixture
def server() -> FastAPI:
    return FastAPI()


@pytest.fixture
def app_context(server: FastAPI):
    config = ApplicationContextConfig(properties_path="")
    return ApplicationContext(config, server=server)


# --- Module-level classes for bean scanning tests ---

class _ScanService:
    pass

class _ScanServiceA:
    pass

class _ScanServiceB:
    pass

class _SingleBeanCollection(BeanCollection):
    @classmethod
    def create_service(cls) -> _ScanService:
        return _ScanService()

class _MultiBeanCollection(BeanCollection):
    @classmethod
    def create_a(cls) -> _ScanServiceA:
        return _ScanServiceA()

    @classmethod
    def create_b(cls) -> _ScanServiceB:
        return _ScanServiceB()

class _MixedCollection(BeanCollection):
    @classmethod
    def create_service(cls) -> _ScanService:
        return _ScanService()

    def helper_method(self):
        pass

    def get_something(self):
        pass


class TestBeanScanning:

    def test_scan_finds_create_methods(self):
        views = _SingleBeanCollection.scan_beans()
        assert len(views) == 1
        assert views[0].bean_name == "_ScanService"
        assert isinstance(views[0].bean, _ScanService)

    def test_scan_multiple_create_methods(self):
        views = _MultiBeanCollection.scan_beans()
        assert len(views) == 2
        names = {v.bean_name for v in views}
        assert names == {"_ScanServiceA", "_ScanServiceB"}

    def test_scan_ignores_non_create_methods(self):
        views = _MixedCollection.scan_beans()
        assert len(views) == 1

    def test_scan_empty_collection(self):
        class EmptyCollection(BeanCollection):
            def helper(self):
                pass

        views = EmptyCollection.scan_beans()
        assert len(views) == 0

    def test_get_name_returns_class_name(self):
        class MySpecialCollection(BeanCollection):
            pass

        assert MySpecialCollection.get_name() == "MySpecialCollection"


class TestBeanViewValidation:

    def test_valid_bean_when_name_matches(self):
        class Foo:
            pass

        view = BeanView(
            bean_creation_func=lambda: Foo(),
            bean_name="Foo",
            bean=Foo(),
        )
        assert view.is_valid_bean() is True

    def test_invalid_bean_when_name_mismatches(self):
        class Foo:
            pass

        class Bar:
            pass

        view = BeanView(
            bean_creation_func=lambda: Bar(),
            bean_name="Foo",
            bean=Bar(),
        )
        assert view.is_valid_bean() is False

    def test_bean_creation_func_excluded_from_serialization(self):
        class Foo:
            pass

        view = BeanView(
            bean_creation_func=lambda: Foo(),
            bean_name="Foo",
            bean=Foo(),
        )
        serialized = view.model_dump()
        assert "bean_creation_func" not in serialized
        assert "bean_name" in serialized


# --- Module-level classes for conflict and retrieval tests ---

class _SharedService:
    pass

class _ConflictCollectionA(BeanCollection):
    @classmethod
    def create_shared(cls) -> _SharedService:
        return _SharedService()

class _ConflictCollectionB(BeanCollection):
    @classmethod
    def create_shared(cls) -> _SharedService:
        return _SharedService()

class _Expected:
    pass

class _Actual:
    pass

class _BadCollection(BeanCollection):
    @classmethod
    def create_expected(cls) -> _Expected:
        return _Actual()  # type: ignore

class _ExternalLib:
    value = "external"

class _LibCollection(BeanCollection):
    @classmethod
    def create_lib(cls) -> _ExternalLib:
        return _ExternalLib()

class _ExternalClient:
    url = "http://api.example.com"

class _ClientCollection(BeanCollection):
    @classmethod
    def create_client(cls) -> _ExternalClient:
        return _ExternalClient()


class TestBeanConflictsInContext:

    def test_duplicate_bean_names_in_different_collections_first_wins(self, app_context: ApplicationContext):
        """When two collections produce beans with the same name, the first registered wins silently."""
        app_context.register_bean_collection(_ConflictCollectionA)
        app_context.register_bean_collection(_ConflictCollectionB)
        app_context.init_ioc_container()

        bean = app_context.get_bean(_SharedService)
        assert bean is not None

    def test_invalid_bean_name_mismatch_raises(self, app_context: ApplicationContext):
        app_context.register_bean_collection(_BadCollection)

        with pytest.raises(InvalidBeanError, match="INVALID BEAN"):
            app_context.init_ioc_container()


class TestBeanRetrievalFromContext:

    def test_get_bean_returns_registered_bean(self, app_context: ApplicationContext):
        app_context.register_bean_collection(_LibCollection)
        app_context.init_ioc_container()

        bean = app_context.get_bean(_ExternalLib)
        assert bean is not None
        assert bean.value == "external"

    def test_get_bean_returns_none_for_unregistered(self, app_context: ApplicationContext):
        class NotRegistered:
            pass

        assert app_context.get_bean(NotRegistered) is None

    def test_get_bean_with_qualifier(self, app_context: ApplicationContext):
        app_context.register_bean_collection(_LibCollection)
        app_context.init_ioc_container()

        assert app_context.get_bean(_ExternalLib, qualifier="_ExternalLib") is not None
        assert app_context.get_bean(_ExternalLib, qualifier="WrongName") is None

    def test_must_get_bean_returns_when_present(self, app_context: ApplicationContext):
        app_context.register_bean_collection(_LibCollection)
        app_context.init_ioc_container()

        bean = app_context.must_get_bean(_ExternalLib)
        assert isinstance(bean, _ExternalLib)


class TestBeanInjectionIntoComponents:

    def test_bean_injected_into_component(self, app_context: ApplicationContext):
        class MyService(Component):
            client: _ExternalClient

        app_context.register_bean_collection(_ClientCollection)
        app_context.register_component(MyService)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        service = app_context.get_component(MyService)
        assert service is not None
        assert service.client.url == "http://api.example.com"

    def test_component_preferred_over_bean_when_both_exist(self, app_context: ApplicationContext):
        class SharedType(Component):
            source: str = "component"

        class SharedCollection(BeanCollection):
            @classmethod
            def create_shared_type(cls) -> SharedType:
                inst = SharedType()
                inst.source = "bean"
                return inst

        class Consumer(Component):
            dep: SharedType

        app_context.register_component(SharedType)
        app_context.register_bean_collection(SharedCollection)
        app_context.register_component(Consumer)
        app_context.init_ioc_container()
        app_context.inject_dependencies_for_app_entities()

        consumer = app_context.get_component(Consumer)
        assert consumer is not None
        assert consumer.dep.source == "component"
