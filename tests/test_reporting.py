import csv
import json

from pi_agent_bench.reporting import (
    build_report,
    write_report,
    write_visualizer_exports,
)


def identity(profile):
    return {
        "profile": profile,
        "description": profile,
        "pi_profile": {
            "profile": "vanilla",
            "configuration": {"tools": ["read"]},
            "configuration_fingerprint": "pi-one",
        },
        "model_resources": [
            {
                "profile": f"{profile}-model",
                "kind": "hosted",
                "model": f"openai/{profile}",
                "execution": {"mode": "inspect-bridge"},
                "configuration": {"revision": "one"},
                "configuration_fingerprint": f"model-{profile}",
            }
        ],
        "default_model_resource": f"{profile}-model",
        "configuration_fingerprint": f"agent-{profile}",
    }


def write_record(
    root,
    profile,
    case,
    trial,
    quality,
    wall,
    *,
    cost=0.1,
    cost_coverage="complete",
    cohort="cohort-a",
):
    record = {
        "schema_version": 5,
        "run_id": f"{profile}-{case}-{trial}",
        "case_id": case,
        "dataset_version": "dataset-1",
        "trial_number": trial,
        "synthetic": False,
        "run_name": "comparison",
        "cache_state": "warm",
        "agent_profile": identity(profile),
        "inspect_model": "mockllm/model",
        "cohort": {"cohort_fingerprint": cohort},
        "harness": {
            "framework_version": "1",
            "inspect_version": "1",
            "pi_version_actual": "1",
            "harness_source_fingerprint": "harness",
            "sandbox_image_id": "image",
            "sandbox_source_fingerprint": "sandbox",
        },
        "started_at": "2026-01-01T00:00:00Z",
        "wall_seconds": wall,
        "timing": {},
        "validity": {"valid": True},
        "success": quality >= 0.75,
        "score": {
            "value": quality,
            "components": {},
            "method": "deterministic",
            "success_threshold": 0.75,
        },
        "usage": {
            "bridged": {},
            "direct": {},
            "total": {
                "input_tokens": 100,
                "cached_input_tokens": 10,
                "reasoning_tokens": 5,
                "output_tokens": 20,
                "model_seconds": 2,
                "reported_cost": cost,
            },
            "cost_coverage": cost_coverage,
            "observed_models": [
                {
                    "provider": "openai",
                    "model": f"openai/{profile}",
                    "execution": "inspect-bridge",
                }
            ],
        },
        "agent": {"turns": 2},
        "verifier": {},
        "artifacts": {"inspect_log": "/tmp/example.eval"},
    }
    path = root / f"{profile}-{case}-{trial}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_report_aggregates_by_agent_profile_with_required_chart_statistics(tmp_path):
    for trial, quality, wall in [(1, 1.0, 10), (2, 0.0, 30)]:
        write_record(tmp_path, "agent-a", "case-1", trial, quality, wall)
    for trial, quality, wall in [(1, 0.5, 20), (2, 0.5, 40)]:
        write_record(tmp_path, "agent-a", "case-2", trial, quality, wall)

    report = build_report(tmp_path)
    summary = report["cohorts"]["cohort-a"]["profiles"]["agent-a"]

    assert summary["mean_quality_score"] == 0.5
    assert summary["median_wall_seconds"] == 25
    assert summary["provider_reported_total_cost"] == 0.4
    assert summary["cost_coverage"] == "complete"
    assert summary["configured_model_resources"][0]["name"] == "agent-a-model"


def test_profile_cost_coverage_combines_partial_and_unavailable(tmp_path):
    write_record(tmp_path, "agent-a", "case-1", 1, 1, 10, cost=0.2)
    write_record(
        tmp_path,
        "agent-a",
        "case-1",
        2,
        1,
        10,
        cost=0,
        cost_coverage="unavailable",
    )
    summary = build_report(tmp_path)["cohorts"]["cohort-a"]["profiles"]["agent-a"]
    assert summary["provider_reported_total_cost"] == 0.2
    assert summary["cost_coverage"] == "partial"


def test_profile_does_not_present_unavailable_cost_as_zero(tmp_path):
    write_record(
        tmp_path,
        "agent-a",
        "case-1",
        1,
        1,
        10,
        cost=0,
        cost_coverage="unavailable",
    )

    summary = build_report(tmp_path)["cohorts"]["cohort-a"]["profiles"]["agent-a"]

    assert summary["provider_reported_total_cost"] is None
    assert summary["provider_reported_cost_per_success"] is None
    assert summary["cost_coverage"] == "unavailable"


def test_report_marks_profiles_with_different_case_coverage_non_comparable(tmp_path):
    write_record(tmp_path, "agent-a", "case-1", 1, 1, 10)
    write_record(tmp_path, "agent-b", "case-2", 1, 1, 10)
    cohort = build_report(tmp_path)["cohorts"]["cohort-a"]
    assert cohort["profiles_comparable"] is False
    assert "different case or trial coverage" in cohort["comparison_warning"]


def test_visualizer_exports_agent_and_cohort_dimensions(tmp_path):
    write_record(tmp_path, "agent-a", "case-1", 1, 1, 10, cost_coverage="partial")
    runs_path, metrics_path = write_visualizer_exports(tmp_path)
    [run] = list(csv.DictReader(runs_path.open()))
    metrics = [json.loads(line) for line in metrics_path.read_text().splitlines()]

    assert run["agent_profile"] == "agent-a"
    assert run["pi_profile"] == "vanilla"
    assert run["model_resources"] == "agent-a-model"
    assert run["cohort_fingerprint"] == "cohort-a"
    assert run["cost_coverage"] == "partial"
    assert {row["metric"] for row in metrics} >= {
        "quality.score",
        "time.wall",
        "cost.provider_reported",
    }
    assert all(row["cohort_fingerprint"] == "cohort-a" for row in metrics)


def test_markdown_names_complete_agent_profiles_and_cost_coverage(tmp_path):
    write_record(tmp_path, "agent-a", "case-1", 1, 1, 10)
    report = build_report(tmp_path)
    markdown, summary = write_report(report, tmp_path / "summary.md")
    text = markdown.read_text()
    assert "Agent profile" in text
    assert "agent-a" in text
    assert "Coverage" in text
    assert summary.is_file()
