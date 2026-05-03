import sys
import tempfile
import os

import pytest

from py_spring_core.commons.module_importer import ModuleImporter


class TestModuleImporter:
    """Test ModuleImporter class functionality."""

    def setup_method(self):
        """Clear module cache before each test."""
        self.importer = ModuleImporter()

    def test_import_module_from_path(self):
        """Test importing a module from a file path."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    def __init__(self):
        self.value = "test"

def test_function():
    return "test"
""")
            temp_file_path = f.name

        try:
            module = self.importer.import_module_from_path(temp_file_path)
            
            assert module is not None
            assert hasattr(module, 'TestClass')
            assert hasattr(module, 'test_function')
            
            # Test that the class can be instantiated
            test_instance = module.TestClass()
            assert test_instance.value == "test"
            
        finally:
            os.unlink(temp_file_path)

    def test_import_module_from_path_caching(self):
        """Test that modules are cached and reused."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    pass
""")
            temp_file_path = f.name

        try:
            # First import
            module1 = self.importer.import_module_from_path(temp_file_path)
            cache_size1 = self.importer.get_cache_size()
            
            # Second import
            module2 = self.importer.import_module_from_path(temp_file_path)
            cache_size2 = self.importer.get_cache_size()
            
            # Should be the same module object
            assert module1 is module2
            # Cache size should not increase
            assert cache_size1 == cache_size2
            
        finally:
            os.unlink(temp_file_path)

    def test_extract_classes_from_module(self):
        """Test extracting classes from a module."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class ClassA:
    pass

class ClassB:
    pass

def function():
    pass

CONSTANT = 42
""")
            temp_file_path = f.name

        try:
            module = self.importer.import_module_from_path(temp_file_path)
            classes = self.importer.extract_classes_from_module(module)
            
            # Should find 2 classes
            assert len(classes) == 2
            
            # Check class names
            class_names = [cls.__name__ for cls in classes]
            assert 'ClassA' in class_names
            assert 'ClassB' in class_names
            
        finally:
            os.unlink(temp_file_path)

    def test_import_classes_from_paths(self):
        """Test importing classes from multiple file paths."""
        # Create temporary Python files
        temp_files = []
        try:
            for i in range(2):
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(f"""
class Class{i}:
    def __init__(self):
        self.id = {i}
""")
                    temp_files.append(f.name)
            
            # Import classes from both files
            classes = self.importer.import_classes_from_paths(temp_files)
            
            # Should find 2 classes
            assert len(classes) == 2
            
            # Check that classes can be instantiated
            class_list = list(classes)
            instance0 = class_list[0]()
            instance1 = class_list[1]()
            
            assert hasattr(instance0, 'id')
            assert hasattr(instance1, 'id')
            
        finally:
            for temp_file in temp_files:
                os.unlink(temp_file)

    def test_import_classes_from_paths_with_filtering(self):
        """Test importing classes with target subclass filtering."""
        # Create a temporary Python file with different types of classes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class BaseClass:
    pass

class SubClass(BaseClass):
    pass

class UnrelatedClass:
    pass
""")
            temp_file_path = f.name

        try:
            # First import to get the BaseClass
            all_classes = self.importer.import_classes_from_paths([temp_file_path])
            base_class = None
            for cls in all_classes:
                if cls.__name__ == 'BaseClass':
                    base_class = cls
                    break
            
            assert base_class is not None
            
            # Import only subclasses of BaseClass
            classes = self.importer.import_classes_from_paths(
                [temp_file_path], 
                target_subclasses=[base_class]
            )
            
            # Should only find SubClass
            assert len(classes) == 1
            class_list = list(classes)
            assert class_list[0].__name__ == 'SubClass'
            
        finally:
            os.unlink(temp_file_path)

    def test_clear_cache(self):
        """Test clearing the module cache."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    pass
""")
            temp_file_path = f.name

        try:
            # Import module
            module1 = self.importer.import_module_from_path(temp_file_path)
            assert self.importer.get_cache_size() == 1
            
            # Clear cache
            self.importer.clear_cache()
            assert self.importer.get_cache_size() == 0
            
            # Import again (should be a different object)
            module2 = self.importer.import_module_from_path(temp_file_path)
            assert module1 is not module2
            
        finally:
            os.unlink(temp_file_path)

    def test_import_nonexistent_file(self):
        """Test importing a non-existent file."""
        with pytest.raises(FileNotFoundError):
            self.importer.import_module_from_path("/nonexistent/file.py")

    def test_import_invalid_python_file(self):
        """Test importing a file with invalid Python syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    def __init__(self):
        # Invalid syntax - missing colon
        if True
            pass
