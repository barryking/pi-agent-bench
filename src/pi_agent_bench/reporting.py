"""Build Pi Agent Bench comparison reports."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

RUN_COLUMNS = [
    "record_schema_version",
    "synthetic",
    "run_id",
    "case_id",
    "dataset_version",
    "started_at",
    "campaign",
    "cache_state",
    "phase",
    "trial_number",
    "profile",
    "profile_kind",
    "model",
    "provider",
    "configuration_fingerprint",
    "scoring_method",
    "success_threshold",
    "grader_model",
    "framework_version",
    "inspect_version",
    "pi_version",
    "sandbox_image",
    "repository_commit",
    "repository_branch",
    "repository_dirty",
    "benchmark_fingerprint",
    "success",
    "quality_score",
    "wall_seconds",
    "inspect_working_seconds",
    "model_working_seconds",
    "tool_working_seconds",
    "observed_output_tokens_per_model_second",
    "input_tokens",
    "cache_write_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "output_tokens",
    "provider_reported_cost",
    "cost_currency",
    "pi_wall_seconds",
    "turns",
    "tool_calls",
    "failed_tool_calls",
    "retries",
    "compactions",
    "agent_return_code",
    "verifier_return_code",
    "inspect_log",
    "final_diff",
    "configuration_json",
]


def build_report(results_dir: str | Path) -> dict[str, Any]:
    source = Path(results_dir)
    records = _load_records(source)
    if not records:
        raise ValueError(f"{source}: no run record JSON files found")

    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        phase = record.get("phase")
        dataset_version = record.get("dataset_version")
        if not isinstance(phase, str) or not phase:
            raise ValueError("run record is missing phase")
        if not isinstance(dataset_version, str) or not dataset_version:
            raise ValueError("run record is missing dataset_version")
        campaign = str(record.get("campaign", "legacy"))
        cache_state = str(record.get("cache_state", "unspecified"))
        benchmark_fingerprint = str(
            record.get("harness", {}).get("benchmark_fingerprint")
            or "legacy-unfingerprinted"
        )
        grouped[
            (
                phase,
                dataset_version,
                campaign,
                cache_state,
                benchmark_fingerprint,
            )
        ].append(record)

    cohorts = {}
    for cohort_identity, cohort_records in sorted(grouped.items()):
        phase, dataset_version, campaign, cache_state, benchmark_fingerprint = (
            cohort_identity
        )
        profiles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in cohort_records:
            profile = record.get("model_configuration", {}).get("profile")
            if not isinstance(profile, str) or not profile:
                raise ValueError("run record is missing model_configuration.profile")
            profiles[profile].append(record)
        for profile, profile_records in profiles.items():
            fingerprints = {
                record.get("model_configuration", {}).get("configuration_fingerprint")
                for record in profile_records
                if record.get("model_configuration", {}).get("configuration_fingerprint")
            }
            if len(fingerprints) > 1:
                raise ValueError(
                    f"profile {profile!r} has several configurations in campaign "
                    f"{campaign!r}; use a new profile name or campaign"
                )
        key = (
            f"{phase}@{dataset_version}::{campaign}::{cache_state}::"
            f"{benchmark_fingerprint}"
        )
        cohorts[key] = {
            "phase": phase,
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
        "schema_version": 3,
        "records": len(records),
        "cohorts": cohorts,
    }


def write_visualizer_exports(
    results_dir: str | Path,
    output_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write a wide run table and long-form metric facts."""
    source = Path(results_dir)
    destination = Path(output_dir) if output_dir else source
    destination.mkdir(parents=True, exist_ok=True)
    records = _load_records(source)
    if not records:
        raise ValueError(f"{source}: no run record JSON files found")

    runs_path = destination / "runs.csv"
    with runs_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUN_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(_flat_run(record))

    metrics_path = destination / "metrics.jsonl"
    with metrics_path.open("w", encoding="utf-8") as handle:
        for record in records:
            for metric in _metric_rows(record):
                handle.write(json.dumps(metric, sort_keys=True) + "\n")
    return runs_path, metrics_path


