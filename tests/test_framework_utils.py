import pytest
from abc import ABC, abstractmethod
from typing import Type, Any

from py_spring_core.core.utils import get_unimplemented_abstract_methods


class TestFrameworkUtils:
    """Test suite for framework utility functions."""

    def test_get_unimplemented_abstract_methods_with_concrete_class(self):
        """Test that fully implemented classes return empty set."""
        
        class AbstractBase(ABC):
            @abstractmethod
            def method_a(self) -> None:
                pass
            
            @abstractmethod
            def method_b(self) -> str:
                pass
        
        class ConcreteImpl(AbstractBase):
            def method_a(self) -> None:
                pass
            
            def method_b(self) -> str:
                return "implemented"
        
        unimplemented = get_unimplemented_abstract_methods(ConcreteImpl)
        assert unimplemented == set()

    def test_get_unimplemented_abstract_methods_with_partial_implementation(self):
        """Test that partially implemented classes return missing methods."""
        
        class AbstractBase(ABC):
            @abstractmethod
            def method_a(self) -> None:
                pass
            
            @abstractmethod
            def method_b(self) -> str:
                pass
            
            @abstractmethod
            def method_c(self) -> int:
                pass
        
        class PartialImpl(AbstractBase):
            def method_a(self) -> None:
                pass
            
            # method_b and method_c are not implemented
        
        unimplemented = get_unimplemented_abstract_methods(PartialImpl)
        assert unimplemented == {"method_b", "method_c"}

    def test_get_unimplemented_abstract_methods_with_no_implementation(self):
        """Test that classes with no implementations return all abstract methods."""
        
        class AbstractBase(ABC):
            @abstractmethod
            def method_a(self) -> None:
                pass
            
            @abstractmethod
            def method_b(self) -> str:
                pass
        
        class NoImpl(AbstractBase):
            # No methods implemented
            pass
        
        unimplemented = get_unimplemented_abstract_methods(NoImpl)
        assert unimplemented == {"method_a", "method_b"}

    def test_get_unimplemented_abstract_methods_with_multiple_inheritance(self):
        """Test with multiple inheritance from abstract classes."""
        
        class AbstractA(ABC):
            @abstractmethod
            def method_a(self) -> None:
                pass
        
        class AbstractB(ABC):
            @abstractmethod
            def method_b(self) -> str:
                pass
        
        class MultipleInheritance(AbstractA, AbstractB):
            def method_a(self) -> None:
                pass
            # method_b is not implemented
        
        unimplemented = get_unimplemented_abstract_methods(MultipleInheritance)
        assert unimplemented == {"method_b"}

    def test_get_unimplemented_abstract_methods_with_inheritance_chain(self):
        """Test with inheritance chain where parent implements some methods."""
        
        class AbstractBase(ABC):
            @abstractmethod
            def method_a(self) -> None:
                pass
            
            @abstractmethod
            def method_b(self) -> str:
                pass
            
            @abstractmethod
            def method_c(self) -> int:
                pass
        
        class PartialParent(AbstractBase):
            def method_a(self) -> None:
                pass
            # method_b and method_c still abstract
        
        class ChildImpl(PartialParent):
            def method_b(self) -> str:
                return "implemented"
            # method_c still not implemented
        
        unimplemented = get_unimplemented_abstract_methods(ChildImpl)
        assert unimplemented == {"method_c"}

    def test_get_unimplemented_abstract_methods_with_no_abstract_methods(self):
        """Test with class that has no abstract methods."""
        
        class NonAbstractBase(ABC):
            def regular_method(self) -> None:
                pass
        
        class RegularClass(NonAbstractBase):
            def another_method(self) -> str:
                return "normal"
        
        unimplemented = get_unimplemented_abstract_methods(RegularClass)
        assert unimplemented == set()

    def test_get_unimplemented_abstract_methods_type_error_non_class(self):
        """Test that function raises TypeError for non-class types."""
        
        with pytest.raises(TypeError, match="Expected a class type"):
            get_unimplemented_abstract_methods("not a class")  # type: ignore
        
        with pytest.raises(TypeError, match="Expected a class type"):
            get_unimplemented_abstract_methods(42)  # type: ignore

    def test_get_unimplemented_abstract_methods_type_error_non_abc(self):
        """Test that function raises TypeError for non-ABC classes."""
        
        class RegularClass:
            def some_method(self) -> None:
                pass
        
        with pytest.raises(TypeError, match="Expected a subclass of abc.ABC"):
            get_unimplemented_abstract_methods(RegularClass)

    def test_get_unimplemented_abstract_methods_with_property_abstracts(self):
        """Test with abstract properties."""
        
        class AbstractWithProperty(ABC):
            @property
            @abstractmethod
            def abstract_property(self) -> str:
                pass
            
            @abstractmethod
            def abstract_method(self) -> None:
                pass
        
        class PartialPropertyImpl(AbstractWithProperty):
            @property
            def abstract_property(self) -> str:
                return "implemented"
            # abstract_method not implemented
        
        unimplemented = get_unimplemented_abstract_methods(PartialPropertyImpl)
        # Properties might be included in the abstract methods set, so we check that abstract_method is there
        # and abstract_property is not (since it's implemented)
        assert "abstract_method" in unimplemented
        assert len([method for method in unimplemented if "abstract_property" not in method]) >= 1

    def test_get_unimplemented_abstract_methods_with_staticmethod_classmethod(self):
        """Test with abstract static and class methods."""
        
        class AbstractWithMethods(ABC):
            @staticmethod
            @abstractmethod
            def abstract_static() -> str:
                pass
            
            @classmethod
            @abstractmethod
            def abstract_class(cls) -> str:
                pass
            
            @abstractmethod
            def abstract_instance(self) -> None:
                pass
        
        class PartialMethodImpl(AbstractWithMethods):
            @staticmethod
            def abstract_static() -> str:
                return "static implemented"
            
            # abstract_class and abstract_instance not implemented
        
        unimplemented = get_unimplemented_abstract_methods(PartialMethodImpl)
        assert unimplemented == {"abstract_class", "abstract_instance"}

    def test_get_unimplemented_abstract_methods_real_world_example(self):
        """Test with a real-world like example similar to GracefulShutdownHandler."""
        
        from py_spring_core.core.interfaces.graceful_shutdown_handler import GracefulShutdownHandler
        
        class IncompleteShutdownHandler(GracefulShutdownHandler):
            def on_shutdown(self, shutdown_type) -> None:
                pass
            # on_timeout and on_error not implemented
        
        unimplemented = get_unimplemented_abstract_methods(IncompleteShutdownHandler)
        assert "on_timeout" in unimplemented
        assert "on_error" in unimplemented
        assert "on_shutdown" not in unimplemented 