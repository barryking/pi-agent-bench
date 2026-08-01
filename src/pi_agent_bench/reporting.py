"""Build agent-profile comparison summaries."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .report_outputs import write_report, write_visualizer_exports
from .result_records import (
    agent_configuration,
    comparison_profile,
    load_records,
    number,
    usage,
)
from .schema_versions import REPORT_SCHEMA_VERSION

__all__ = ["build_report", "write_report", "write_visualizer_exports"]


def build_report(results_dir: str | Path) -> dict[str, Any]:
    source = Path(results_dir)
    records = load_records(source)
    if not records:
        raise ValueError(f"{source}: no run record JSON files found")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["cohort"]["cohort_fingerprint"]].append(record)

    cohorts = {}
    for cohort_fingerprint, cohort_records in sorted(grouped.items()):
        profiles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in cohort_records:
            profile = comparison_profile(record)
            if not profile:
                raise ValueError("run record is missing agent_profile.profile")
            profiles[profile].append(record)
        for profile, profile_records in profiles.items():
            fingerprints = {
                agent_configuration(record).get("configuration_fingerprint")
                for record in profile_records
            }
            if len(fingerprints) > 1:
                raise ValueError(
                    f"agent profile {profile!r} has several composed configurations "
                    f"in cohort {cohort_fingerprint}"
                )
        coverage = {
            profile: _coverage_signature(profile_records)
            for profile, profile_records in profiles.items()
        }
        expected_coverage = next(iter(coverage.values()), ())
        comparable_profiles = sorted(
            profile for profile, signature in coverage.items() if signature == expected_coverage
        )
        first = cohort_records[0]
        cohorts[cohort_fingerprint] = {
            "cohort_fingerprint": cohort_fingerprint,
            "dataset_version": first["dataset_version"],
            "run_names": sorted({record["run_name"] for record in cohort_records}),
            "benchmark_ids": sorted(
                {
                    str(record.get("benchmark_id") or record["run_id"])
                    for record in cohort_records
                }
            ),
            "cache_state": first["cache_state"],
            "records": len(cohort_records),
            "profiles_comparable": len(comparable_profiles) == len(profiles),
            "comparison_warning": (
                None
                if len(comparable_profiles) == len(profiles)
                else "Profiles have different case or trial coverage and cannot share a ranking."
            ),
            "profiles": {
                profile: _profile_summary(profile_records)
                for profile, profile_records in sorted(profiles.items())
            },
        }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "records": len(records),
        "cohorts": cohorts,
    }


def _coverage_signature(records: list[dict[str, Any]]) -> tuple[tuple[str, int], ...]:
    counts = Counter(str(record["case_id"]) for record in records)
    return tuple(sorted(counts.items()))


def _profile_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [record for record in records if record.get("success") is True]
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_case[str(record["case_id"])].append(record)
    case_quality = [
        statistics.fmean(number(record.get("score", {}).get("value")) for record in values)
        for values in by_case.values()
    ]
    case_success = [
        statistics.fmean(
            1.0 if record.get("success") is True else 0.0 for record in values
        )
        for values in by_case.values()
    ]
    wall = [number(record.get("wall_seconds")) for record in records]
    successful_wall = [number(record.get("wall_seconds")) for record in successes]
    usage_values = [usage(record) for record in records]
    successful_usage = [usage(record) for record in successes]
    successful_total_tokens = [
        item["input_tokens"] + item["output_tokens"]
        for item in successful_usage
        if isinstance(item["input_tokens"], (int, float))
        and isinstance(item["output_tokens"], (int, float))
    ]
    costs = [
        float(item["total_cost"])
        for item in usage_values
        if isinstance(item["total_cost"], (int, float))
    ]
    total_cost = sum(costs)
    coverage_states = [str(item["cost_coverage"]) for item in usage_values]
    identity = agent_configuration(records[0])
    configured_resources = [
        {
            "name": resource.get("profile"),
            "kind": resource.get("kind"),
            "model": resource.get("model"),
            "execution": resource.get("execution", {}).get("mode"),
        }
        for resource in identity["model_resources"]
    ]
    observed_models = _observed_models(records)
    failed_cases = sorted(
        {
            str(record["case_id"])
            for record in records
            if record.get("success") is not True
        }
    )
    return {
        "agent_profile": identity["profile"],
        "agent_profile_fingerprint": identity["configuration_fingerprint"],
        "pi_profile": identity["pi_profile"].get("profile"),
        "configured_model_resources": configured_resources,
        "default_model_resource": identity["default_model_resource"],
        "observed_models": observed_models,
        "trials": len(records),
        "cases": len(by_case),
        "successes": len(successes),
        "success_rate": statistics.fmean(case_success),
        "mean_quality_score": statistics.fmean(case_quality),
        "median_wall_seconds": statistics.median(wall),
        "median_successful_wall_seconds": (
            statistics.median(successful_wall) if successful_wall else None
        ),
        "p95_successful_wall_seconds": _percentile(successful_wall, 0.95),
        "input_tokens": _sum_complete(item["input_tokens"] for item in usage_values),
        "cached_input_tokens": _sum_complete(
            item["cached_input_tokens"] for item in usage_values
        ),
        "reasoning_tokens": _sum_complete(
            item["reasoning_tokens"] for item in usage_values
        ),
        "output_tokens": _sum_complete(item["output_tokens"] for item in usage_values),
        "median_tokens_per_success": (
            statistics.median(successful_total_tokens)
            if successful_total_tokens
            else None
        ),
        "provider_reported_total_cost": total_cost,
        "cost_coverage": _combined_cost_coverage(coverage_states),
        "cost_coverage_runs": dict(sorted(Counter(coverage_states).items())),
        "provider_reported_cost_per_success": (
            total_cost / len(successes) if successes else None
        ),
        "failed_cases": failed_cases,
    }


def _observed_models(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    for record in records:
        for item in record.get("usage", {}).get("observed_models", []):
            if not isinstance(item, dict):
                continue
            key = (item.get("provider"), item.get("model"), item.get("execution"))
            observed[key] = {
                "provider": key[0],
                "model": key[1],
                "execution": key[2],
            }
    return list(observed.values())


def _combined_cost_coverage(states: list[str]) -> str:
    if states and all(state == "complete" for state in states):
        return "complete"
    if states and all(state == "unavailable" for state in states):
        return "unavailable"
    return "partial"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _sum_complete(values) -> int | float | None:
    items = list(values)
    if not items or any(value is None for value in items):
        return None
    return sum(items)
