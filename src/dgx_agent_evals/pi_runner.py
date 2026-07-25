"""Run Pi in JSON event mode and retain its raw trajectory."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

TrustMode = Literal["approve", "no-approve"]


@dataclass(frozen=True)
class PiRunConfig:
    provider: str
    model: str
    timeout_seconds: int
    trust_mode: TrustMode = "no-approve"
    executable: str = "pi"


@dataclass(frozen=True)
class PiRunResult:
    command: tuple[str, ...]
    return_code: int
    wall_seconds: float
    events: tuple[dict[str, Any], ...]
    non_json_lines: tuple[str, ...]
    stderr: str


def build_command(config: PiRunConfig, prompt: str) -> tuple[str, ...]:
    """Construct a fresh, non-persistent Pi JSON-mode invocation."""
    trust_flag = "--approve" if config.trust_mode == "approve" else "--no-approve"
    return (
        config.executable,
        "--mode",
        "json",
        "--no-session",
        trust_flag,
        "--provider",
        config.provider,
        "--model",
        config.model,
        prompt,
    )


def run_pi(config: PiRunConfig, prompt: str, workspace: str | Path) -> PiRunResult:
    """Execute Pi.

    The caller is responsible for providing a disposable, appropriately
    sandboxed workspace. This function does not weaken process isolation.
    """
    command = build_command(config, prompt)
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=Path(workspace),
        text=True,
        capture_output=True,
        timeout=config.timeout_seconds,
        check=False,
    )
    wall_seconds = time.perf_counter() - started

    events: list[dict[str, Any]] = []
    non_json_lines: list[str] = []
    for raw_line in completed.stdout.splitlines():
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError:
            non_json_lines.append(raw_line)
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            non_json_lines.append(raw_line)

    return PiRunResult(
        command=command,
        return_code=completed.returncode,
        wall_seconds=wall_seconds,
        events=tuple(events),
        non_json_lines=tuple(non_json_lines),
        stderr=completed.stderr,
    )
