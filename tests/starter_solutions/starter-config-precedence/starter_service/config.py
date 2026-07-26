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
    """Combine settings without discarding false, zero, or empty values."""
    result: dict[str, Any] = {}
    for key, default in defaults.items():
        if key in command_line:
            result[key] = command_line[key]
        elif key.upper() in environment:
            result[key] = environment[key.upper()]
        elif key in file_values:
            result[key] = file_values[key]
        else:
            result[key] = default
    return result
