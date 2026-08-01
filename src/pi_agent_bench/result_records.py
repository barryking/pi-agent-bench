"""Read and normalise compact benchmark result records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema_versions import (
    RUN_RECORD_SCHEMA_VERSION,
    SUPPORTED_RUN_RECORD_SCHEMA_VERSIONS,
)


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
    schema_version = record.get("schema_version")
    if schema_version not in SUPPORTED_RUN_RECORD_SCHEMA_VERSIONS:
        supported = ", ".join(
            str(value) for value in sorted(SUPPORTED_RUN_RECORD_SCHEMA_VERSIONS)
        )
        raise ValueError(f"{path}: supported run record schema versions are {supported}")
    for field in ("run_id", "case_id", "dataset_version", "run_name"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError(f"{path}: run record is missing {field}")
    if schema_version == RUN_RECORD_SCHEMA_VERSION and (
        not isinstance(record.get("benchmark_id"), str) or not record["benchmark_id"]
    ):
        raise ValueError(f"{path}: run record is missing benchmark_id")
    if record.get("cache_state") not in {"unspecified", "cold", "warm"}:
        raise ValueError(f"{path}: cache_state must be unspecified, cold, or warm")
    agent = agent_configuration(record)
    required_agent = {
        "profile",
        "pi_profile",
        "model_resources",
        "default_model_resource",
        "configuration_fingerprint",
    }
    if not required_agent.issubset(agent):
        raise ValueError(f"{path}: run record has incomplete agent profile identity")
    cohort = record.get("cohort")
    if not isinstance(cohort, dict) or not cohort.get("cohort_fingerprint"):
        raise ValueError(f"{path}: run record has incomplete cohort identity")
    if schema_version == RUN_RECORD_SCHEMA_VERSION and cohort.get(
        "cohort_schema_version"
    ) != 2:
        raise ValueError(f"{path}: run record needs cohort_schema_version 2")
    harness = record.get("harness")
    required_harness = {
        "sandbox_image_id",
        "sandbox_source_fingerprint",
    }
    if not isinstance(harness, dict) or not required_harness.issubset(harness):
        raise ValueError(f"{path}: run record has incomplete harness identity")
    if schema_version == RUN_RECORD_SCHEMA_VERSION and not {
        "execution_protocol_fingerprint",
        "sandbox_runtime_fingerprint",
    }.issubset(harness):
        raise ValueError(f"{path}: run record has incomplete execution identity")
    usage_record = record.get("usage")
    if (
        not isinstance(usage_record, dict)
        or not isinstance(usage_record.get("total"), dict)
        or usage_record.get("cost_coverage") not in {"complete", "partial", "unavailable"}
    ):
        raise ValueError(f"{path}: run record has incomplete usage accounting")


def agent_configuration(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("agent_profile")
    if not isinstance(value, dict) or not value.get("profile"):
        raise ValueError("run record is missing agent_profile.profile")
    return value


def comparison_profile(record: dict[str, Any]) -> str:
    value = agent_configuration(record).get("profile")
    return value if isinstance(value, str) else ""


def usage(record: dict[str, Any]) -> dict[str, int | float | str | None]:
    raw = record.get("usage", {})
    total = raw.get("total", {}) if isinstance(raw, dict) else {}
    return {
        "input_tokens": optional_number(total.get("input_tokens")),
        "cached_input_tokens": optional_number(total.get("cached_input_tokens")),
        "reasoning_tokens": optional_number(total.get("reasoning_tokens")),
        "output_tokens": optional_number(total.get("output_tokens")),
        "model_seconds": optional_number(total.get("model_seconds")),
        "total_cost": optional_number(total.get("reported_cost")),
        "cost_coverage": raw.get("cost_coverage"),
    }


def number(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def optional_number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
