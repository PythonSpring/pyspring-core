import importlib
import importlib.metadata
import inspect
import pkgutil
from types import ModuleType
from typing import Iterable, Type

from loguru import logger

from py_spring_core.core.starter.py_spring_starter import PySpringStarter

ENTRY_POINT_GROUP = "pyspring.starters"


class StarterDiscovery:
    """Discovers PySpringStarter subclasses via entry points or package scanning."""

    @staticmethod
    def from_entry_points() -> list[Type[PySpringStarter]]:
        """Scan entry_points group 'pyspring.starters' and return starter classes.

        Each entry point should reference a concrete PySpringStarter subclass.
        Invalid entries (not a subclass, load failures) are logged and skipped.

        Returns:
            A deduplicated list of PySpringStarter subclasses.
        """
        discovered: list[Type[PySpringStarter]] = []
        seen: set[Type[PySpringStarter]] = set()

        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        for ep in eps:
            try:
                cls = ep.load()
            except Exception as e:
                logger.warning(
                    f"[STARTER DISCOVERY] Failed to load entry point '{ep.name}': {e}"
                )
                continue

            if not isinstance(cls, type) or not issubclass(cls, PySpringStarter):
                logger.warning(
                    f"[STARTER DISCOVERY] Entry point '{ep.name}' does not reference "
                    f"a PySpringStarter subclass (got {cls!r}), skipping."
                )
                continue

            if cls is PySpringStarter:
                logger.warning(
                    f"[STARTER DISCOVERY] Entry point '{ep.name}' references the base "
                    f"PySpringStarter class, skipping."
                )
                continue

            if cls not in seen:
                seen.add(cls)
                discovered.append(cls)
                logger.debug(
                    f"[STARTER DISCOVERY] Discovered starter from entry point: {cls.__name__}"
                )

        return discovered

    @staticmethod
    def from_packages(package_names: Iterable[str]) -> list[Type[PySpringStarter]]:
        """Dynamically import packages by name and discover all PySpringStarter subclasses.

        Recursively walks each package's sub-modules, inspects every class, and
        collects concrete PySpringStarter subclasses.

        Args:
            package_names: Dotted package names to scan (e.g. ["my_starter_pkg"]).

        Returns:
            A deduplicated list of PySpringStarter subclasses.
        """
        discovered: list[Type[PySpringStarter]] = []
        seen: set[Type[PySpringStarter]] = set()

        for package_name in package_names:
            try:
                package = importlib.import_module(package_name)
            except ImportError:
                logger.warning(
                    f"[STARTER DISCOVERY] Failed to import package: {package_name}"
                )
                continue

            modules_to_inspect: list[ModuleType] = [package]

            package_path = getattr(package, "__path__", None)
            if package_path is not None:
                for _importer, module_name, _is_pkg in pkgutil.walk_packages(
                    package_path, prefix=package.__name__ + "."
                ):
                    try:
                        sub_module = importlib.import_module(module_name)
                        modules_to_inspect.append(sub_module)
                    except Exception as e:
                        logger.warning(
                            f"[STARTER DISCOVERY] Failed to import sub-module {module_name}: {e}"
                        )
                        continue

            for module in modules_to_inspect:
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, PySpringStarter)
                        and obj is not PySpringStarter
                        and obj not in seen
                    ):
                        seen.add(obj)
                        discovered.append(obj)

        return discovered
