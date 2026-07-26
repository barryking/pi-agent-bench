"""Application configuration loading."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def load_config(
    defaults: Mapping[str, Any],
    file_values: Mapping[str, Any],
    environment: Mapping[str, Any],
    command_line: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine settings using command line, environment, file, then defaults."""
    return {
        key: (
            command_line.get(key)
            or environment.get(key.upper())
            or file_values.get(key)
            or default
        )
        for key, default in defaults.items()
    }
