import os

import pytest

from py_spring_core.core.entities.properties.env_var_resolver import (
    EnvVarNotFoundError,
    EnvVarResolver,
)


class TestResolveValue:
    def test_no_placeholder_returns_unchanged(self):
        assert EnvVarResolver.resolve_value("hello world") == "hello world"

    def test_plain_env_var_resolves(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TEST_HOST", "myhost")
        assert EnvVarResolver.resolve_value("${TEST_HOST}") == "myhost"

    def test_missing_env_var_no_default_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("NONEXISTENT_VAR_XYZ", raising=False)
        with pytest.raises(EnvVarNotFoundError, match="NONEXISTENT_VAR_XYZ"):
            EnvVarResolver.resolve_value("${NONEXISTENT_VAR_XYZ}")

    def test_default_used_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        assert EnvVarResolver.resolve_value("${MISSING_VAR:fallback}") == "fallback"

    def test_env_var_overrides_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MY_VAR", "real_value")
        assert EnvVarResolver.resolve_value("${MY_VAR:fallback}") == "real_value"

    def test_empty_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("EMPTY_DEFAULT_VAR", raising=False)
        assert EnvVarResolver.resolve_value("${EMPTY_DEFAULT_VAR:}") == ""

    def test_partial_substitution(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("HOST", "db.example.com")
        monkeypatch.setenv("PORT", "3306")
        result = EnvVarResolver.resolve_value("postgresql://${HOST}:${PORT}/mydb")
        assert result == "postgresql://db.example.com:3306/mydb"

    def test_partial_substitution_with_defaults(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("HOST2", raising=False)
        monkeypatch.setenv("PORT2", "5432")
        result = EnvVarResolver.resolve_value("postgresql://${HOST2:localhost}:${PORT2}/mydb")
        assert result == "postgresql://localhost:5432/mydb"


class TestResolveDict:
    def test_flat_dict_resolves_string_values(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DB_HOST", "prod-db")
        data = {"host": "${DB_HOST}", "name": "static_value"}
        result = EnvVarResolver.resolve_dict(data)
        assert result == {"host": "prod-db", "name": "static_value"}

    def test_non_string_values_unchanged(self):
        data = {"port": 5432, "enabled": True, "ratio": 0.5, "nothing": None}
        result = EnvVarResolver.resolve_dict(data)
        assert result == {"port": 5432, "enabled": True, "ratio": 0.5, "nothing": None}

    def test_nested_dict_resolves(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("INNER_VAL", "resolved")
        data = {"level1": {"level2": {"value": "${INNER_VAL}"}}}
        result = EnvVarResolver.resolve_dict(data)
        assert result == {"level1": {"level2": {"value": "resolved"}}}

    def test_list_values_resolved(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ITEM_A", "alpha")
        data = {"items": ["${ITEM_A}", "static", 42]}
        result = EnvVarResolver.resolve_dict(data)
        assert result == {"items": ["alpha", "static", 42]}

    def test_list_with_nested_dicts(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NESTED_LIST_VAR", "found")
        data = {"servers": [{"host": "${NESTED_LIST_VAR}"}, {"host": "static"}]}
        result = EnvVarResolver.resolve_dict(data)
        assert result == {"servers": [{"host": "found"}, {"host": "static"}]}

    def test_missing_var_in_dict_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("MISSING_DICT_VAR", raising=False)
        data = {"key": "${MISSING_DICT_VAR}"}
        with pytest.raises(EnvVarNotFoundError, match="MISSING_DICT_VAR"):
            EnvVarResolver.resolve_dict(data)
