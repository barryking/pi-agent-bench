"""Normalize bridged and Pi-direct usage from one Inspect sample."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .verification import finite_number


@dataclass(frozen=True)
class _PathUsage:
    values: dict[str, Any]
    call_count: int
    cloud_cost_states: list[bool]
    observed_models: list[dict[str, Any]]


def inspect_timing(sample: Any) -> dict[str, float | int | None]:
    """Build small timing facts from Inspect events, which remain the source."""
    model_seconds = 0.0
    tool_seconds = 0.0
    model_output_tokens = 0
    model_calls = 0
    tool_calls = 0
    for event in getattr(sample, "events", None) or []:
        event_type = getattr(event, "event", None)
        seconds = getattr(event, "working_time", None)
        if event_type == "model" and getattr(event, "role", None) in {None, ""}:
            model_calls += 1
            if finite_number(seconds) is not None:
                model_seconds += float(seconds)
            output = getattr(event, "output", None)
            usage = getattr(output, "usage", None)
            tokens = getattr(usage, "output_tokens", None)
            if isinstance(tokens, int) and not isinstance(tokens, bool):
                model_output_tokens += tokens
        elif event_type == "tool":
            tool_calls += 1
            if finite_number(seconds) is not None:
                tool_seconds += float(seconds)
    working_seconds = getattr(sample, "working_time", None)
    return {
        "inspect_working_seconds": (
            float(working_seconds) if finite_number(working_seconds) is not None else None
        ),
        "model_working_seconds": model_seconds if model_calls else None,
        "tool_working_seconds": tool_seconds if tool_calls else None,
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "model_output_tokens": model_output_tokens if model_calls else None,
        "observed_output_tokens_per_model_second": (
            model_output_tokens / model_seconds
            if model_output_tokens and model_seconds > 0
            else None
        ),
    }


def usage_record(
    sample: Any,
    score_metadata: dict[str, Any],
    agent_identity: dict[str, Any],
    timing: dict[str, float | int | None],
) -> dict[str, Any]:
    """Merge path-level usage without treating missing measurements as zero."""
    resources = agent_identity["model_resources"]
    bridged = _bridged_path_usage(sample, timing, resources)
    direct = _direct_path_usage(score_metadata, resources)
    total = {
        "call_count": bridged.call_count + direct.call_count,
        **{
            field: _merge_usage_field(bridged.values, direct.values, field)
            for field in (
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "model_seconds",
            )
        },
        "reported_cost": float(bridged.values["reported_cost"])
        + _numeric(direct.values.get("reported_cost")),
    }
    cloud_cost_states = [*bridged.cloud_cost_states, *direct.cloud_cost_states]
    if not cloud_cost_states or all(cloud_cost_states):
        coverage = "complete"
    elif any(cloud_cost_states):
        coverage = "partial"
    else:
        coverage = "unavailable"
    return {
        "bridged": bridged.values,
        "direct": direct.values,
        "total": total,
        "cost_coverage": coverage,
        "observed_models": [*bridged.observed_models, *direct.observed_models],
    }


def _bridged_path_usage(
    sample: Any,
    timing: dict[str, float | int | None],
    resources: list[dict[str, Any]],
) -> _PathUsage:
    raw = json_value(sample.model_usage or {})
    raw = raw if isinstance(raw, dict) else {}
    bridge_calls = timing.get("model_calls")
    call_count = int(bridge_calls) if isinstance(bridge_calls, int) else len(raw)
    if raw and call_count == 0:
        call_count = len(raw)
    values = {
        "call_count": call_count,
        "input_tokens": _strict_usage_sum(raw, "input_tokens", call_count),
        "cached_input_tokens": _strict_usage_sum(
            raw, "input_tokens_cache_read", call_count
        ),
        "output_tokens": _strict_usage_sum(raw, "output_tokens", call_count),
        "reasoning_tokens": _strict_usage_sum(raw, "reasoning_tokens", call_count),
        "model_seconds": timing.get("model_working_seconds") if call_count else 0.0,
        "reported_cost": 0.0,
    }
    cloud_cost_states: list[bool] = []
    observed_models: list[dict[str, Any]] = []
    for observed_model, model_usage in raw.items():
        if not isinstance(model_usage, dict):
            continue
        resource = _bridged_resource(resources, str(observed_model))
        observed_models.append(
            {
                "provider": _provider_from_model(str(observed_model)),
                "model": str(observed_model),
                "execution": "inspect-bridge",
            }
        )
        if resource is None or resource.get("kind") == "hosted":
            cost = model_usage.get("total_cost")
            has_cost = isinstance(cost, (int, float)) and not isinstance(cost, bool)
            cloud_cost_states.append(has_cost)
            if has_cost:
                values["reported_cost"] += float(cost)
    if call_count and not raw and any(
        resource.get("kind") == "hosted"
        and resource.get("execution", {}).get("mode") == "inspect-bridge"
        for resource in resources
    ):
        cloud_cost_states.append(False)
    return _PathUsage(values, call_count, cloud_cost_states, observed_models)


def _direct_path_usage(
    score_metadata: dict[str, Any],
    resources: list[dict[str, Any]],
) -> _PathUsage:
    values = score_metadata.get("pi_direct_usage")
    values = dict(values) if isinstance(values, dict) else _empty_usage()
    call_count = values.get("call_count")
    if not isinstance(call_count, int) or isinstance(call_count, bool):
        call_count = 0
        values["call_count"] = 0

    observed = score_metadata.get("pi_observed_models")
    observed = observed if isinstance(observed, list) else []
    reported_remaining = score_metadata.get("pi_direct_cost_reported_calls", 0)
    reported_remaining = (
        int(reported_remaining)
        if isinstance(reported_remaining, int)
        and not isinstance(reported_remaining, bool)
        else 0
    )
    cloud_cost_states: list[bool] = []
    observed_models: list[dict[str, Any]] = []
    for item in observed:
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        model = item.get("model")
        calls = item.get("call_count")
        observed_models.append(
            {
                "provider": provider,
                "model": model,
                "call_count": calls,
                "execution": "pi-direct",
            }
        )
        resource = _direct_resource(resources, provider, model)
        if resource is None or resource.get("kind") == "hosted":
            model_calls = (
                int(calls)
                if isinstance(calls, int) and not isinstance(calls, bool)
                else 0
            )
            reported_calls = min(reported_remaining, model_calls)
            reported_remaining -= reported_calls
            cloud_cost_states.extend(
                [True] * reported_calls + [False] * (model_calls - reported_calls)
            )

    unattributed = score_metadata.get("pi_unattributed_assistant_calls", 0)
    if (
        isinstance(unattributed, int)
        and not isinstance(unattributed, bool)
        and unattributed > 0
        and any(
            resource.get("execution", {}).get("mode") == "pi-direct"
            for resource in resources
        )
    ):
        for field in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "model_seconds",
        ):
            values[field] = None
        cloud_cost_states.extend([False] * unattributed)
    return _PathUsage(values, call_count, cloud_cost_states, observed_models)


def json_value(value: Any) -> Any:
    """Convert Inspect/Pydantic values into finite JSON-compatible data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _empty_usage() -> dict[str, int | float]:
    return {
        "call_count": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "model_seconds": 0.0,
        "reported_cost": 0.0,
    }


