# Module Cache API Documentation

## Overview

PySpring's module cache mechanism provides functionality to prevent duplicate imports, solving compatibility issues with ORM frameworks like SQLAlchemy.

## Core API

### `dynamically_import_modules`

Dynamically imports modules and returns a set of classes, with cache mechanism support.

```python
from py_spring_core.core.utils import dynamically_import_modules

def dynamically_import_modules(
    module_paths: Iterable[str],
    is_ignore_error: bool = True,
    target_subclasses: Iterable[Type[object]] = [],
) -> set[Type[object]]
```

**Parameters:**
- `module_paths`: List of module file paths to import
- `is_ignore_error`: Whether to ignore import errors (default True)
- `target_subclasses`: Target subclass filter (default empty list, returns all classes)

**Returns:**
- `set[Type[object]]`: Set of imported classes

**Example:**
```python
# Import all classes
classes = dynamically_import_modules(['models/user.py', 'models/role.py'])

# Only import subclasses of specific base classes
from py_spring_core.core.entities.component import Component
components = dynamically_import_modules(
    ['services/'], 
    target_subclasses=[Component]
)
```

### `clear_module_cache`

Clears the global module cache.

```python
from py_spring_core.core.utils import clear_module_cache

def clear_module_cache() -> None
```

**Usage:**
- Force re-import in test environments
- Reload modified modules in development environments
- Memory management

**Example:**
```python
# Clear cache and re-import
clear_module_cache()
classes = dynamically_import_modules(['updated_module.py'])
```

## ClassScanner API

### Instance-Level Cache

The `ClassScanner` class provides instance-level module caching:

```python
from py_spring_core.commons.class_scanner import ClassScanner

scanner = ClassScanner(['models/'])

# First scan
scanner.scan_classes_for_file_paths()
classes1 = list(scanner.get_classes())

# Second scan (uses cache)
scanner.scan_classes_for_file_paths()
classes2 = list(scanner.get_classes())

# Clear instance cache
scanner.clear_module_cache()
```

## Usage Scenarios

### 1. Solving SQLAlchemy Duplicate Registration Issues

```python
# Before fix: Would throw "Multiple classes found" error
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserRoleLink(Base):
    __tablename__ = 'user_role_links'
    id = Column(Integer, primary_key=True)

# Multiple imports would cause duplicate registration errors
# After fix: Using cache mechanism ensures classes are only registered once
```

### 2. Performance Optimization

```python
# Import all modules once during application startup
def initialize_models():
    model_files = [
        'models/user.py',
        'models/role.py', 
        'models/permission.py'
    ]
    
    # First import will cache modules
    classes = dynamically_import_modules(model_files)
    
    # Subsequent access uses cache, avoiding repeated I/O and compilation
    return classes
```

### 3. Test Environment

```python
import pytest
from py_spring_core.core.utils import clear_module_cache

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache after each test"""
    yield
    clear_module_cache()

def test_module_import():
    # Test module import functionality
    classes = dynamically_import_modules(['test_module.py'])
    assert len(classes) > 0
```

## Best Practices

### 1. Cache Key Management

```python
# Use absolute paths to ensure cache consistency
from pathlib import Path

file_path = Path('relative/path.py').resolve()
cache_key = str(file_path)  # Automatically handles path differences
```

### 2. Error Handling

```python
try:
    classes = dynamically_import_modules(['problematic_module.py'])
except Exception as e:
    logger.error(f"Import failed: {e}")
    # Handle import errors
```

### 3. Memory Management

```python
# Periodically clear cache in long-running applications
import gc

def cleanup_cache():
    clear_module_cache()
    gc.collect()  # Force garbage collection
```

## Logging and Debugging

### Cache Usage Logs

```python
# Enable debug logs to view cache usage
import logging
logging.getLogger('py_spring_core.core.utils').setLevel(logging.DEBUG)

# Log output example:
# [MODULE IMPORT] Import module path: /path/to/module.py
# [DYNAMICALLY MODULE IMPORT] Successfully imported module_name
# [MODULE CACHE] Using cached module: module_name
```

### Cache Status Check

```python
# Check cache status (internal implementation)
def get_cache_info():
    from py_spring_core.core.utils import _module_cache
    return {
        'cache_size': len(_module_cache),
        'cached_modules': list(_module_cache.keys())
    }
```

## Compatibility Notes

### Backward Compatibility

- All existing APIs remain unchanged
- Cache mechanism is transparent to users
- Does not affect existing functionality

### Framework Compatibility

- ✅ SQLAlchemy
- ✅ Django ORM  
- ✅ Pydantic
- ✅ Other class identity sensitive libraries

## Troubleshooting

### Common Issues

1. **Cache Not Working**
   - Check if file paths are consistent
   - Confirm absolute paths are used

2. **Memory Leaks**
   - Periodically call `clear_module_cache()`
   - Check for circular references

3. **Thread Safety Issues**
   - Current implementation is not thread-safe
   - Recommend using in single-threaded environments

### Debugging Tips

```python
# Force re-import for debugging
clear_module_cache()
classes = dynamically_import_modules(['debug_module.py'])

# Check class identity
print(f"Class identity: {id(classes[0])}")
print(f"Class module: {classes[0].__module__}")
``` 