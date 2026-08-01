"""Run Pi in JSON mode for Pi Agent Bench."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .model_profiles import ModelProfile


@dataclass(frozen=True)
class PiRunConfig:
    provider: str
    model: str
    timeout_seconds: int
    executable: str = "pi"
    tools: tuple[str, ...] = ("read", "bash", "edit", "write", "grep", "find", "ls")
    isolate_resources: bool = True
    model_patterns: tuple[str, ...] = ()
    context_files_enabled: bool = True
    skills_enabled: bool = False
    extensions_enabled: bool = False
    prompt_templates_enabled: bool = False
    thinking_level: str | None = None


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


@dataclass(frozen=True)
class PiDirectUsage:
    aggregate: dict[str, int | float | None]
    cost_reported_calls: int
    observed_models: tuple[dict[str, Any], ...]
    unattributed_assistant_calls: int


def build_command(config: PiRunConfig, prompt: str) -> tuple[str, ...]:
    """Construct a fresh, non-persistent Pi JSON-mode invocation."""
    command = [
        config.executable,
        "--mode",
        "json",
        "--no-session",
        "--no-approve",
    ]
    if config.isolate_resources:
        if not config.skills_enabled:
            command.append("--no-skills")
        if not config.extensions_enabled:
            command.append("--no-extensions")
        if not config.prompt_templates_enabled:
            command.append("--no-prompt-templates")
        command.append("--no-themes")
        if not config.context_files_enabled:
            command.append("--no-context-files")
    if config.tools:
        command.extend(["--tools", ",".join(config.tools)])
    if config.thinking_level:
        command.extend(["--thinking", config.thinking_level])
    if config.model_patterns:
        command.extend(["--models", ",".join(config.model_patterns)])
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


def build_models_config(
    resources: tuple[ModelProfile, ...],
    *,
    port: int | None,
    context_tokens: int,
) -> dict[str, Any]:
    """Build the isolated Pi catalog for all configured model resources."""
    providers: dict[str, dict[str, Any]] = {}
    bridged = [
        resource for resource in resources if resource.execution_mode == "inspect-bridge"
    ]
    if bridged:
        if port is None:
            raise ValueError("bridged model resources require an Inspect bridge port")
        providers["inspect-bridge"] = {
                "baseUrl": f"http://localhost:{port}/v1",
                "api": "openai-completions",
                "apiKey": "inspect",
                "compat": {
                    "supportsDeveloperRole": False,
                    "supportsReasoningEffort": False,
                },
                "models": [
                    _pi_model_definition(resource, context_tokens)
                    for resource in bridged
                ],
        }
    for resource in resources:
        if resource.execution_mode != "pi-direct":
            continue
        provider = resource.direct_provider
        assert provider is not None
        providers.setdefault(provider, {}).setdefault("models", []).append(
            _pi_model_definition(resource, context_tokens, direct=True)
        )
    return {"providers": providers}


def model_selector(resource: ModelProfile) -> tuple[str, str]:
    """Return Pi provider/model identifiers for one configured resource."""
    if resource.execution_mode == "inspect-bridge":
        return "inspect-bridge", resource.name
    assert resource.direct_provider is not None and resource.direct_model is not None
    return resource.direct_provider, resource.direct_model


def model_patterns(resources: tuple[ModelProfile, ...]) -> tuple[str, ...]:
    return tuple("/".join(model_selector(resource)) for resource in resources)


def unconfigured_models(
    events: tuple[dict[str, Any], ...],
    resources: tuple[ModelProfile, ...],
) -> tuple[str, ...]:
    """Return attributed assistant models outside the composed profile."""
    allowed = {model_selector(resource) for resource in resources}
    unexpected: set[str] = set()
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        provider = message.get("provider")
        model = message.get("model")
        if (
            isinstance(provider, str)
            and provider
            and isinstance(model, str)
            and model
            and (provider, model) not in allowed
        ):
            unexpected.add(f"{provider}/{model}")
    return tuple(sorted(unexpected))


def _pi_model_definition(
    resource: ModelProfile,
    case_context_tokens: int,
    *,
    direct: bool = False,
) -> dict[str, Any]:
    capabilities = resource.capped_capabilities(case_context_tokens)
    return {
        "id": resource.direct_model if direct else resource.name,
        "name": resource.name,
        "reasoning": capabilities["reasoning"],
        "input": capabilities["input"],
        "contextWindow": capabilities["context_tokens"],
        "maxTokens": capabilities["max_output_tokens"],
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


def summarise_direct_usage(
    events: tuple[dict[str, Any], ...],
    direct_models: set[tuple[str, str]],
) -> PiDirectUsage:
    """Aggregate only assistant completions attributed to configured direct models."""
    messages: list[dict[str, Any]] = []
    seen: set[str] = set()
    unattributed = 0
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        response_id = message.get("responseId")
        timestamp = message.get("timestamp")
        key = (
            f"response:{response_id}"
            if isinstance(response_id, str) and response_id
            else f"timestamp:{timestamp}"
        )
        if key in seen:
            continue
        seen.add(key)
        provider = message.get("provider")
        model = message.get("model")
        if (provider, model) in direct_models:
            messages.append(message)
        elif provider != "inspect-bridge":
            unattributed += 1

    observed: dict[tuple[str, str], dict[str, Any]] = {}
    cost_reported_calls = 0
    totals: dict[str, int | float] = {
        "call_count": len(messages),
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "model_seconds": 0.0,
        "reported_cost": 0.0,
    }
    availability = {
        "input_tokens": True,
        "cached_input_tokens": True,
        "output_tokens": True,
        "reasoning_tokens": True,
        "model_seconds": True,
    }
    for message in messages:
        usage = message.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        provider = str(message["provider"])
        model = str(message["model"])
        per_model = observed.setdefault(
            (provider, model),
            {"provider": provider, "model": model, "call_count": 0},
        )
        per_model["call_count"] += 1
        values = {
            "input_tokens": _optional_usage_int(usage, "input", "input_tokens"),
            "cached_input_tokens": _optional_usage_int(
                usage, "cacheRead", "cachedInput", "cached_input_tokens"
            ),
            "output_tokens": _optional_usage_int(usage, "output", "output_tokens"),
            "reasoning_tokens": _optional_usage_int(
                usage, "reasoning", "reasoningTokens", "reasoning_tokens"
            ),
        }
        if values["input_tokens"] is not None and values["cached_input_tokens"] is not None:
            values["input_tokens"] += values["cached_input_tokens"]
        for field, value in values.items():
            if value is None:
                availability[field] = False
            else:
                totals[field] += value
        duration_ms = message.get("durationMs")
        if isinstance(duration_ms, (int, float)) and not isinstance(duration_ms, bool):
            totals["model_seconds"] += float(duration_ms) / 1000
        else:
            availability["model_seconds"] = False
        cost = _reported_cost(usage)
        if cost is not None:
            totals["reported_cost"] += cost
            cost_reported_calls += 1
    aggregate = {
        field: (
            value
            if field in {"call_count", "reported_cost"} or availability.get(field, True)
            else None
        )
        for field, value in totals.items()
    }
    return PiDirectUsage(
        aggregate=aggregate,
        cost_reported_calls=cost_reported_calls,
        observed_models=tuple(observed.values()),
        unattributed_assistant_calls=unattributed,
    )


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0


def _optional_usage_int(usage: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _reported_cost(usage: dict[str, Any]) -> float | None:
    cost = usage.get("cost")
    if isinstance(cost, dict):
        for key in ("total", "totalCost", "reported_cost"):
            value = cost.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    for key in ("cost", "total_cost", "reported_cost"):
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None
