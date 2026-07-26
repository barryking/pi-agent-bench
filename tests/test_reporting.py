import csv
import json

from pi_agent_bench.reporting import (
    build_report,
    write_report,
    write_visualizer_exports,
)


def write_record(
    path,
    *,
    profile,
    success,
    score,
    wall,
    input_tokens,
    output_tokens,
    cost,
    phase="coding",
    dataset_version="1",
):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": f"run-{profile}",
                "case_id": "case-1",
                "dataset_version": dataset_version,
                "started_at": "2026-07-25T12:00:00Z",
                "phase": phase,
                "trial_number": 1,
                "model_configuration": {
                    "profile": profile,
                    "kind": "hosted" if profile != "dgx" else "local",
                    "configuration": {"temperature": 0},
                },
                "inspect_model": f"openai/{profile}",
                "harness": {
                    "framework_version": "0.2.0",
                    "inspect_version": "0.3.249",
                    "pi_version_actual": "0.82.1",
                },
                "success": success,
                "score": {
                    "value": score,
                    "components": {"tests_pass": success},
                },
                "wall_seconds": wall,
                "timing": {
                    "inspect_working_seconds": wall - 0.5,
                    "model_working_seconds": 4.0,
                    "tool_working_seconds": 1.0,
                    "observed_output_tokens_per_model_second": 5.0,
                },
                "usage": {
                    f"openai/{profile}": {
                        "input_tokens": input_tokens,
                        "input_tokens_cache_write": 3,
                        "input_tokens_cache_read": 2,
                        "reasoning_tokens": 4,
                        "output_tokens": output_tokens,
                        "total_cost": cost,
                    }
                },
                "agent": {
                    "wall_seconds": wall - 1,
                    "turns": 2,
                    "tool_calls": 3,
                    "failed_tool_calls": 0,
                    "retries": 1,
                    "compactions": 0,
                    "return_code": 0,
                },
                "verifier": {"return_code": 0},
                "artifacts": {"inspect_log": "logs/example.eval"},
            }
        ),
        encoding="utf-8",
    )


def test_builds_profile_comparison_report(tmp_path):
    write_record(
        tmp_path / "dgx-1.json",
        profile="dgx",
        success=True,
        score=1.0,
        wall=20,
        input_tokens=100,
        output_tokens=20,
        cost=None,
    )
    write_record(
        tmp_path / "cloud-1.json",
        profile="hosted-quality",
        success=True,
        score=1.0,
        wall=5,
        input_tokens=90,
        output_tokens=15,
        cost=0.25,
    )

    report = build_report(tmp_path)
    markdown, summary_json = write_report(report, tmp_path / "summary.md")

    cohort = report["cohorts"]["coding@1"]
    assert report["schema_version"] == 2
    assert cohort["profiles"]["dgx"]["success_rate"] == 1.0
    assert cohort["profiles"]["dgx"]["provider_reported_total_cost"] is None
    assert cohort["profiles"]["hosted-quality"]["provider_reported_total_cost"] == 0.25
    assert "hosted-quality" in markdown.read_text(encoding="utf-8")
    assert summary_json.exists()


def test_writes_visualizer_friendly_wide_and_long_exports(tmp_path):
    write_record(
        tmp_path / "dgx-1.json",
        profile="dgx",
        success=True,
        score=0.75,
        wall=20,
        input_tokens=100,
        output_tokens=20,
        cost=None,
    )

    runs_path, metrics_path = write_visualizer_exports(tmp_path)

    with runs_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    metrics = [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()
    ]

    assert rows[0]["profile"] == "dgx"
    assert rows[0]["record_schema_version"] == "1"
    assert rows[0]["started_at"] == "2026-07-25T12:00:00Z"
    assert rows[0]["pi_version"] == "0.82.1"
    assert rows[0]["reasoning_tokens"] == "4"
    assert rows[0]["model_working_seconds"] == "4.0"
    assert rows[0]["observed_output_tokens_per_model_second"] == "5.0"
    assert rows[0]["configuration_json"] == '{"temperature":0}'
    assert {row["metric"] for row in metrics} >= {
        "quality.score",
        "quality.component.tests_pass",
        "time.wall",
        "time.model_working",
        "time.tool_working",
        "speed.observed_output_tokens_per_model_second",
        "tokens.cache_write",
        "tokens.reasoning",
        "tokens.total",
        "agent.tool_calls",
    }
    assert {row["schema_version"] for row in metrics} == {1}
    assert {row["started_at"] for row in metrics} == {"2026-07-25T12:00:00Z"}


