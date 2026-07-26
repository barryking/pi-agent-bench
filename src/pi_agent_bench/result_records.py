"""Read and normalise compact benchmark result records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_records(source: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(source.glob("*.json")):
        if path.name == "summary.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("validity", {}).get("valid") is False:
            continue
        validate_record(record, path)
        records.append(record)
    return records


def validate_record(record: dict[str, Any], path: Path) -> None:
    if record.get("schema_version") != 4:
        raise ValueError(f"{path}: expected run record schema_version 4")
    for field in ("run_id", "case_id", "dataset_version", "run_name"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError(f"{path}: run record is missing {field}")
    if record.get("cache_state") not in {"unspecified", "cold", "warm"}:
        raise ValueError(f"{path}: cache_state must be unspecified, cold, or warm")
    for field in ("model_configuration", "agent_configuration"):
        identity = record.get(field)
        if not isinstance(identity, dict) or not identity.get("profile"):
            raise ValueError(f"{path}: run record is missing {field}.profile")
        if not isinstance(identity.get("configuration"), dict):
            raise ValueError(f"{path}: run record is missing {field}.configuration")
        if not identity.get("configuration_fingerprint"):
            raise ValueError(
                f"{path}: run record is missing {field}.configuration_fingerprint"
            )
    harness = record.get("harness")
    required_harness = {
        "benchmark_fingerprint",
        "sandbox_image_id",
        "sandbox_source_fingerprint",
    }
    if not isinstance(harness, dict) or not required_harness.issubset(harness):
        raise ValueError(f"{path}: run record has incomplete harness identity")


def agent_configuration(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("agent_configuration")
    if not isinstance(value, dict) or not value.get("profile"):
        raise ValueError("run record is missing agent_configuration.profile")
    return value


def comparison_profile(record: dict[str, Any]) -> str:
    model = record.get("model_configuration", {}).get("profile")
    if not isinstance(model, str) or not model:
        return ""
    agent = agent_configuration(record).get("profile")
    if not isinstance(agent, str) or not agent or agent == "vanilla":
        return model
    return f"{model} + {agent}"


def usage(record: dict[str, Any]) -> dict[str, int | float | None]:
    raw_usage = record.get("usage", {})
    values = list(raw_usage.values()) if isinstance(raw_usage, dict) else []
    agent = record.get("agent", {})
    provider_input = optional_int_sum(item.get("input_tokens") for item in values)
    provider_cached = optional_int_sum(
        item.get("input_tokens_cache_read") for item in values
    )
    provider_output = optional_int_sum(item.get("output_tokens") for item in values)
    return {
        "input_tokens": (
            provider_input
            if provider_input is not None
            else optional_int(agent.get("input_tokens"))
        ),
        "cache_write_tokens": optional_int_sum(
            item.get("input_tokens_cache_write") for item in values
        ),
        "cached_input_tokens": (
            provider_cached
            if provider_cached is not None
            else optional_int(agent.get("cached_input_tokens"))
        ),
        "reasoning_tokens": optional_int_sum(
            item.get("reasoning_tokens") for item in values
        ),
        "output_tokens": (
            provider_output
            if provider_output is not None
            else optional_int(agent.get("output_tokens"))
        ),
        "total_cost": optional_sum(item.get("total_cost") for item in values),
    }


def number(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def optional_int_sum(values) -> int | None:
    numbers = [
        int(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return sum(numbers) if numbers else None


def optional_int(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def optional_sum(values) -> float | None:
    numbers = [number(value) for value in values if value is not None]
    return sum(numbers) if numbers else None