def write_report(
    report: dict[str, Any],
    output_markdown: str | Path,
    output_json: str | Path | None = None,
) -> tuple[Path, Path]:
    markdown_path = Path(output_markdown)
    json_path = Path(output_json) if output_json else markdown_path.with_suffix(".json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return markdown_path, json_path


def _profile_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [record for record in records if record.get("success") is True]
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_case[str(record.get("case_id"))].append(record)
    case_quality = [
        statistics.fmean(_number(record.get("score", {}).get("value")) for record in values)
        for values in by_case.values()
    ]
    case_success = [
        statistics.fmean(1.0 if record.get("success") is True else 0.0 for record in values)
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
    total_cost_values = [item["total_cost"] for item in usage if item["total_cost"] is not None]
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
        "cache_write_tokens": _sum_available(item["cache_write_tokens"] for item in usage),
        "cached_input_tokens": _sum_available(
            item["cached_input_tokens"] for item in usage
        ),
        "reasoning_tokens": _sum_available(item["reasoning_tokens"] for item in usage),
        "output_tokens": _sum_available(item["output_tokens"] for item in usage),
        "median_tokens_per_success": (
            statistics.median(successful_total_tokens)
            if successful_total_tokens
            else None
        ),
        "provider_reported_total_cost": total_cost,
        "cost_coverage_runs": len(total_cost_values),
        "provider_reported_cost_per_success": (
            total_cost / len(successes) if total_cost is not None and successes else None
        ),
    }


def _load_records(source: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(source.glob("*.json"))
        if path.name != "summary.json"
    ]
    return [
        record
        for record in records
        if record.get("validity", {}).get("valid") is not False
    ]


def _flat_run(record: dict[str, Any]) -> dict[str, Any]:
    profile = record.get("model_configuration", {})
    harness = record.get("harness", {})
    agent = record.get("agent", {})
    usage = _usage(record)
    artifacts = record.get("artifacts", {})
    timing = record.get("timing", {})
    return {
        "record_schema_version": record.get("schema_version"),
        "synthetic": record.get("synthetic", False),
        "run_id": record.get("run_id"),
        "case_id": record.get("case_id"),
        "dataset_version": record.get("dataset_version"),
        "started_at": record.get("started_at"),
        "campaign": record.get("campaign", "legacy"),
        "cache_state": record.get("cache_state", "unspecified"),
        "phase": record.get("phase"),
        "trial_number": record.get("trial_number"),
        "profile": profile.get("profile"),
        "profile_kind": profile.get("kind"),
        "model": profile.get("model") or record.get("inspect_model"),
        "provider": profile.get("configuration", {}).get(
            "provider",
            profile.get("configuration", {}).get(
                "runtime",
                profile.get("configuration", {}).get("hardware"),
            ),
        ),
        "configuration_fingerprint": profile.get("configuration_fingerprint"),
        "scoring_method": record.get("score", {}).get("method"),
        "success_threshold": record.get("score", {}).get("success_threshold"),
        "grader_model": record.get("score", {}).get("grader_model"),
        "framework_version": harness.get("framework_version"),
        "inspect_version": harness.get("inspect_version"),
        "pi_version": harness.get("pi_version_actual"),
        "sandbox_image": harness.get("sandbox_image"),
        "repository_commit": harness.get("repository_commit"),
        "repository_branch": harness.get("repository_branch"),
        "repository_dirty": harness.get("repository_dirty"),
        "benchmark_fingerprint": harness.get("benchmark_fingerprint"),
        "success": record.get("success"),
        "quality_score": record.get("score", {}).get("value"),
        "wall_seconds": record.get("wall_seconds"),
        "inspect_working_seconds": timing.get("inspect_working_seconds"),
        "model_working_seconds": timing.get("model_working_seconds"),
        "tool_working_seconds": timing.get("tool_working_seconds"),
        "observed_output_tokens_per_model_second": timing.get(
            "observed_output_tokens_per_model_second"
        ),
        "input_tokens": usage["input_tokens"],
        "cache_write_tokens": usage["cache_write_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"],
        "output_tokens": usage["output_tokens"],
        "provider_reported_cost": usage["total_cost"],
        "cost_currency": profile.get("configuration", {}).get("cost_currency"),
        "pi_wall_seconds": agent.get("wall_seconds"),
        "turns": agent.get("turns"),
        "tool_calls": agent.get("tool_calls"),
        "failed_tool_calls": agent.get("failed_tool_calls"),
        "retries": agent.get("retries"),
        "compactions": agent.get("compactions"),
        "agent_return_code": agent.get("return_code"),
        "verifier_return_code": record.get("verifier", {}).get("return_code"),
        "inspect_log": artifacts.get("inspect_log"),
        "final_diff": artifacts.get("final_diff"),
        "configuration_json": json.dumps(
            profile.get("configuration", {}),
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


def _metric_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    flat = _flat_run(record)
    dimensions = {
        "schema_version": 1,
        "synthetic": flat["synthetic"],
        "run_id": flat["run_id"],
        "case_id": flat["case_id"],
        "dataset_version": flat["dataset_version"],
        "started_at": flat["started_at"],
        "campaign": flat["campaign"],
        "cache_state": flat["cache_state"],
        "phase": flat["phase"],
        "trial_number": flat["trial_number"],
        "profile": flat["profile"],
        "profile_kind": flat["profile_kind"],
        "model": flat["model"],
        "provider": flat["provider"],
        "configuration_fingerprint": flat["configuration_fingerprint"],
        "configuration_json": flat["configuration_json"],
        "scoring_method": flat["scoring_method"],
        "success_threshold": flat["success_threshold"],
        "grader_model": flat["grader_model"],
        "framework_version": flat["framework_version"],
        "inspect_version": flat["inspect_version"],
        "pi_version": flat["pi_version"],
        "sandbox_image": flat["sandbox_image"],
        "repository_commit": flat["repository_commit"],
        "repository_branch": flat["repository_branch"],
        "repository_dirty": flat["repository_dirty"],
        "benchmark_fingerprint": flat["benchmark_fingerprint"],
    }
    definitions = [
        ("quality.success", int(bool(flat["success"])), "ratio"),
        ("quality.score", flat["quality_score"], "ratio"),
        ("time.wall", flat["wall_seconds"], "seconds"),
        ("time.inspect_working", flat["inspect_working_seconds"], "seconds"),
        ("time.model_working", flat["model_working_seconds"], "seconds"),
        ("time.tool_working", flat["tool_working_seconds"], "seconds"),
        ("time.pi", flat["pi_wall_seconds"], "seconds"),
        (
            "speed.observed_output_tokens_per_model_second",
            flat["observed_output_tokens_per_model_second"],
            "tokens/second",
        ),
        ("tokens.input", flat["input_tokens"], "tokens"),
        ("tokens.cache_write", flat["cache_write_tokens"], "tokens"),
        ("tokens.cached_input", flat["cached_input_tokens"], "tokens"),
        ("tokens.reasoning", flat["reasoning_tokens"], "tokens"),
        ("tokens.output", flat["output_tokens"], "tokens"),
        (
            "tokens.total",
            (
                flat["input_tokens"] + flat["output_tokens"]
                if flat["input_tokens"] is not None
                and flat["output_tokens"] is not None
                else None
            ),
            "tokens",
        ),
        (
            "cost.provider_reported",
            flat["provider_reported_cost"],
            flat["cost_currency"] or "currency-unspecified",
        ),
        ("agent.turns", flat["turns"], "count"),
        ("agent.tool_calls", flat["tool_calls"], "count"),
        ("agent.failed_tool_calls", flat["failed_tool_calls"], "count"),
        ("agent.retries", flat["retries"], "count"),
        ("agent.compactions", flat["compactions"], "count"),
    ]
    rows = [
        {**dimensions, "metric": name, "value": value, "unit": unit}
        for name, value, unit in definitions
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    components = record.get("score", {}).get("components", {})
    if isinstance(components, dict):
        for name, value in sorted(components.items()):
            if isinstance(value, bool):
                rows.append(
                    {
                        **dimensions,
                        "metric": f"quality.component.{name}",
                        "value": int(value),
                        "unit": "ratio",
                    }
                )
            elif isinstance(value, (int, float)):
                rows.append(
                    {
                        **dimensions,
                        "metric": f"quality.component.{name}",
                        "value": value,
                        "unit": "ratio",
                    }
                )
    return rows


def _usage(record: dict[str, Any]) -> dict[str, int | float | None]:
    usage = record.get("usage", {})
    values = list(usage.values()) if isinstance(usage, dict) else []
    agent = record.get("agent", {})
    provider_input = _optional_int_sum(item.get("input_tokens") for item in values)
    provider_cached = _optional_int_sum(
        item.get("input_tokens_cache_read") for item in values
    )
    provider_output = _optional_int_sum(
        item.get("output_tokens") for item in values
    )
    return {
        "input_tokens": (
            provider_input
            if provider_input is not None
            else _optional_int(agent.get("input_tokens"))
        ),
        "cache_write_tokens": _optional_int_sum(
            item.get("input_tokens_cache_write") for item in values
        ),
        "cached_input_tokens": (
            provider_cached
            if provider_cached is not None
            else _optional_int(agent.get("cached_input_tokens"))
        ),
        "reasoning_tokens": _optional_int_sum(
            item.get("reasoning_tokens") for item in values
        ),
        "output_tokens": (
            provider_output
            if provider_output is not None
            else _optional_int(agent.get("output_tokens"))
        ),
        "total_cost": _optional_sum(item.get("total_cost") for item in values),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _number(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _optional_int_sum(values) -> int | None:
    numbers = [
        int(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return sum(numbers) if numbers else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def _sum_available(values) -> int | float | None:
    numbers = [value for value in values if value is not None]
    return sum(numbers) if numbers else None


def _optional_sum(values) -> float | None:
    numbers = [_number(value) for value in values if value is not None]
    return sum(numbers) if numbers else None


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Pi Agent Bench comparison",
        "",
        "Generated from compact run records on the Mac. Planning, coding and "
        "dataset versions are reported as separate cohorts.",
        "",
    ]
    for cohort in report["cohorts"].values():
        lines.extend(
            [
                (
                    f"## {cohort['phase']} — dataset {cohort['dataset_version']} — "
                    f"campaign {cohort['campaign']} — {cohort['cache_state']} cache"
                ),
                "",
                (
                    "| Profile | Model | Runs | Success | Mean quality | "
                    "Median successful seconds | p95 successful seconds | "
                    "Median tokens / success | Input / cached / output tokens | "
                    "Reported cost | Cost / success |"
                ),
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for profile, values in cohort["profiles"].items():
            lines.append(
                "| {profile} | {model} | {runs} | {success:.1%} | {quality:.3f} | "
                "{median} | {p95} | {tokens_per_success} | "
                "{input_tokens} / {cached_tokens} / {output_tokens} | {cost} | "
                "{cost_per_success} |".format(
                    profile=profile,
                    model=values["model"],
                    runs=values["runs"],
                    success=values["success_rate"],
                    quality=values["mean_quality_score"],
                    median=_format_number(values["median_successful_wall_seconds"]),
                    p95=_format_number(values["p95_successful_wall_seconds"]),
                    tokens_per_success=_format_count(
                        values["median_tokens_per_success"]
                    ),
                    input_tokens=_format_count(values["input_tokens"]),
                    cached_tokens=_format_count(values["cached_input_tokens"]),
                    output_tokens=_format_count(values["output_tokens"]),
                    cost=_format_number(values["provider_reported_total_cost"], 6),
                    cost_per_success=_format_number(
                        values["provider_reported_cost_per_success"], 6
                    ),
                )
            )
        lines.append("")
    lines.extend(
        [
            "",
            "Provider-reported cost is shown only where the provider supplied it. "
            "Local hardware, energy and operating costs require separate assumptions.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_number(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _format_count(value: int | float | None) -> str:
    return "n/a" if value is None else str(value)
