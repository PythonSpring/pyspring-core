import pytest

from py_spring_core.core.entities.bean_collection import BeanCollection, BeanView
from py_spring_core.core.entities.component import Component


class TestBeanView:
    class TestBean: ...

    @pytest.fixture
    def test_bean(self) -> TestBean:
        return self.TestBean()

    @pytest.fixture
    def test_bean_view(self, test_bean: TestBean) -> BeanView:
        bean_view = BeanView(
            bean_creation_func=lambda: test_bean, bean_name="TestBean", bean=test_bean
        )
        assert bean_view.is_valid_bean() is True
        return bean_view

    def test_valid_bean_identification(self, test_bean_view: BeanView):
        assert test_bean_view.is_valid_bean() is True

    def test_set_and_get_bean_attributes(self, test_bean_view: BeanView):
        assert test_bean_view.bean_name == "TestBean"
        assert isinstance(test_bean_view.bean, self.TestBean)

    def test_exclude_bean_creation_func_from_serialization(
        self, test_bean_view: BeanView
    ):
        assert "bean_creation_func" not in test_bean_view.model_dump()

    def test_empty_bean_name(self):
        bean = Component()
        bean_view = BeanView(bean_creation_func=lambda: bean, bean_name="", bean=bean)
        assert not bean_view.is_valid_bean()

    def test_none_bean(self):
        bean_view = BeanView(
            bean_creation_func=lambda: None, bean_name="Component", bean=None
        )
        assert not bean_view.is_valid_bean()

    def test_arbitrary_types_for_bean_attribute(self):
        arbitrary_object = object()
        bean_view = BeanView(
            bean_creation_func=lambda: arbitrary_object,
            bean_name="object",
            bean=arbitrary_object,
        )
        assert isinstance(bean_view.bean, object)

    def test_internal_consistency_on_update(self):
        initial_bean = Component()
        updated_bean = Component()
        bean_view = BeanView(
            bean_creation_func=lambda: initial_bean,
            bean_name="Component",
            bean=initial_bean,
        )
        assert bean_view.is_valid_bean()

        # Update attributes
        bean_view.bean_name = "UpdatedComponent"
        bean_view.bean = updated_bean

        assert not bean_view.is_valid_bean()

        # Revert attributes to valid state
        updated_bean.__class__.__name__ = "UpdatedComponent"
        assert bean_view.is_valid_bean()


class TestBeanCollection:
    def test_scan_beans_identifies_all_beans(self):
        class TestClass(BeanCollection):
            @classmethod
            def create_bean_a(cls) -> Component:
                return Component()

            @classmethod
            def create_bean_b(cls) -> Component:
                return Component()

        beans = TestClass.scan_beans()
        assert len(beans) == 2
