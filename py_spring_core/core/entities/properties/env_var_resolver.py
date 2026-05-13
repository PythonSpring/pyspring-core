import os
import re


class EnvVarNotFoundError(Exception):
    """Raised when a ${VAR} placeholder references an unset environment variable with no default."""

    ...


class EnvVarResolver:
    """Resolves ${VAR} and ${VAR:default} placeholders in property values using environment variables."""

    _PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")

    @staticmethod
    def _replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        value = os.environ.get(var_name)
        if value is not None:
            return value
        if default is not None:
            return default
        raise EnvVarNotFoundError(
            f"[ENV VAR NOT FOUND] Environment variable '{var_name}' is not set and no default was provided"
        )

    @classmethod
    def resolve_value(cls, value: str) -> str:
        """Resolve all ${VAR} and ${VAR:default} placeholders in a string value."""
        return cls._PATTERN.sub(cls._replace_match, value)

    @classmethod
    def _resolve_item(cls, value: object) -> object:
        """Resolve a single item: string, dict, list, or pass through."""
        if isinstance(value, str):
            return cls.resolve_value(value)
        if isinstance(value, dict):
            return cls.resolve_dict(value)
        if isinstance(value, list):
            return [cls._resolve_item(item) for item in value]
        return value

    @classmethod
    def resolve_dict(cls, data: dict) -> dict:
        """Recursively resolve all ${VAR} placeholders in a nested dict."""
        return {key: cls._resolve_item(value) for key, value in data.items()}
