import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from py_spring_core.core.utils import dynamically_import_modules, clear_module_cache
from py_spring_core.commons.class_scanner import ClassScanner


class TestModuleImportCache:
    """Test module import caching to prevent duplicate imports."""

    def setup_method(self):
        """Clear module cache before each test."""
        clear_module_cache()

    def test_dynamically_import_modules_cache(self):
        """Test that dynamically_import_modules uses cache to prevent duplicate imports."""
        # Create a temporary Python file with a class
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    def __init__(self):
        self.value = "test"
""")
            temp_file_path = f.name

        try:
            # First import - get all classes without filtering
            classes1 = dynamically_import_modules([temp_file_path], target_subclasses=[])
            
            # Second import of the same file
            classes2 = dynamically_import_modules([temp_file_path], target_subclasses=[])
            
            # Both should return the same classes
            assert len(classes1) == 1
            assert len(classes2) == 1
            assert classes1 == classes2
            
            # The class should be the same object (not a duplicate)
            class1 = list(classes1)[0]
            class2 = list(classes2)[0]
            assert class1 is class2
            
        finally:
            os.unlink(temp_file_path)

    def test_class_scanner_cache(self):
        """Test that ClassScanner uses cache to prevent duplicate imports."""
        # Create a temporary Python file with a class
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    def __init__(self):
        self.value = "test"
""")
            temp_file_path = f.name

        try:
            scanner = ClassScanner([temp_file_path])
            
            # First scan
            scanner.scan_classes_for_file_paths([])
            classes1 = list(scanner.get_classes())
            
            # Second scan
            scanner.scan_classes_for_file_paths([])
            classes2 = list(scanner.get_classes())
            
            # Both should return the same classes
            assert len(classes1) == 1
            assert len(classes2) == 1
            assert classes1 == classes2
            
            # The class should be the same object (not a duplicate)
            assert classes1[0] is classes2[0]
            
        finally:
            os.unlink(temp_file_path)

    def test_clear_module_cache(self):
        """Test that clear_module_cache works correctly."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    pass
""")
            temp_file_path = f.name

        try:
            # First import
            classes1 = dynamically_import_modules([temp_file_path], target_subclasses=[])
            
            # Clear cache
            clear_module_cache()
            
            # Second import after clearing cache
            classes2 = dynamically_import_modules([temp_file_path], target_subclasses=[])
            
            # Classes should be different objects after clearing cache
            class1 = list(classes1)[0]
            class2 = list(classes2)[0]
            assert class1 is not class2
            
        finally:
            os.unlink(temp_file_path)

    def test_class_scanner_clear_cache(self):
        """Test that ClassScanner clear_module_cache works correctly."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    pass
""")
            temp_file_path = f.name

        try:
            scanner = ClassScanner([temp_file_path])
            
            # First scan
            scanner.scan_classes_for_file_paths([])
            classes1 = list(scanner.get_classes())
            
            # Clear cache
            scanner.clear_module_cache()
            
            # Second scan after clearing cache
            scanner.scan_classes_for_file_paths([])
            classes2 = list(scanner.get_classes())
            
            # Classes should be different objects after clearing cache
            assert classes1[0] is not classes2[0]
            
        finally:
            os.unlink(temp_file_path)

    @patch('py_spring_core.commons.module_importer.logger')
    def test_cache_logging(self, mock_logger):
        """Test that cache usage is properly logged."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
class TestClass:
    pass
""")
            temp_file_path = f.name

        try:
            # First import (should log import)
            dynamically_import_modules([temp_file_path], target_subclasses=[])
            
            # Second import (should log cache usage)
            dynamically_import_modules([temp_file_path], target_subclasses=[])
            
            # Check that debug log for cache usage was called
            # Get the actual module name from the temp file
            module_name = Path(temp_file_path).stem
            mock_logger.debug.assert_called_with(
                f"[MODULE CACHE] Using cached module: {module_name}"
            )
            
        finally:
            os.unlink(temp_file_path) 