""")
            temp_file_path = f.name

        try:
            with pytest.raises(SyntaxError):
                self.importer.import_module_from_path(temp_file_path)

        finally:
            os.unlink(temp_file_path)

    def test_import_registers_module_in_sys_modules(self):
        """Test that imported modules are registered in sys.modules.

        Without sys.modules registration, standard Python imports in scanned
        modules would re-execute the module, creating duplicate class objects.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a module file
            model_file = os.path.join(tmpdir, "my_model.py")
            with open(model_file, "w") as f:
                f.write("class Product:\n    pass\n")

            module = self.importer.import_module_from_path(model_file)
            assert module is not None

            # The module should be findable in sys.modules by its stem name
            assert "my_model" in sys.modules
            assert sys.modules["my_model"] is module

            # Clean up sys.modules
            sys.modules.pop("my_model", None)

    def test_standard_import_returns_same_class_after_module_importer(self):
        """Test that standard Python import returns the same class object as ModuleImporter.

        When ModuleImporter loads a module and a subsequently loaded module
        imports from it via standard 'from X import Y', Python should find
        the already-loaded module in sys.modules and return the same class
        object, preserving class identity across import mechanisms.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create model file
            model_file = os.path.join(tmpdir, "repro_model.py")
            with open(model_file, "w") as f:
                f.write("class Product:\n    pass\n")

            # Create service file that imports from model via standard import
            service_file = os.path.join(tmpdir, "repro_service.py")
            with open(service_file, "w") as f:
                f.write(
                    "from repro_model import Product\n"
                    "product_cls = Product\n"
                )

            # Add tmpdir to sys.path so standard imports can resolve
            sys.path.insert(0, tmpdir)
            try:
                # Step 1: ModuleImporter loads the model
                model_module = self.importer.import_module_from_path(model_file)
                product_from_importer = model_module.Product

                # Step 2: ModuleImporter loads the service (which does 'from repro_model import Product')
                service_module = self.importer.import_module_from_path(service_file)
                product_from_service = service_module.product_cls

                # These MUST be the same class object
                assert product_from_importer is product_from_service, (
                    f"Product class loaded by ModuleImporter (id={id(product_from_importer)}) "
                    f"differs from Product class loaded by standard import in service "
                    f"(id={id(product_from_service)}). This means sys.modules was not "
                    f"populated by ModuleImporter."
                )
            finally:
                sys.path.remove(tmpdir)
                sys.modules.pop("repro_model", None)
                sys.modules.pop("repro_service", None)

    def test_standard_import_before_module_importer_returns_same_class(self):
        """Test that ModuleImporter reuses a module already in sys.modules.

        When a service is scanned before its model dependency, the service's
        standard 'from X import Y' populates sys.modules first. When
        ModuleImporter later scans the model file, it must detect the existing
        sys.modules entry and reuse it instead of creating a duplicate module.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            model_file = os.path.join(tmpdir, "reverse_model.py")
            with open(model_file, "w") as f:
                f.write("class Product:\n    pass\n")

            service_file = os.path.join(tmpdir, "reverse_service.py")
            with open(service_file, "w") as f:
                f.write(
                    "from reverse_model import Product\n"
                    "product_cls = Product\n"
                )

            sys.path.insert(0, tmpdir)
            try:
                # Step 1: ModuleImporter loads the SERVICE first.
                # During exec_module, Python's standard import loads reverse_model
                # into sys.modules.
                service_module = self.importer.import_module_from_path(service_file)
                product_from_service = service_module.product_cls

                # Step 2: ModuleImporter loads the MODEL file.
                # It must detect that "reverse_model" is already in sys.modules
                # and return that module instead of creating a new one.
                model_module = self.importer.import_module_from_path(model_file)
                product_from_importer = model_module.Product

                assert product_from_importer is product_from_service, (
                    f"Product from ModuleImporter (id={id(product_from_importer)}) "
                    f"differs from Product loaded by standard import in service "
                    f"(id={id(product_from_service)}). ModuleImporter did not "
                    f"check sys.modules before creating a new module."
                )
            finally:
                sys.path.remove(tmpdir)
                sys.modules.pop("reverse_model", None)
                sys.modules.pop("reverse_service", None)

    def test_clear_cache_removes_sys_modules_entries(self):
        """Test that clear_cache also removes entries from sys.modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_file = os.path.join(tmpdir, "cache_test_model.py")
            with open(model_file, "w") as f:
                f.write("class Foo:\n    pass\n")

            self.importer.import_module_from_path(model_file)

            # Module should be in sys.modules after import
            assert "cache_test_model" in sys.modules

            # After clearing cache, it should be removed from sys.modules too
            self.importer.clear_cache()
            assert "cache_test_model" not in sys.modules

    def test_sys_modules_name_collision_returns_correct_module(self):
        """Test that a sys.modules entry with the same stem name but different
        file path is NOT incorrectly reused.

        Scenario: Two different files share the same stem name (e.g.
        ``dir_a/models.py`` and ``dir_b/models.py``). If ``dir_a/models.py``
        is already in ``sys.modules`` under the key ``"models"``, importing
        ``dir_b/models.py`` must NOT return the ``dir_a`` module. It should
        create and execute a fresh module for ``dir_b/models.py``.

        The old implementation only checked ``module_name in sys.modules``
        without verifying the file path, which caused it to silently return
        the wrong module.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two directories each with a file that has the same stem name
            dir_a = os.path.join(tmpdir, "dir_a")
            dir_b = os.path.join(tmpdir, "dir_b")
            os.makedirs(dir_a)
            os.makedirs(dir_b)

            file_a = os.path.join(dir_a, "collision.py")
            with open(file_a, "w") as f:
                f.write("SOURCE = 'dir_a'\n")

            file_b = os.path.join(dir_b, "collision.py")
            with open(file_b, "w") as f:
                f.write("SOURCE = 'dir_b'\n")

            try:
                # Import the first file — this puts "collision" into sys.modules
                module_a = self.importer.import_module_from_path(file_a)
                assert module_a.SOURCE == "dir_a"
                assert "collision" in sys.modules

                # Now import the second file which has the same stem "collision"
                # but lives in a different directory.
                module_b = self.importer.import_module_from_path(file_b)

                # The second module MUST NOT be the same object as the first.
                # It must have been freshly loaded from dir_b.
                assert module_b.SOURCE == "dir_b", (
                    f"Expected SOURCE='dir_b' but got SOURCE='{module_b.SOURCE}'. "
                    f"ModuleImporter incorrectly reused the sys.modules entry from "
                    f"a different file path with the same stem name."
                )
                assert module_a is not module_b
            finally:
                sys.modules.pop("collision", None)