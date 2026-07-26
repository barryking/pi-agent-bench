"""Resolve files named by benchmark cases and saved Inspect logs."""

from __future__ import annotations

from pathlib import Path

from .repository import REPOSITORY_ROOT


def resolve_starting_repository(
    value: object,
    dataset_path: str | Path | None,
) -> Path:
    """Resolve one starting repository relative to its dataset or the clone."""
    if not isinstance(value, str) or not value:
        raise ValueError("outcome case has no starting_repository path")
    requested = Path(value).expanduser()
    candidates = [requested] if requested.is_absolute() else []
    if dataset_path is not None:
        dataset = Path(dataset_path).expanduser().resolve()
        candidates.append(dataset.parent / requested)
    candidates.append(REPOSITORY_ROOT / requested)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved
    raise ValueError(
        f"starting repository directory does not exist: {candidates[-1].resolve()}"
    )
