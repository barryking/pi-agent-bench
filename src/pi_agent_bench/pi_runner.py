"""Run Pi in JSON mode for Pi Agent Bench."""

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
    tools: tuple[str, ...] = ("read", "bash", "edit", "write", "grep", "find", "ls")
    isolate_resources: bool = True
    thinking_level: str | None = None


@dataclass(frozen=True)
class PiRunResult:
    command: tuple[str, ...]
    return_code: int
    wall_seconds: float
    events: tuple[dict[str, Any], ...]
    non_json_lines: tuple[str, ...]
    stderr: str


@dataclass(frozen=True)
class PiEventSummary:
    turns: int
    tool_calls: int
    failed_tool_calls: int
    compactions: int
    retries: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


def build_command(config: PiRunConfig, prompt: str) -> tuple[str, ...]:
    """Construct a fresh, non-persistent Pi JSON-mode invocation."""
    trust_flag = "--approve" if config.trust_mode == "approve" else "--no-approve"
    command = [
        config.executable,
        "--mode",
        "json",
        "--no-session",
        trust_flag,
    ]
    if config.isolate_resources:
        command.extend(
            [
                "--no-skills",
                "--no-extensions",
                "--no-prompt-templates",
                "--no-themes",
                "--no-context-files",
            ]
        )
    if config.tools:
        command.extend(["--tools", ",".join(config.tools)])
    if config.thinking_level:
        command.extend(["--thinking", config.thinking_level])
    command.extend(
        [
        "--provider",
        config.provider,
        "--model",
        config.model,
        prompt,
        ]
    )
    return tuple(command)


def build_bridge_models_config(port: int, context_tokens: int) -> dict[str, Any]:
    """Return a minimal Pi custom-provider file for Inspect's sandbox bridge."""
    return {
        "providers": {
            "inspect-bridge": {
                "baseUrl": f"http://localhost:{port}/v1",
                "api": "openai-completions",
                "apiKey": "inspect",
                "compat": {
                    "supportsDeveloperRole": False,
                    "supportsReasoningEffort": False,
                },
                "models": [
                    {
                        "id": "inspect",
                        "name": "Inspect model bridge",
                        "contextWindow": context_tokens,
                        "maxTokens": min(32768, max(1024, context_tokens // 4)),
                    }
                ],
            }
        }
    }


def parse_json_events(stdout: str) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    """Split Pi JSON mode output into structured events and unexpected lines."""
    events: list[dict[str, Any]] = []
    non_json_lines: list[str] = []
    for raw_line in stdout.splitlines():
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError:
            non_json_lines.append(raw_line)
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            non_json_lines.append(raw_line)
    return tuple(events), tuple(non_json_lines)


def summarise_events(events: tuple[dict[str, Any], ...]) -> PiEventSummary:
    """Summarise stable Pi JSON event fields without copying the trajectory."""
    turns = sum(event.get("type") == "turn_start" for event in events)
    tool_calls = sum(event.get("type") == "tool_execution_start" for event in events)
    failed_tool_calls = sum(
        event.get("type") == "tool_execution_end" and event.get("isError") is True
        for event in events
    )
    compactions = sum(event.get("type") == "compaction_start" for event in events)
    retries = sum(event.get("type") == "auto_retry_start" for event in events)
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        uncached_input = _usage_int(usage, "input", "input_tokens")
        cached_input = _usage_int(
            usage, "cacheRead", "cachedInput", "cached_input_tokens"
        )
        input_tokens += uncached_input + cached_input
        cached_input_tokens += cached_input
        output_tokens += _usage_int(usage, "output", "output_tokens")
    return PiEventSummary(
        turns=turns,
        tool_calls=tool_calls,
        failed_tool_calls=failed_tool_calls,
        compactions=compactions,
        retries=retries,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
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

    events, non_json_lines = parse_json_events(completed.stdout)

    return PiRunResult(
        command=command,
        return_code=completed.returncode,
        wall_seconds=wall_seconds,
        events=events,
        non_json_lines=non_json_lines,
        stderr=completed.stderr,
    )


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0
