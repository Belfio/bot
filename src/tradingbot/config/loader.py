"""TOML configuration file loader with deep merge support."""

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_toml(path: Path) -> dict[str, Any]:
    """Load a single TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config(*paths: Path) -> dict[str, Any]:
    """Load and merge multiple TOML config files. Later files override earlier ones."""
    config: dict[str, Any] = {}
    for path in paths:
        if path.exists():
            config = deep_merge(config, load_toml(path))
    return config