def _strict_usage_sum(
    values: dict[str, Any],
    field: str,
    call_count: int,
) -> int | None:
    if call_count == 0:
        return 0
    numbers = []
    for value in values.values():
        if not isinstance(value, dict):
            return None
        item = value.get(field)
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            return None
        numbers.append(int(item))
    return sum(numbers) if numbers else None


def _merge_usage_field(
    bridged: dict[str, Any],
    direct: dict[str, Any],
    field: str,
) -> int | float | None:
    values = []
    for usage in (bridged, direct):
        if usage.get("call_count", 0) == 0:
            continue
        value = usage.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        values.append(value)
    return sum(values) if values else 0


def _bridged_resource(resources: list[dict[str, Any]], model: str) -> dict[str, Any] | None:
    for resource in resources:
        if (
            resource.get("execution", {}).get("mode") == "inspect-bridge"
            and resource.get("model") == model
        ):
            return resource
    return None


def _direct_resource(
    resources: list[dict[str, Any]],
    provider: Any,
    model: Any,
) -> dict[str, Any] | None:
    for resource in resources:
        execution = resource.get("execution", {})
        if (
            execution.get("mode") == "pi-direct"
            and execution.get("provider") == provider
            and execution.get("model") == model
        ):
            return resource
    return None


def _provider_from_model(model: str) -> str | None:
    return model.split("/", 1)[0] if "/" in model else None


def _numeric(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
