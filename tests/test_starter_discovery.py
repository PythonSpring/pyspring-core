from unittest.mock import MagicMock, patch

import pytest

from py_spring_core.core.starter.py_spring_starter import PySpringStarter
from py_spring_core.core.starter.starter_discovery import (
    ENTRY_POINT_GROUP,
    StarterDiscovery,
)


class FakeStarterA(PySpringStarter):
    pass


class FakeStarterB(PySpringStarter):
    pass


class NotAStarter:
    pass


def _make_entry_point(name: str, load_return):
    """Create a mock EntryPoint that returns load_return on .load()."""
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = load_return
    return ep


def _make_failing_entry_point(name: str, exc: Exception):
    """Create a mock EntryPoint whose .load() raises exc."""
    ep = MagicMock()
    ep.name = name
    ep.load.side_effect = exc
    return ep


class TestStarterDiscoveryFromEntryPoints:
    """Tests for StarterDiscovery.from_entry_points."""

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_discovers_valid_starter(self, mock_eps):
        mock_eps.return_value = [_make_entry_point("a", FakeStarterA)]
        result = StarterDiscovery.from_entry_points()
        assert result == [FakeStarterA]

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_discovers_multiple_starters(self, mock_eps):
        mock_eps.return_value = [
            _make_entry_point("a", FakeStarterA),
            _make_entry_point("b", FakeStarterB),
        ]
        result = StarterDiscovery.from_entry_points()
        assert result == [FakeStarterA, FakeStarterB]

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_skips_non_starter_class(self, mock_eps):
        mock_eps.return_value = [_make_entry_point("bad", NotAStarter)]
        result = StarterDiscovery.from_entry_points()
        assert result == []

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_skips_non_class_object(self, mock_eps):
        mock_eps.return_value = [_make_entry_point("func", lambda: None)]
        result = StarterDiscovery.from_entry_points()
        assert result == []

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_skips_base_pyspringstarter(self, mock_eps):
        mock_eps.return_value = [_make_entry_point("base", PySpringStarter)]
        result = StarterDiscovery.from_entry_points()
        assert result == []

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_handles_load_failure_gracefully(self, mock_eps):
        mock_eps.return_value = [
            _make_failing_entry_point("broken", ImportError("no module")),
            _make_entry_point("good", FakeStarterA),
        ]
        result = StarterDiscovery.from_entry_points()
        assert result == [FakeStarterA]

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_deduplicates_same_class(self, mock_eps):
        mock_eps.return_value = [
            _make_entry_point("a1", FakeStarterA),
            _make_entry_point("a2", FakeStarterA),
        ]
        result = StarterDiscovery.from_entry_points()
        assert result == [FakeStarterA]

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_returns_empty_when_no_entry_points(self, mock_eps):
        mock_eps.return_value = []
        result = StarterDiscovery.from_entry_points()
        assert result == []

    @patch("py_spring_core.core.starter.starter_discovery.importlib.metadata.entry_points")
    def test_called_with_correct_group(self, mock_eps):
        mock_eps.return_value = []
        StarterDiscovery.from_entry_points()
        mock_eps.assert_called_once_with(group=ENTRY_POINT_GROUP)
