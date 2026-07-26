"""Safe temporary coding-workspace preparation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def prepare_workspace(fixture: Path, diff: str, workspace: Path) -> None:
    """Copy a fixture, reset it to its baseline, and apply an optional diff."""
    shutil.copytree(fixture, workspace, symlinks=True)
    if (workspace / ".git").exists():
        run_git(workspace, "reset", "--hard", "-q", "HEAD")
        run_git(workspace, "clean", "-ffdqx")
    else:
        run_git(workspace, "init", "-q")
        run_git(workspace, "config", "user.name", "Pi Agent Bench")
        run_git(workspace, "config", "user.email", "bench@example.invalid")
        run_git(workspace, "add", ".")
        run_git(workspace, "commit", "-qm", "baseline")
    if not diff.strip():
        return
    result = subprocess.run(
        ["git", "apply", "--binary", "-"],
        cwd=workspace,
        input=diff,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"saved diff could not be applied: {result.stderr.strip()}")


def run_git(workspace: Path, *args: str) -> None:
    """Run a checked Git command in a prepared workspace."""
    subprocess.run(
        ["git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
