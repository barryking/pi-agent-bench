"""Capture immutable benchmark and sandbox identity at run time."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .versions import FRAMEWORK_VERSION, INSPECT_VERSION, PI_VERSION, SANDBOX_IMAGE

ROOT = Path(__file__).resolve().parents[2]
SANDBOX_LABEL = "dev.pi.benchmark-source"
SANDBOX_SOURCE_PATHS = (
    Path(".dockerignore"),
    Path("docker/Dockerfile"),
    Path("docker/compose.yaml"),
    Path("verifiers"),
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

    paths = [
        Path(line)
        for line in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
        if line
    ]
    return {
        "repository_commit": git("rev-parse", "HEAD") or None,
        "repository_branch": git("branch", "--show-current") or None,
        "repository_dirty": bool(git("status", "--porcelain=v1")),
        "benchmark_fingerprint": _paths_fingerprint(root, paths),
    }


def sandbox_source_fingerprint(root: Path = ROOT) -> str:
    """Hash only source files that affect the protected sandbox image."""

    paths: list[Path] = []
    for relative in SANDBOX_SOURCE_PATHS:
        path = root / relative
        if path.is_dir():
            paths.extend(item.relative_to(root) for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            paths.append(relative)
    return _paths_fingerprint(root, paths)


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
        **repository_identity(root),
        **sandbox_identity(root),
    }


def validate_harness_identity(value: Any) -> dict[str, Any]:
    """Validate identity read from an Inspect log without recalculating it."""

    required = {
        "framework_version",
        "pi_version_expected",
        "inspect_version",
        "repository_commit",
        "repository_branch",
        "repository_dirty",
        "benchmark_fingerprint",
        "sandbox_image",
        "sandbox_image_id",
        "sandbox_repo_digests",
        "sandbox_source_fingerprint",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        missing = sorted(required - set(value if isinstance(value, dict) else {}))
        raise ValueError(f"Inspect log has incomplete harness identity: {', '.join(missing)}")
    return dict(value)


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
