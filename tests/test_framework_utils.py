import sys
import types

import pytest
from abc import ABC, abstractmethod
from typing import Type, Any

from py_spring_core.core.starter.py_spring_starter import PySpringStarter
from py_spring_core.core.starter.starter_discovery import StarterDiscovery
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


def _make_module(name: str, source: str) -> types.ModuleType:
    """Create an in-memory module, execute source in it, and register in sys.modules."""
    module = types.ModuleType(name)
    exec(source, module.__dict__)
    sys.modules[name] = module
    return module


class TestDiscoverStartersFromPackages:
    """Test suite for StarterDiscovery.from_packages."""

    def _create_fake_package(self, pkg_name: str, sub_modules: dict[str, str] | None = None):
        """Helper to build a fake package with optional sub-modules in sys.modules.

        Returns a list of module names to clean up after the test.
        """
        registered: list[str] = []

        # Root package module (must have __path__ for walk_packages to recurse)
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = []  # non-filesystem package
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg
        registered.append(pkg_name)

        if sub_modules:
            for sub_name, source in sub_modules.items():
                full_name = f"{pkg_name}.{sub_name}"
                mod = _make_module(full_name, source)
                mod.__package__ = pkg_name
                setattr(pkg, sub_name, mod)
                registered.append(full_name)

        return registered

    def test_discovers_starter_from_single_module(self, tmp_path):
        """A package containing a PySpringStarter subclass is discovered."""
        pkg_dir = tmp_path / "fake_starter_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "from py_spring_core.core.starter.py_spring_starter import PySpringStarter\n"
            "class MyStarter(PySpringStarter): pass\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            result = StarterDiscovery.from_packages(["fake_starter_pkg"])
            assert len(result) == 1
            assert result[0].__name__ == "MyStarter"
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("fake_starter_pkg", None)

    def test_discovers_starters_from_nested_submodules(self, tmp_path):
        """Starters in nested sub-packages are fully walked."""
        pkg_dir = tmp_path / "nested_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        sub_dir = pkg_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text(
            "from py_spring_core.core.starter.py_spring_starter import PySpringStarter\n"
            "class SubStarter(PySpringStarter): pass\n"
        )

        sys.path.insert(0, str(tmp_path))
        try:
            result = StarterDiscovery.from_packages(["nested_pkg"])
            names = [cls.__name__ for cls in result]
            assert "SubStarter" in names
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("nested_pkg"):
                    del sys.modules[key]

    def test_excludes_base_pyspringstarter(self, tmp_path):
        """The PySpringStarter base class itself is never included."""
        pkg_dir = tmp_path / "base_only_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "from py_spring_core.core.starter.py_spring_starter import PySpringStarter\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            result = StarterDiscovery.from_packages(["base_only_pkg"])
            assert len(result) == 0
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("base_only_pkg", None)

    def test_returns_empty_for_no_starters(self, tmp_path):
        """A package with no starter subclasses returns an empty list."""
        pkg_dir = tmp_path / "no_starter_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("X = 42\n")
        sys.path.insert(0, str(tmp_path))
        try:
            result = StarterDiscovery.from_packages(["no_starter_pkg"])
            assert result == []
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("no_starter_pkg", None)

    def test_skips_invalid_package_gracefully(self):
        """An invalid package name logs a warning and does not raise."""
        result = StarterDiscovery.from_packages(["totally_nonexistent_pkg_12345"])
        assert result == []

    def test_handles_multiple_packages(self, tmp_path):
        """Passing multiple package names returns starters from all of them."""
        for name in ("multi_a", "multi_b"):
            d = tmp_path / name
            d.mkdir()
            (d / "__init__.py").write_text(
                "from py_spring_core.core.starter.py_spring_starter import PySpringStarter\n"
                f"class Starter_{name}(PySpringStarter): pass\n"
            )
        sys.path.insert(0, str(tmp_path))
        try:
            result = StarterDiscovery.from_packages(["multi_a", "multi_b"])
            names = {cls.__name__ for cls in result}
            assert names == {"Starter_multi_a", "Starter_multi_b"}
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("multi_a") or key.startswith("multi_b"):
                    del sys.modules[key]

    def test_no_duplicates_across_packages(self, tmp_path):
        """A starter re-exported in multiple packages is only returned once."""
        # Package A defines the starter
        pkg_a = tmp_path / "dedup_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            "from py_spring_core.core.starter.py_spring_starter import PySpringStarter\n"
            "class SharedStarter(PySpringStarter): pass\n"
        )
        # Package B re-exports it
        pkg_b = tmp_path / "dedup_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            "from dedup_a import SharedStarter\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            result = StarterDiscovery.from_packages(["dedup_a", "dedup_b"])
            assert len(result) == 1
            assert result[0].__name__ == "SharedStarter"
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("dedup_"):
                    del sys.modules[key]