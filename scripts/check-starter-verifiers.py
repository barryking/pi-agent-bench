#!/usr/bin/env python3
"""Prove every owned starter verifier against baseline and reference code."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pi_agent_bench.versions import SANDBOX_IMAGE
from pi_agent_bench.workspace import remove_docker_workspace_contents

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "starter" / "cases.jsonl"
SOLUTIONS = ROOT / "tests" / "starter_solutions"
IMAGE = SANDBOX_IMAGE


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def verifier_result(workspace: Path, command: list[str]) -> dict[str, Any]:
    completed = run(
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
            IMAGE,
            *command,
        ]
    )
    for line in reversed(completed.stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError(
        f"verifier produced no JSON (exit {completed.returncode}): "
        f"{completed.stdout}\n{completed.stderr}"
    )


def prepare(starting_repository: Path, workspace: Path) -> None:
    shutil.copytree(starting_repository, workspace)
    commands = (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Starter proof"],
        ["git", "config", "user.email", "proof@example.invalid"],
        ["git", "add", "."],
        ["git", "commit", "-qm", "baseline"],
    )
    for command in commands:
        completed = run(command, cwd=workspace)
        if completed.returncode:
            raise RuntimeError(completed.stderr)


def main() -> int:
    cases = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    first_verifier = cases[0]["expected"]["verifier_command"][1]
    protected = run(
        [
            "docker",
            "run",
            "--rm",
            IMAGE,
            "python3",
            "-c",
            (
                "import os, sys; "
                "raise SystemExit(0 if not os.access(sys.argv[1], os.R_OK) else 1)"
            ),
            first_verifier,
        ]
    )
    if protected.returncode:
        raise RuntimeError(
            f"Pi sandbox user can read protected verifier {first_verifier}"
        )
    print("proved: protected verifiers are unreadable to the Pi sandbox user")
    with tempfile.TemporaryDirectory(prefix="starter-verifiers-") as temporary:
        root = Path(temporary)
        try:
            for case in cases:
                case_id = case["id"]
                starting_repository = ROOT / case["metadata"]["starting_repository"]
                workspace = root / case_id
                prepare(starting_repository, workspace)
                before = verifier_result(
                    workspace, case["expected"]["verifier_command"]
                )
                threshold = float(case["expected"]["success_threshold"])
                if float(before.get("score", 1.0)) >= threshold:
                    raise RuntimeError(
                        f"{case_id}: untouched starting repository unexpectedly passed"
                    )

                shutil.copytree(SOLUTIONS / case_id, workspace, dirs_exist_ok=True)
                after = verifier_result(
                    workspace, case["expected"]["verifier_command"]
                )
                components = after.get("components", {})
                missing = [
                    name
                    for name in case["expected"]["required_components"]
                    if components.get(name) != 1.0
                ]
                if float(after.get("score", 0.0)) < threshold or missing:
                    raise RuntimeError(
                        f"{case_id}: reference solution failed; "
                        f"score={after.get('score')}, missing={missing}, "
                        f"explanation={after.get('explanation')}"
                    )
                print(
                    f"proved: {case_id}; "
                    f"before={before['score']}; after={after['score']}"
                )
        finally:
            remove_docker_workspace_contents(root, IMAGE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
