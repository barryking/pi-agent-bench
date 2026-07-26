"""Prove a Pi Agent Bench outcome case before using it."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .inspect_tasks import load_case_suite
from .repository import REPOSITORY_ROOT
from .verification import finite_number, verifier_payload
from .versions import SANDBOX_IMAGE
from .workspace import prepare_workspace, remove_docker_workspace_contents


def prove_outcome_case(
    dataset: str | Path,
    known_good_diff: str | Path,
    output: str | Path,
) -> Path:
    """Run one protected verifier before and after a known-good patch."""
    source, cases, dataset_version = load_case_suite(dataset)
    if len(cases) != 1:
        raise ValueError("case proof needs a dataset containing exactly one outcome case")
    case = cases[0]
    if case.metadata.get("draft") is True:
        raise ValueError(f"{case.id}: finish the draft before proving it")

    starting_repository = _resolve_starting_repository(
        case.metadata.get("starting_repository"), source
    )
    patch_path = Path(known_good_diff).expanduser().resolve()
    if not patch_path.is_file():
        raise ValueError(f"known-good diff does not exist: {patch_path}")
    patch = patch_path.read_text(encoding="utf-8")
    if not patch.strip():
        raise ValueError("known-good diff is empty")

    temporary_parent = REPOSITORY_ROOT / "workspaces"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".case-proof-", dir=temporary_parent) as temporary:
        root = Path(temporary)
        try:
            before_workspace = root / "before"
            after_workspace = root / "after"
            prepare_workspace(starting_repository, "", before_workspace)
            prepare_workspace(starting_repository, patch, after_workspace)
            before = _run_verifier(before_workspace, case.expected.verifier_command)
            after = _run_verifier(after_workspace, case.expected.verifier_command)
        finally:
            remove_docker_workspace_contents(root, SANDBOX_IMAGE)

    proof = assess_case_proof(
        before,
        after,
        success_threshold=case.expected.success_threshold,
        required_components=case.expected.required_components,
    )
    record = {
        "schema_version": 1,
        "case_id": case.id,
        "dataset_version": dataset_version,
        "proved_at": datetime.now(UTC).isoformat(),
        "starting_repository": str(starting_repository),
        "source_commit": case.metadata.get("source_commit"),
        "sandbox_image": SANDBOX_IMAGE,
        "verifier_command": list(case.expected.verifier_command),
        "known_good_diff_sha256": hashlib.sha256(patch.encode()).hexdigest(),
        "required_components": list(case.expected.required_components),
        **proof,
    }
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not proof["proved"]:
        raise ValueError(
            f"{case.id}: case proof failed; see {destination} "
            f"(before={proof['before']['quality']}, after={proof['after']['quality']})"
        )
    return destination


def assess_case_proof(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    success_threshold: float,
    required_components: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Check the two scores without hiding missing or broken verifier output."""
    before_quality = _quality(before)
    after_quality = _quality(after)
    before_failed = before_quality is not None and before_quality < success_threshold
    after_components = after.get("components", {})
    critical_passed = isinstance(after_components, dict) and all(
        _component_passed(after_components.get(name)) for name in required_components
    )
    after_passed = (
        after_quality is not None and after_quality >= success_threshold and critical_passed
    )
    return {
        "success_threshold": success_threshold,
        "required_components": list(required_components),
        "before": {
            "quality": before_quality,
            "failed_as_expected": before_failed,
            "components": before.get("components", {}),
            "explanation": before.get("explanation"),
        },
        "after": {
            "quality": after_quality,
            "passed_as_expected": after_passed,
            "components": after.get("components", {}),
            "explanation": after.get("explanation"),
        },
        "proved": before_failed and after_passed,
    }


def _run_verifier(workspace: Path, command: tuple[str, ...]) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            "root",
            "--volume",
            f"{workspace}:/workspace",
            "--workdir",
            "/workspace",
            SANDBOX_IMAGE,
            *command,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    payload = verifier_payload(completed.stdout)
    payload["process_return_code"] = completed.returncode
    if completed.stderr:
        payload["process_stderr"] = completed.stderr
    return payload


def _resolve_starting_repository(value: Any, dataset: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("outcome case has no starting_repository path")
    requested = Path(value).expanduser()
    candidates = (
        [requested]
        if requested.is_absolute()
        else [dataset.parent / requested, REPOSITORY_ROOT / requested]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved
    raise ValueError(f"outcome starting_repository does not exist: {candidates[-1].resolve()}")


def _quality(payload: dict[str, Any]) -> float | None:
    return finite_number(payload.get("score"))


def _component_passed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    number = finite_number(value)
    return number is not None and number >= 1.0
