# **PySpring** Framework

#### **PySpring** is a Python web framework inspired by Spring Boot. It combines FastAPI for the web layer, and Pydantic for data validation. PySpring provides a structured approach to building scalable web applications with `auto dependency injection`, `auto configuration management` and a `web server` for hosting your application.

## Key Features
- **Application Initialization**: `PySpringApplication` class serves as the main entry point for the **PySpring** application. It initializes the application from a configuration file, scans the application source directory for Python files, and groups them into class files and model files.

- **Application Context Management**: **PySpring** manages the application context and dependency injection. It registers application entities such as components, controllers, bean collections, and properties. It also initializes the application context and injects dependencies.

- **REST Controllers**: **PySpring** supports RESTful API development using the RestController class. It allows you to define routes, handle HTTP requests, and register middlewares easily.

- **Component-based Architecture**: **PySpring** encourages a component-based architecture, where components are reusable and modular building blocks of the application. Components can have their own lifecycle and can be registered and managed by the application context.

- **Properties Management**: Properties classes provide a convenient way to manage application-specific configurations. **PySpring** supports loading properties from a properties file and injecting them into components.

- **Framework Modules**: **PySpring** allows the integration of additional framework modules to extend the functionality of the application. Modules can provide additional routes, middlewares, or any other custom functionality required by the application.

- **Builtin FastAPI Integration**: **PySpring** integrates with `FastAPI`, a modern, fast (high-performance), web framework for building APIs with Python. It leverages FastAPI's features for routing, request handling, and server configuration.

## Project Structure
```
PySpring/
├── src/                    # Source code directory
├── tests/                  # Test files
├── logs/                   # Application logs
├── py_spring_core/         # Core framework package
├── app-config.json         # Application configuration
├── application-properties.json  # Application properties
├── main.py                 # Application entry point
├── pyproject.toml          # Project metadata and dependencies
└── README.md              # Project documentation
```

## Getting Started

### Prerequisites
- Python 3.10 or higher
- pip (Python package installer)

### Installation
1. Install the **PySpring** framework:
```bash
pip install py-spring-core
```

2. Create a new Python project and navigate to its directory

3. Set up your application:
   - Implement your application properties, components, and controllers using **PySpring** conventions inside the declared source code folder (which can be modified via the `app_src_target_dir` key in `app-config.json`)
   - Create an `app-config.json` file for your application configuration
   - Create an `application-properties.json` file for your application properties

4. Create your main application script:
```python
from py_spring_core import PySpringApplication

def main():
    app = PySpringApplication("./app-config.json")
    app.run()

if __name__ == "__main__":
    main()
```

5. Run your application:
```bash
python main.py
```

For a complete example project, please refer to the [PySpring Example Project](https://github.com/NFUChen/PySpring-Example-Project).

## Development Setup
1. Clone the repository:
```bash
git clone https://github.com/NFUChen/PySpring.git
cd PySpring
```

2. Install development dependencies:
```bash
pip install -e ".[dev]"
```

3. Run tests:
```bash
pytest
```

## Dependencies
PySpring relies on several key dependencies:
- FastAPI (0.112.0)
- Pydantic (2.8.2)
- Uvicorn (0.30.5)
- Loguru (0.7.2)
- And other supporting packages

For a complete list of dependencies, see `pyproject.toml`.

## Contributing

Contributions to **PySpring** are welcome! If you find any issues or have suggestions for improvements, please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
