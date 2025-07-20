import tempfile
import os
from pathlib import Path
from typing import Type

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
        result = self.importer.import_module_from_path("/nonexistent/file.py")
        assert result is None

    def test_import_invalid_python_file(self):
        """Test importing a file with invalid Python syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    def __init__(self):
        # Invalid syntax
        if True:
            pass
""")
            temp_file_path = f.name

        try:
            result = self.importer.import_module_from_path(temp_file_path)
            assert result is None
            
        finally:
            os.unlink(temp_file_path) 