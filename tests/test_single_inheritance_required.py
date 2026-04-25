"""
Edge case tests for SingleInheritanceRequired enforcement.

Covers:
- Zero subclasses returns None
- Single subclass allowed
- Multiple subclasses raise ValueError
- check_only_one_subclass_allowed validation
- get_subclass returns correct type
- Nested subclass detection
"""

import pytest

from py_spring_core.core.interfaces.single_inheritance_required import (
    SingleInheritanceRequired,
)


class TestSingleInheritanceRequired:

    def test_no_subclass_returns_none(self):
        class Standalone(SingleInheritanceRequired["Standalone"]):
            pass

        result = Standalone.get_subclass()
        assert result is None

    def test_single_subclass_returns_it(self):
        class Base(SingleInheritanceRequired["Base"]):
            pass

        class OnlyChild(Base):
            pass

        result = Base.get_subclass()
        assert result is OnlyChild

    def test_multiple_subclasses_raises_value_error(self):
        class Base(SingleInheritanceRequired["Base"]):
            pass

        class ChildA(Base):
            pass

        class ChildB(Base):
            pass

        with pytest.raises(ValueError, match="Only one subclass is allowed"):
            Base.get_subclass()

    def test_check_only_one_subclass_allowed_passes_with_one(self):
        class Base(SingleInheritanceRequired["Base"]):
            pass

        class Only(Base):
            pass

        Base.check_only_one_subclass_allowed()

    def test_check_only_one_subclass_allowed_passes_with_none(self):
        class Base(SingleInheritanceRequired["Base"]):
            pass

        Base.check_only_one_subclass_allowed()

    def test_check_only_one_subclass_allowed_raises_with_multiple(self):
        class Base(SingleInheritanceRequired["Base"]):
            pass

        class A(Base):
            pass

        class B(Base):
            pass

        with pytest.raises(ValueError, match="Only one subclass is allowed"):
            Base.check_only_one_subclass_allowed()


class TestApplicationContextRequiredEdgeCases:

    def test_get_context_raises_when_not_set(self):
        from py_spring_core.core.interfaces.application_context_required import (
            ApplicationContextRequired,
        )

        class MyMixin(ApplicationContextRequired):
            pass

        saved = MyMixin._app_context
        MyMixin._app_context = None

        try:
            with pytest.raises(RuntimeError, match="ApplicationContext is not set"):
                MyMixin.get_application_context()
        finally:
            MyMixin._app_context = saved

    def test_set_and_get_context(self):
        from unittest.mock import MagicMock
        from py_spring_core.core.interfaces.application_context_required import (
            ApplicationContextRequired,
        )

        class MyMixin(ApplicationContextRequired):
            pass

        mock_ctx = MagicMock()
        saved = MyMixin._app_context

        try:
            MyMixin.set_application_context(mock_ctx)
            assert MyMixin.get_application_context() is mock_ctx
        finally:
            MyMixin._app_context = saved
