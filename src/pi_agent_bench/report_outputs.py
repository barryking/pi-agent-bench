"""Write agent-profile reports and visualizer data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .result_records import agent_configuration, comparison_profile, load_records, usage
from .schema_versions import METRIC_EXPORT_SCHEMA_VERSION

RUN_COLUMNS = [
    "record_schema_version",
    "synthetic",
    "run_id",
    "benchmark_id",
    "case_id",
    "dataset_version",
    "started_at",
    "run_name",
    "cache_state",
    "trial_number",
    "agent_profile",
    "pi_profile",
    "model_resources",
    "default_model_resource",
    "agent_profile_fingerprint",
    "cohort_fingerprint",
    "scoring_method",
    "success_threshold",
    "framework_version",
    "inspect_version",
    "pi_version",
    "sandbox_image",
    "sandbox_image_id",
    "sandbox_source_fingerprint",
    "sandbox_runtime_fingerprint",
    "execution_protocol_fingerprint",
    "harness_source_fingerprint",
    "repository_commit",
    "repository_branch",
    "repository_dirty",
    "success",
    "quality_score",
    "wall_seconds",
    "inspect_working_seconds",
    "model_working_seconds",
    "tool_working_seconds",
    "observed_output_tokens_per_model_second",
    "input_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "output_tokens",
    "provider_reported_cost",
    "cost_coverage",
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
    "agent_profile_json",
    "observed_models_json",
]


def write_visualizer_exports(
    results_dir: str | Path,
    output_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    source = Path(results_dir)
    destination = Path(output_dir) if output_dir else source
    destination.mkdir(parents=True, exist_ok=True)
    records = load_records(source)
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


def _flat_run(record: dict[str, Any]) -> dict[str, Any]:
    profile = agent_configuration(record)
    harness = record.get("harness", {})
    cohort = record.get("cohort", {})
    agent = record.get("agent", {})
    usage_values = usage(record)
    artifacts = record.get("artifacts", {})
    timing = record.get("timing", {})
    resources = profile.get("model_resources", [])
    return {
        "record_schema_version": record.get("schema_version"),
        "synthetic": record.get("synthetic", False),
        "run_id": record.get("run_id"),
        "benchmark_id": record.get("benchmark_id") or record.get("run_id"),
        "case_id": record.get("case_id"),
        "dataset_version": record.get("dataset_version"),
        "started_at": record.get("started_at"),
        "run_name": record["run_name"],
        "cache_state": record["cache_state"],
        "trial_number": record.get("trial_number"),
        "agent_profile": comparison_profile(record),
        "pi_profile": profile.get("pi_profile", {}).get("profile"),
        "model_resources": ",".join(
            str(resource.get("profile")) for resource in resources
        ),
        "default_model_resource": profile.get("default_model_resource"),
        "agent_profile_fingerprint": profile.get("configuration_fingerprint"),
        "cohort_fingerprint": cohort.get("cohort_fingerprint"),
        "scoring_method": record.get("score", {}).get("method"),
        "success_threshold": record.get("score", {}).get("success_threshold"),
        "framework_version": harness.get("framework_version"),
        "inspect_version": harness.get("inspect_version"),
        "pi_version": harness.get("pi_version_actual"),
        "sandbox_image": harness.get("sandbox_image"),
        "sandbox_image_id": harness.get("sandbox_image_id"),
        "sandbox_source_fingerprint": harness.get("sandbox_source_fingerprint"),
        "sandbox_runtime_fingerprint": harness.get(
            "sandbox_runtime_fingerprint",
            harness.get("sandbox_source_fingerprint"),
        ),
        "execution_protocol_fingerprint": harness.get(
            "execution_protocol_fingerprint",
            harness.get("harness_source_fingerprint"),
        ),
        "harness_source_fingerprint": harness.get("harness_source_fingerprint"),
        "repository_commit": harness.get("repository_commit"),
        "repository_branch": harness.get("repository_branch"),
        "repository_dirty": harness.get("repository_dirty"),
        "success": record.get("success"),
        "quality_score": record.get("score", {}).get("value"),
        "wall_seconds": record.get("wall_seconds"),
        "inspect_working_seconds": timing.get("inspect_working_seconds"),
        "model_working_seconds": timing.get("model_working_seconds"),
        "tool_working_seconds": timing.get("tool_working_seconds"),
        "observed_output_tokens_per_model_second": timing.get(
            "observed_output_tokens_per_model_second"
        ),
        "input_tokens": usage_values["input_tokens"],
        "cached_input_tokens": usage_values["cached_input_tokens"],
        "reasoning_tokens": usage_values["reasoning_tokens"],
        "output_tokens": usage_values["output_tokens"],
        "provider_reported_cost": usage_values["total_cost"],
        "cost_coverage": usage_values["cost_coverage"],
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
        "agent_profile_json": json.dumps(profile, sort_keys=True, separators=(",", ":")),
        "observed_models_json": json.dumps(
            record.get("usage", {}).get("observed_models", []),
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


def _metric_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    flat = _flat_run(record)
    dimensions = {
        "schema_version": METRIC_EXPORT_SCHEMA_VERSION,
        "synthetic": flat["synthetic"],
        "run_id": flat["run_id"],
        "benchmark_id": flat["benchmark_id"],
        "case_id": flat["case_id"],
        "dataset_version": flat["dataset_version"],
        "started_at": flat["started_at"],
        "run_name": flat["run_name"],
        "cache_state": flat["cache_state"],
        "trial_number": flat["trial_number"],
        "profile": flat["agent_profile"],
        "agent_profile": flat["agent_profile"],
        "pi_profile": flat["pi_profile"],
        "model_resources": flat["model_resources"],
        "default_model_resource": flat["default_model_resource"],
        "agent_profile_fingerprint": flat["agent_profile_fingerprint"],
        "cohort_fingerprint": flat["cohort_fingerprint"],
        "cost_coverage": flat["cost_coverage"],
        "scoring_method": flat["scoring_method"],
        "success_threshold": flat["success_threshold"],
        "framework_version": flat["framework_version"],
        "inspect_version": flat["inspect_version"],
        "pi_version": flat["pi_version"],
        "sandbox_image": flat["sandbox_image"],
        "sandbox_image_id": flat["sandbox_image_id"],
        "sandbox_source_fingerprint": flat["sandbox_source_fingerprint"],
        "sandbox_runtime_fingerprint": flat["sandbox_runtime_fingerprint"],
        "execution_protocol_fingerprint": flat["execution_protocol_fingerprint"],
        "harness_source_fingerprint": flat["harness_source_fingerprint"],
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
        ("cost.provider_reported", flat["provider_reported_cost"], "cost"),
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
    if rows:
        # Large profile/evidence objects are sample dimensions, not metric
        # dimensions. Emit them once per sample rather than on every metric row.
        rows[0]["agent_profile_json"] = flat["agent_profile_json"]
        rows[0]["observed_models_json"] = flat["observed_models_json"]
    components = record.get("score", {}).get("components", {})
    if isinstance(components, dict):
        for name, value in sorted(components.items()):
            if isinstance(value, (bool, int, float)):
                rows.append(
                    {
                        **dimensions,
                        "metric": f"quality.component.{name}",
                        "value": int(value) if isinstance(value, bool) else value,
                        "unit": "ratio",
                    }
                )
    return rows


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Pi Agent Bench comparison",
        "",
        "Complete agent profiles are judged by protected outcome verification.",
        "",
    ]
    for cohort in report["cohorts"].values():
        run_names = ", ".join(cohort["run_names"])
        lines.extend(
            [
                f"## Dataset {cohort['dataset_version']} — runs {run_names}",
                "",
            ]
        )
        if cohort["comparison_warning"]:
            lines.extend([f"> {cohort['comparison_warning']}", ""])
        lines.extend(
            [
                (
                    "| Agent profile | Pi profile | Model resources | Trials | Success | "
                    "Mean quality | Median wall seconds | Reported run cost | Coverage |"
                ),
                "|---|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for profile, values in cohort["profiles"].items():
            resources = ", ".join(
                resource["name"] for resource in values["configured_model_resources"]
            )
            lines.append(
                "| {profile} | {pi} | {resources} | {runs} | {success:.1%} | "
                "{quality:.3f} | {wall} | {cost} | {coverage} |".format(
                    profile=profile,
                    pi=values["pi_profile"],
                    resources=resources,
                    runs=values["trials"],
                    success=values["success_rate"],
                    quality=values["mean_quality_score"],
                    wall=_format_number(values["median_wall_seconds"]),
                    cost=_format_number(values["provider_reported_total_cost"], 6),
                    coverage=values["cost_coverage"],
                )
            )
        lines.append("")
    lines.extend(
        [
            "Reported cost covers inference calls only. Partial values are lower bounds; "
            "unavailable cloud cost is never treated as free.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_number(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"
