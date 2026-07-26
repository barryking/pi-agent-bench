"""Shared parsing for Inspect scores and protected verifier output."""

from __future__ import annotations

import json
import math
from typing import Any


def primary_score(scores: dict[str, Any]) -> tuple[str, Any | None]:
    """Choose the score containing benchmark quality, then fall back safely."""
    for name, score in scores.items():
        if isinstance(score.value, dict) and "quality" in score.value:
            return name, score
    return next(iter(scores.items()), ("unscored", None))


def quality_value(value: Any) -> float | None:
    """Read a finite quality number from a scalar or Inspect score dictionary."""
    if isinstance(value, dict):
        value = value.get("quality")
    return finite_number(value)


def finite_number(value: Any) -> float | None:
    """Return a finite real number without accepting booleans."""
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        return float(value)
    return None


def verifier_payload(stdout: str) -> dict[str, Any]:
    """Read the last JSON object emitted by a protected verifier."""
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {
        "score": 0.0,
        "explanation": "verifier did not emit a JSON object",
    }
