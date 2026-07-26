"""Find the checked-out Pi Agent Bench repository."""

from __future__ import annotations

from pathlib import Path

REQUIRED_PATHS = (
    Path("pyproject.toml"),
    Path("docker/compose.yaml"),
    Path("evals/schemas/golden-case.schema.json"),
)


def repository_root(start: str | Path | None = None) -> Path:
    """Return the clone root or explain that a source checkout is required."""
    source = Path(start).resolve() if start is not None else Path(__file__).resolve()
    candidates = (source, *source.parents) if source.is_dir() else source.parents
    for candidate in candidates:
        if all((candidate / required).is_file() for required in REQUIRED_PATHS):
            return candidate
    raise RuntimeError(
        "Pi Agent Bench needs a cloned repository because its cases, verifiers, "
        "Docker files, and reports live beside the Python package. Clone the repository, "
        "run ./scripts/bootstrap-mac.sh, and use pi-bench from that checkout."
    )


REPOSITORY_ROOT = repository_root()
