# **PySpring** Core

**PySpring** is a Python framework inspired by Spring Boot. It combines FastAPI for the web layer and Pydantic for data validation, providing a structured approach to building scalable web applications with automatic dependency injection, configuration management, component lifecycle hooks, event-driven architecture, and a built-in web server.

## Key Features

- **IoC Container & Dependency Injection** - Automatic dependency injection based on type annotations, supporting `Component`, `BeanCollection`, `Properties`, and qualifier-based resolution via `Annotated[T, 'qualifier']`.

- **Component Lifecycle** - Components support `Singleton` and `Prototype` scopes, with `post_construct()` and `pre_destroy()` lifecycle hooks.

- **REST Controllers** - Declarative route definition using `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, and `@PatchMapping` decorators with full FastAPI parameter support.

- **Properties Management** - Type-safe configuration via Pydantic-based `Properties` classes, loaded from a JSON properties file and automatically injected into components.

- **Bean Collections** - Factory-style bean registration using `BeanCollection` classes with `create_*` methods and return type annotations.

- **Middleware Support** - Custom middleware via the `Middleware` base class and `MiddlewareConfiguration` for controlling registration order through `MiddlewareRegistry`.

- **Event System** - Publish/subscribe event architecture using `ApplicationEventPublisher`, `ApplicationEvent`, and the `@EventListener` decorator.

- **Graceful Shutdown** - Configurable graceful shutdown handling with `GracefulShutdownHandler`, supporting SIGINT/SIGTERM signals with timeout management.

- **Exception Handlers** - Global exception handling with the `@ExceptionHandler` decorator.

- **Starter Modules** - Extensible plugin system via `PySpringStarter`, supporting manual registration and auto-discovery through `pyspring.starters` entry points.

- **Logging** - Integrated Loguru-based logging with configurable log level, rotation, retention, file output, and JSON format support.

## Project Structure

```
my-pyspring-app/
├── src/                            # Application source code (configurable)
│   ├── controllers/
│   ├── components/
│   ├── properties/
│   └── ...
├── app-config.json                 # Application configuration
├── application-properties.json     # Application properties
└── main.py                        # Application entry point
```

## Getting Started

### Prerequisites
- Python >= 3.11, < 3.13

### Installation

```bash
pip install py-spring-core
```

### Configuration

Create an `app-config.json`:

```json
{
    "app_src_target_dir": "./src",
    "server_config": {
        "host": "0.0.0.0",
        "port": 8080,
        "enabled": true
    },
    "properties_file_path": "./application-properties.json",
    "loguru_config": {
        "log_file_path": "./logs/app.log",
        "log_level": "DEBUG"
    },
    "shutdown_config": {
        "timeout_seconds": 30.0,
        "enabled": true
    }
}
```

Create an `application-properties.json` for your application properties:

```json
{
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "mydb"
    }
}
```

### Application Entry Point

```python
from py_spring_core import PySpringApplication

def main():
    app = PySpringApplication("./app-config.json")
    app.run()

if __name__ == "__main__":
    main()
```

### Defining a Component

```python
from py_spring_core import Component

