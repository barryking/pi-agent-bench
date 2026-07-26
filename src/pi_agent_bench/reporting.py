"""Build Pi Agent Bench comparison summaries."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .report_outputs import (
    _agent_configuration,
    _comparison_profile,
    _load_records,
    _number,
    _usage,
    write_report,
    write_visualizer_exports,
)

__all__ = ["build_report", "write_report", "write_visualizer_exports"]


def build_report(results_dir: str | Path) -> dict[str, Any]:
    source = Path(results_dir)
    records = _load_records(source)
    if not records:
        raise ValueError(f"{source}: no run record JSON files found")

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        dataset_version = record.get("dataset_version")
        if not isinstance(dataset_version, str) or not dataset_version:
            raise ValueError("run record is missing dataset_version")
        campaign = record["campaign"]
        cache_state = record["cache_state"]
        benchmark_fingerprint = record["harness"]["benchmark_fingerprint"]
        grouped[
            (
                dataset_version,
                campaign,
                cache_state,
                benchmark_fingerprint,
            )
        ].append(record)

    cohorts = {}
    for cohort_identity, cohort_records in sorted(grouped.items()):
        dataset_version, campaign, cache_state, benchmark_fingerprint = cohort_identity
        profiles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in cohort_records:
            profile = _comparison_profile(record)
            if not profile:
                raise ValueError("run record is missing model_configuration.profile")
            profiles[profile].append(record)
        for profile, profile_records in profiles.items():
            fingerprints = {
                (
                    record.get("model_configuration", {}).get(
                        "configuration_fingerprint"
                    ),
                    _agent_configuration(record).get("configuration_fingerprint"),
                )
                for record in profile_records
                if record.get("model_configuration", {}).get(
                    "configuration_fingerprint"
                )
            }
            if len(fingerprints) > 1:
                raise ValueError(
                    f"profile {profile!r} has several configurations in campaign "
                    f"{campaign!r}; use a new profile name or campaign"
                )
        key = f"{dataset_version}::{campaign}::{cache_state}::{benchmark_fingerprint}"
        cohorts[key] = {
            "dataset_version": dataset_version,
            "campaign": campaign,
            "cache_state": cache_state,
            "benchmark_fingerprint": benchmark_fingerprint,
            "records": len(cohort_records),
            "profiles": {
                profile: _profile_summary(profile_records)
                for profile, profile_records in sorted(profiles.items())
            },
        }
    return {
        "schema_version": 5,
        "records": len(records),
        "cohorts": cohorts,
    }


def _profile_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [record for record in records if record.get("success") is True]
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_case[str(record.get("case_id"))].append(record)
    case_quality = [
        statistics.fmean(
            _number(record.get("score", {}).get("value")) for record in values
        )
        for values in by_case.values()
    ]
    case_success = [
        statistics.fmean(
            1.0 if record.get("success") is True else 0.0 for record in values
        )
        for values in by_case.values()
    ]
    wall = [_number(record.get("wall_seconds")) for record in records]
    successful_wall = [_number(record.get("wall_seconds")) for record in successes]
    usage = [_usage(record) for record in records]
    successful_usage = [_usage(record) for record in successes]
    successful_total_tokens = [
        item["input_tokens"] + item["output_tokens"]
        for item in successful_usage
        if item["input_tokens"] is not None and item["output_tokens"] is not None
    ]
    total_cost_values = [
        item["total_cost"] for item in usage if item["total_cost"] is not None
    ]
    total_cost = sum(total_cost_values) if total_cost_values else None
    return {
        "model": next(
            (
                record.get("model_configuration", {}).get("model")
                or record.get("inspect_model")
                for record in records
                if record.get("model_configuration", {}).get("model")
                or record.get("inspect_model")
            ),
            None,
        ),
        "model_profile": records[0].get("model_configuration", {}).get("profile"),
        "agent_profile": _agent_configuration(records[0]).get("profile"),
        "runs": len(records),
        "cases": len(by_case),
        "successes": len(successes),
        "success_rate": statistics.fmean(case_success),
        "mean_quality_score": statistics.fmean(case_quality),
        "median_wall_seconds": statistics.median(wall),
        "median_successful_wall_seconds": (
            statistics.median(successful_wall) if successful_wall else None
        ),
        "p95_successful_wall_seconds": _percentile(successful_wall, 0.95),
        "input_tokens": _sum_available(item["input_tokens"] for item in usage),
        "cache_write_tokens": _sum_available(
            item["cache_write_tokens"] for item in usage
        ),
        "cached_input_tokens": _sum_available(
            item["cached_input_tokens"] for item in usage
        ),
        "reasoning_tokens": _sum_available(
            item["reasoning_tokens"] for item in usage
        ),
        "output_tokens": _sum_available(item["output_tokens"] for item in usage),
        "median_tokens_per_success": (
            statistics.median(successful_total_tokens)
            if successful_total_tokens
            else None
        ),
        "provider_reported_total_cost": total_cost,
        "cost_coverage_runs": len(total_cost_values),
        "provider_reported_cost_per_success": (
            total_cost / len(successes)
            if total_cost is not None and successes
            else None
        ),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _sum_available(values) -> int | float | None:
    numbers = [value for value in values if value is not None]
    return sum(numbers) if numbers else None