def test_report_never_aggregates_planning_and_coding(tmp_path):
    write_record(
        tmp_path / "planning.json",
        profile="dgx",
        success=False,
        score=0.0,
        wall=30,
        input_tokens=100,
        output_tokens=20,
        cost=None,
        phase="planning",
        dataset_version="plan-1",
    )
    write_record(
        tmp_path / "coding.json",
        profile="dgx",
        success=True,
        score=1.0,
        wall=20,
        input_tokens=100,
        output_tokens=20,
        cost=None,
        phase="coding",
        dataset_version="code-1",
    )

    report = build_report(tmp_path)

    assert report["cohorts"]["planning@plan-1"]["profiles"]["dgx"]["mean_quality_score"] == 0
    assert report["cohorts"]["coding@code-1"]["profiles"]["dgx"]["mean_quality_score"] == 1


def test_missing_usage_is_not_exported_as_zero(tmp_path):
    path = tmp_path / "run.json"
    write_record(
        path,
        profile="dgx",
        success=True,
        score=1.0,
        wall=20,
        input_tokens=100,
        output_tokens=20,
        cost=None,
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    record["usage"]["openai/dgx"].pop("reasoning_tokens")
    path.write_text(json.dumps(record), encoding="utf-8")

    runs_path, metrics_path = write_visualizer_exports(tmp_path)
    with runs_path.open(encoding="utf-8", newline="") as handle:
        [run] = list(csv.DictReader(handle))
    metrics = [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()
    ]

    assert run["reasoning_tokens"] == ""
    assert "tokens.reasoning" not in {row["metric"] for row in metrics}


def test_invalid_attempts_never_enter_reports_or_exports(tmp_path):
    write_record(
        tmp_path / "valid.json",
        profile="dgx",
        success=True,
        score=1.0,
        wall=20,
        input_tokens=100,
        output_tokens=20,
        cost=None,
    )
    invalid = {
        "schema_version": 1,
        "run_id": "run-invalid",
        "validity": {"valid": False, "reason": "cancelled"},
    }
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")

    report = build_report(tmp_path)
    runs_path, _ = write_visualizer_exports(tmp_path)

    assert report["records"] == 1
    with runs_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["run_id"] for row in rows] == ["run-dgx"]


def test_direct_pi_run_uses_profile_model_and_pi_tokens(tmp_path):
    path = tmp_path / "direct.json"
    write_record(
        path,
        profile="subscription",
        success=True,
        score=1.0,
        wall=20,
        input_tokens=100,
        output_tokens=20,
        cost=None,
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    record["model_configuration"]["model"] = "openai-codex/gpt-example"
    record["model_configuration"]["execution"] = {"mode": "pi-direct"}
    record["usage"] = {}
    record["agent"].update(
        {
            "input_tokens": 321,
            "cached_input_tokens": 123,
            "output_tokens": 45,
        }
    )
    path.write_text(json.dumps(record), encoding="utf-8")

    runs_path, _ = write_visualizer_exports(tmp_path)
    with runs_path.open(encoding="utf-8", newline="") as handle:
        [run] = list(csv.DictReader(handle))

    assert run["model"] == "openai-codex/gpt-example"
    assert run["input_tokens"] == "321"
    assert run["cached_input_tokens"] == "123"
    assert run["output_tokens"] == "45"