class UserService(Component):
    def post_construct(self):
        # Called after dependency injection
        ...

    def pre_destroy(self):
        # Called during shutdown
        ...

    def get_user(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Alice"}
```

### Defining Properties

```python
from py_spring_core import Properties

class DatabaseProperties(Properties):
    __key__ = "database"

    host: str
    port: int
    name: str
```

### Defining a REST Controller

```python
from py_spring_core import RestController, GetMapping, PostMapping

class UserController(RestController):
    class Config:
        prefix = "/api/users"

    # Dependencies are injected automatically by type annotation
    user_service: UserService

    @GetMapping("/{user_id}")
    def get_user(self, user_id: int):
        return self.user_service.get_user(user_id)

    @PostMapping("/")
    def create_user(self, name: str):
        return {"name": name}
```

### Defining a Bean Collection

```python
from py_spring_core import BeanCollection

class AppBeans(BeanCollection):
    def create_http_client(self) -> HttpClient:
        return HttpClient(timeout=30)
```

### Using the Event System

```python
from py_spring_core import (
    Component, ApplicationEvent, ApplicationEventPublisher, EventListener
)

class UserCreatedEvent(ApplicationEvent):
    user_id: int
    username: str

class NotificationService(Component):
    @EventListener(UserCreatedEvent)
    def on_user_created(self, event: UserCreatedEvent):
        print(f"User created: {event.username}")

class UserService(Component):
    event_publisher: ApplicationEventPublisher

    def create_user(self, username: str):
        self.event_publisher.publish(UserCreatedEvent(user_id=1, username=username))
```

### Using Middleware

```python
from fastapi import Request, Response
from py_spring_core import Middleware, MiddlewareConfiguration, MiddlewareRegistry

class AuthMiddleware(Middleware):
    def should_skip(self, request: Request) -> bool:
        return request.url.path == "/health"

    async def process_request(self, request: Request) -> Response | None:
        token = request.headers.get("Authorization")
        if not token:
            return Response(status_code=401, content="Unauthorized")
        return None  # Continue to next middleware/route

class AppMiddlewareConfig(MiddlewareConfiguration):
    def configure_middlewares(self, registry: MiddlewareRegistry):
        registry.add_middleware(AuthMiddleware)
```

### Using Starters

```python
from py_spring_core import PySpringStarter, PySpringApplication

class MyStarter(PySpringStarter):
    def on_configure(self):
        self.component_classes.append(MyComponent)
        self.properties_classes.append(MyProperties)

    def on_initialized(self):
        # Called after IoC container is built
        ...

    def on_destroy(self):
        # Called during shutdown
        ...

# Manual registration
app = PySpringApplication("./app-config.json", starters=[MyStarter()])
app.run()
```

### Component Scopes & Qualifiers

```python
from typing import Annotated
from py_spring_core import Component, ComponentScope

class TransientService(Component):
    class Config:
        scope = ComponentScope.Prototype

class PrimaryCache(Component):
    class Config:
        name = "redis_cache"

class MyService(Component):
    # Qualifier-based injection
    cache: Annotated[CacheBase, "redis_cache"]
```

### Graceful Shutdown

```python
from py_spring_core import GracefulShutdownHandler, ShutdownType

class AppShutdownHandler(GracefulShutdownHandler):
    def on_shutdown(self, shutdown_type: ShutdownType):
        print(f"Shutting down: {shutdown_type}")

    def on_timeout(self):
        print("Shutdown timed out")

    def on_error(self, error: Exception):
        print(f"Shutdown error: {error}")
```

## Configuration Reference

### `app-config.json`

| Field | Type | Description |
|---|---|---|
| `app_src_target_dir` | `str` | Directory containing application source code |
| `server_config.host` | `str` | Server host address |
| `server_config.port` | `int` | Server port number |
| `server_config.enabled` | `bool` | Whether to start the web server (default: `true`) |
| `exclude_file_patterns` | `list[str]` | Regex patterns for files to exclude from scanning (default: `[".*/models\\.py$"]`) |
| `properties_file_path` | `str` | Path to the properties JSON file |
| `loguru_config.log_file_path` | `str \| null` | Log file path (set `null` to disable file logging) |
| `loguru_config.log_level` | `str` | Log level: `TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL` |
| `loguru_config.log_rotation` | `str \| null` | Log rotation interval (e.g. `"1 day"`) |
| `loguru_config.log_retention` | `str \| null` | Log retention period (e.g. `"7 days"`) |
| `loguru_config.format` | `str` | Log format: `text` or `json` |
| `shutdown_config.timeout_seconds` | `float` | Graceful shutdown timeout in seconds (default: `30.0`) |
| `shutdown_config.enabled` | `bool` | Whether shutdown timeout is enabled (default: `true`) |

## Dependencies

Key runtime dependencies:

- **FastAPI** >= 0.136.1
- **Pydantic** >= 2.11.7
- **Uvicorn** >= 0.30.5
- **Loguru** >= 0.7.2
- **PyYAML** >= 6.0.2
- **cachetools** >= 5.5.0

For a complete list, see `pyproject.toml`.

## Development

```bash
git clone https://github.com/NFUChen/PySpring.git
cd PySpring
pip install -e ".[dev]"
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
