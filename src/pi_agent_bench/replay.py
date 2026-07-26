"""Replay Pi Agent Bench coding diffs."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inspect_ai.log import read_eval_log

from .verification import finite_number, primary_score, quality_value, verifier_payload
from .versions import SANDBOX_IMAGE
from .workspace import prepare_workspace, remove_docker_workspace_contents

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def replay_coding_log(
    log_file: str | Path,
    output_dir: str | Path = "results/replay",
) -> list[Path]:
    """Reconstruct coding workspaces, apply saved diffs, and rerun verifiers."""
    source = Path(log_file).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Inspect log does not exist: {source}")
    log = read_eval_log(source)
    if str(log.status) != "success":
        raise ValueError(f"coding replay requires a successful log, got {log.status}")
    samples = log.samples or []
    if not samples or any(sample.metadata.get("phase") != "coding" for sample in samples):
        raise ValueError("coding replay requires a completed coding Inspect log")

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    replay_root = REPOSITORY_ROOT / "repos"
    replay_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for sample in samples:
        _, score = primary_score(sample.scores or {})
        if score is None:
            raise ValueError(f"{sample.id}: coding log has no score")
        metadata = score.metadata or {}
        final_diff = metadata.get("final_diff")
        if not isinstance(final_diff, str):
            raise ValueError(f"{sample.id}: coding score has no saved final diff")
        fixture = _resolve_fixture(
            sample.metadata.get("fixture"),
            log.eval.metadata.get("dataset_path") if log.eval.metadata else None,
        )
        verifier = (
            sample.metadata.get("expected", {}).get("verifier_command")
            if isinstance(sample.metadata.get("expected"), dict)
            else None
        )
        if not isinstance(verifier, list) or not all(
            isinstance(item, str) and item for item in verifier
        ):
            raise ValueError(f"{sample.id}: log has no valid verifier command")

        with tempfile.TemporaryDirectory(
            prefix=f".replay-{sample.id}-",
            dir=replay_root,
        ) as temporary:
            workspace = Path(temporary) / "workspace"
            try:
                prepare_workspace(fixture, final_diff, workspace)
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
                        *verifier,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
            finally:
                remove_docker_workspace_contents(workspace, SANDBOX_IMAGE)
        payload = verifier_payload(completed.stdout)
        original_quality = quality_value(score.value)
        replay_quality = finite_number(payload.get("score"))
        record = {
            "schema_version": 1,
            "run_id": log.eval.run_id,
            "case_id": str(sample.id),
            "trial_number": sample.epoch,
            "source_inspect_log": str(source),
            "replayed_at": datetime.now(UTC).isoformat(),
            "sandbox_image": SANDBOX_IMAGE,
            "fixture": str(fixture),
            "verifier_command": verifier,
            "original_quality": original_quality,
            "replay_quality": replay_quality,
            "score_matches": (
                original_quality is not None
                and replay_quality is not None
                and abs(original_quality - replay_quality) < 1e-9
            ),
            "verifier": {
                "return_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "payload": payload,
            },
        }
        path = destination / (
            f"{log.eval.run_id}__{sample.id}__trial-{sample.epoch}.replay.json"
        )
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def _resolve_fixture(value: Any, dataset_path: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("coding sample has no fixture path")
    requested = Path(value).expanduser()
    candidates = [requested] if requested.is_absolute() else []
    if isinstance(dataset_path, str) and dataset_path:
        candidates.append(Path(dataset_path).expanduser().resolve().parent / requested)
    candidates.append(REPOSITORY_ROOT / requested)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved
    raise ValueError(f"coding fixture does not exist: {candidates[-1].resolve()}")
