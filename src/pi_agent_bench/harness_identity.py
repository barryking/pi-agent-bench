"""Capture immutable benchmark and sandbox identity at run time."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .schema_versions import COHORT_SCHEMA_VERSION
from .versions import FRAMEWORK_VERSION, INSPECT_VERSION, PI_VERSION, SANDBOX_IMAGE

ROOT = Path(__file__).resolve().parents[2]
SANDBOX_LABEL = "dev.pi.benchmark-source"
SANDBOX_BUILD_SOURCE_PATHS = (
    Path(".dockerignore"),
    Path("docker/Dockerfile"),
    Path("docker/compose.yaml"),
    Path("verifiers"),
)
SANDBOX_RUNTIME_SOURCE_PATHS = (
    Path("docker/Dockerfile"),
    Path("docker/compose.yaml"),
)
EXECUTION_SOURCE_PATHS = (
    Path("pyproject.toml"),
    Path("evals/schemas"),
    Path("src/pi_agent_bench/agent_profiles.py"),
    Path("src/pi_agent_bench/case_assets.py"),
    Path("src/pi_agent_bench/cli_execution.py"),
    Path("src/pi_agent_bench/dataset.py"),
    Path("src/pi_agent_bench/inspect_agent.py"),
    Path("src/pi_agent_bench/inspect_scorers.py"),
    Path("src/pi_agent_bench/inspect_tasks.py"),
    Path("src/pi_agent_bench/model_profiles.py"),
    Path("src/pi_agent_bench/pi_guard.py"),
    Path("src/pi_agent_bench/pi_profiles.py"),
    Path("src/pi_agent_bench/pi_runner.py"),
    Path("src/pi_agent_bench/verification.py"),
    Path("src/pi_agent_bench/versions.py"),
)


def repository_identity(root: Path = ROOT) -> dict[str, Any]:
    """Describe the exact repository state used to start a benchmark run."""

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    return {
        "repository_commit": git("rev-parse", "HEAD") or None,
        "repository_branch": git("branch", "--show-current") or None,
        "repository_dirty": bool(git("status", "--porcelain=v1")),
    }


def sandbox_source_fingerprint(root: Path = ROOT) -> str:
    """Hash only source files that affect the protected sandbox image."""

    paths: list[Path] = []
    for relative in SANDBOX_BUILD_SOURCE_PATHS:
        path = root / relative
        if path.is_dir():
            paths.extend(item.relative_to(root) for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            paths.append(relative)
    return _paths_fingerprint(root, paths)


def sandbox_runtime_fingerprint(root: Path = ROOT) -> str:
    """Hash the common sandbox runtime without case-specific verifiers."""
    return _selected_source_fingerprint(root, SANDBOX_RUNTIME_SOURCE_PATHS)


def execution_protocol_fingerprint(root: Path = ROOT) -> str:
    """Hash only framework source capable of changing execution or scoring."""
    return _selected_source_fingerprint(root, EXECUTION_SOURCE_PATHS)


def build_sandbox(root: Path = ROOT) -> None:
    """Build the sandbox and label it with the exact protected source hash."""

    fingerprint = sandbox_source_fingerprint(root)
    subprocess.run(
        [
            "docker",
            "build",
            "--provenance=false",
            "--tag",
            SANDBOX_IMAGE,
            "--file",
            "docker/Dockerfile",
            "--build-arg",
            f"BENCHMARK_SOURCE_FINGERPRINT={fingerprint}",
            "--build-arg",
            f"PI_VERSION={PI_VERSION}",
            "--build-arg",
            f"FRAMEWORK_VERSION={FRAMEWORK_VERSION}",
            ".",
        ],
        cwd=root,
        check=True,
    )


def sandbox_identity(
    root: Path = ROOT,
    *,
    require_fresh: bool = True,
) -> dict[str, Any]:
    """Inspect the local sandbox and optionally reject stale image content."""

    result = subprocess.run(
        ["docker", "image", "inspect", SANDBOX_IMAGE],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            f"sandbox image {SANDBOX_IMAGE} is missing; run `pi-bench build-sandbox`"
        )
    try:
        [image] = json.loads(result.stdout)
        image_id = image["Id"]
        labels = image.get("Config", {}).get("Labels", {}) or {}
        repo_digests = image.get("RepoDigests") or []
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read sandbox image identity for {SANDBOX_IMAGE}") from exc

    expected = sandbox_source_fingerprint(root)
    actual = labels.get(SANDBOX_LABEL)
    if require_fresh and actual != expected:
        reason = "has no source fingerprint" if not actual else "does not match this checkout"
        raise ValueError(
            f"sandbox image {SANDBOX_IMAGE} {reason}; run `pi-bench build-sandbox`"
        )
    expected_labels = {
        "dev.pi.version": PI_VERSION,
        "org.opencontainers.image.version": FRAMEWORK_VERSION,
    }
    if require_fresh:
        mismatches = [
            f"{name}={labels.get(name)!r}, expected {expected_value!r}"
            for name, expected_value in expected_labels.items()
            if labels.get(name) != expected_value
        ]
        if mismatches:
            raise ValueError(
                f"sandbox image {SANDBOX_IMAGE} has stale version labels "
                f"({'; '.join(mismatches)}); run `pi-bench build-sandbox`"
            )
    return {
        "sandbox_image": SANDBOX_IMAGE,
        "sandbox_image_id": image_id,
        "sandbox_repo_digests": sorted(str(value) for value in repo_digests),
        "sandbox_source_fingerprint": actual,
    }


def capture_harness_identity(root: Path = ROOT) -> dict[str, Any]:
    """Capture the immutable harness facts stored in every Inspect log."""

    return {
        "framework_version": FRAMEWORK_VERSION,
        "pi_version_expected": PI_VERSION,
        "inspect_version": INSPECT_VERSION,
        "execution_protocol_fingerprint": execution_protocol_fingerprint(root),
        "sandbox_runtime_fingerprint": sandbox_runtime_fingerprint(root),
        **repository_identity(root),
        **sandbox_identity(root),
    }


def validate_harness_identity(value: Any) -> dict[str, Any]:
    """Validate identity read from an Inspect log without recalculating it."""

    if not isinstance(value, dict):
        raise ValueError("Inspect log has incomplete harness identity")
    normalized = dict(value)
    # Schema-5 logs used one broad source hash. Preserve their rebuildability
    # while new logs record the two narrower identities explicitly.
    for current, legacy in (
        ("execution_protocol_fingerprint", "harness_source_fingerprint"),
        ("sandbox_runtime_fingerprint", "sandbox_source_fingerprint"),
    ):
        if normalized.get(current) is None and normalized.get(legacy):
            normalized[current] = normalized[legacy]
    required = {
        "framework_version",
        "pi_version_expected",
        "inspect_version",
        "repository_commit",
        "repository_branch",
        "repository_dirty",
        "execution_protocol_fingerprint",
        "sandbox_runtime_fingerprint",
        "sandbox_image",
        "sandbox_image_id",
        "sandbox_repo_digests",
        "sandbox_source_fingerprint",
    }
    if not required.issubset(normalized):
        missing = sorted(required - set(normalized))
        raise ValueError(f"Inspect log has incomplete harness identity: {', '.join(missing)}")
    empty_fingerprints = sorted(
        field
        for field in (
            "execution_protocol_fingerprint",
            "sandbox_runtime_fingerprint",
        )
        if not isinstance(normalized.get(field), str) or not normalized[field]
    )
    if empty_fingerprints:
        raise ValueError(
            "Inspect log has incomplete harness identity: "
            + ", ".join(empty_fingerprints)
        )
    return normalized


def cohort_identity(
    dataset: str | Path,
    *,
    cache_state: str,
    cost_limit: float | None,
    harness: dict[str, Any],
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build the shared use-case and environment identity for comparison arms."""
    from .case_assets import resolve_starting_repository
    from .dataset import load_cases

    source = Path(dataset).expanduser()
    if not source.is_absolute():
        source = root / source
    source = source.resolve()
    cases = load_cases(source)
    dataset_versions = {
        str(case.metadata.get("dataset_version", "")).strip() for case in cases
    }
    case_identities = []
    for case in cases:
        starting_value = case.metadata.get("starting_repository")
        if not isinstance(starting_value, str) or not starting_value:
            raise ValueError(f"{case.id}: metadata.starting_repository must be a path")
        starting_repository = resolve_starting_repository(starting_value, source)
        verifier = root / "verifiers" / case.id / "verify.py"
        case_identities.append(
            {
                "id": case.id,
                "instruction_sha256": _value_fingerprint(case.instruction),
                "starting_repository_sha256": _tree_fingerprint(starting_repository),
                "source_commit": case.metadata.get("source_commit"),
                "verifier_sha256": _file_fingerprint(verifier),
                "scoring": {
                    "verifier_command": list(case.expected.verifier_command),
                    "success_threshold": case.expected.success_threshold,
                    "required_components": list(case.expected.required_components),
                    "score_components": list(case.metadata.get("score_components", [])),
                },
                "limits": {
                    "seconds": case.limits.seconds,
                    "turns": case.limits.turns,
                    "context_tokens": case.limits.context_tokens,
                    "total_tokens": case.limits.total_tokens,
                },
            }
        )
    dataset_version = next(iter(dataset_versions)) if len(dataset_versions) == 1 else None
    canonical = {
        "cohort_schema_version": COHORT_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "cases": case_identities,
        "cache_state": cache_state,
        "cost_limit": cost_limit,
        "pi_version": harness["pi_version_expected"],
        "inspect_version": harness["inspect_version"],
        "execution_protocol_fingerprint": harness.get(
            "execution_protocol_fingerprint",
            harness.get("harness_source_fingerprint"),
        ),
        "sandbox_runtime_fingerprint": harness.get(
            "sandbox_runtime_fingerprint",
            harness["sandbox_source_fingerprint"],
        ),
    }
    evidence = {
        # These facts are retained for audit but do not split otherwise identical
        # use cases and execution conditions into different comparison cohorts.
        "dataset_file_sha256": _file_fingerprint(source),
        "framework_version": harness["framework_version"],
        "sandbox_image_id": harness["sandbox_image_id"],
        "sandbox_build_source_fingerprint": harness["sandbox_source_fingerprint"],
    }
    return {
        "cohort_fingerprint": _value_fingerprint(canonical),
        **canonical,
        "evidence": evidence,
    }


def _paths_fingerprint(root: Path, paths: list[Path]) -> str:
    fingerprint = hashlib.sha256()
    for relative in sorted(set(paths)):
        path = root / relative
        if not path.is_file():
            continue
        fingerprint.update(str(relative).encode())
        fingerprint.update(b"\0")
        fingerprint.update(path.read_bytes())
        fingerprint.update(b"\0")
    return fingerprint.hexdigest()


def _selected_source_fingerprint(root: Path, selections: tuple[Path, ...]) -> str:
    paths: list[Path] = []
    for relative in selections:
        path = root / relative
        if path.is_dir():
            paths.extend(item.relative_to(root) for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            paths.append(relative)
    return _paths_fingerprint(root, paths)


def _tree_fingerprint(root: Path) -> str:
    fingerprint = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        fingerprint.update(relative.as_posix().encode())
        fingerprint.update(b"\0")
        fingerprint.update(path.read_bytes())
        fingerprint.update(b"\0")
    return fingerprint.hexdigest()


def _file_fingerprint(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"identity source does not exist: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
