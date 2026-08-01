import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pi_agent_bench.agent_profiles import AgentProfile
from pi_agent_bench.model_profiles import ModelProfile
from pi_agent_bench.pi_profiles import vanilla_pi_profile
from pi_agent_bench.reporting import write_visualizer_exports
from pi_agent_bench.result_records import validate_record
from pi_agent_bench.run_records import export_inspect_logs, write_run_records
from pi_agent_bench.versions import (
    FRAMEWORK_VERSION,
    INSPECT_VERSION,
    PI_VERSION,
    SANDBOX_IMAGE,
)

ROOT = Path(__file__).resolve().parents[1]
HARNESS_IDENTITY = {
    "framework_version": FRAMEWORK_VERSION,
    "pi_version_expected": PI_VERSION,
    "inspect_version": INSPECT_VERSION,
    "repository_commit": "test-commit",
    "repository_branch": "test-branch",
    "repository_dirty": False,
    "harness_source_fingerprint": "test-harness",
    "sandbox_image": SANDBOX_IMAGE,
    "sandbox_image_id": "sha256:test-image",
    "sandbox_repo_digests": [],
    "sandbox_source_fingerprint": "test-sandbox",
}
COHORT_IDENTITY = {
    "cohort_fingerprint": "test-cohort",
    "dataset_version": "test-1",
}
CURRENT_HARNESS_IDENTITY = {
    **HARNESS_IDENTITY,
    "execution_protocol_fingerprint": "test-execution",
    "sandbox_runtime_fingerprint": "test-runtime",
}
CURRENT_COHORT_IDENTITY = {
    "cohort_schema_version": 2,
    "cohort_fingerprint": "test-cohort-v2",
    "dataset_version": "test-1",
}


def agent_profile(*, kind="local"):
    resource = ModelProfile.from_dict(
        "resource",
        {
            "kind": kind,
            "model": "openai/resource",
            "execution": {
                "mode": "inspect-bridge",
                "model_args": {},
                "model_args_env": {},
                "generate_config": {},
            },
            "capabilities": {
                "context_tokens": 32768,
                "max_output_tokens": 8192,
                "reasoning": False,
                "input": ["text"],
            },
            "configuration": {"revision": "one"},
        },
    )
    return AgentProfile(
        name="test-agent",
        description="Test.",
        pi_profile=vanilla_pi_profile(),
        model_resources=(resource,),
        default_model_resource="resource",
    )


def hybrid_agent_profile():
    bridged = agent_profile(kind="hosted").model_resources[0]
    direct = ModelProfile.from_dict(
        "review",
        {
            "kind": "hosted",
            "model": "openai-codex/review",
            "execution": {
                "mode": "pi-direct",
                "provider": "openai-codex",
                "model": "review",
                "auth_file_env": "PI_AUTH_FILE",
            },
            "capabilities": {
                "context_tokens": 32768,
                "max_output_tokens": 8192,
                "reasoning": True,
                "input": ["text"],
            },
            "configuration": {"revision": "review"},
        },
    )
    return AgentProfile(
        name="hybrid-agent",
        description="Hybrid.",
        pi_profile=vanilla_pi_profile(),
        model_resources=(bridged, direct),
        default_model_resource="resource",
    )


def score(*, quality=1.0, metadata=None):
    return SimpleNamespace(
        value={"quality": quality, "success": float(quality >= 0.75)},
        explanation="checked",
        metadata={
            "success_threshold": 0.75,
            "required_components": [],
            "scoring_method": "deterministic",
            "pi_version": PI_VERSION,
            "pi": {"turns": 2},
            **(metadata or {}),
        },
    )


def log(*, model_usage=None, status="success", sample_error=None, score_value=None):
    sample = SimpleNamespace(
        id="case-1",
        epoch=1,
        error=sample_error,
        scores={"outcome": score_value or score()},
        metadata={},
        started_at="2026-01-01T00:00:00Z",
        total_time=12.0,
        working_time=10.0,
        model_usage=model_usage or {},
        events=[],
        turn_count=2,
    )
    return SimpleNamespace(
        status=status,
        error=None,
        location="test-fixtures/test.eval",
        eval=SimpleNamespace(run_id="run-1", task_version="test-1", model="mockllm/model"),
        samples=[sample],
    )


def test_pins_match_package_and_sandbox_contract():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert f'inspect-ai=={INSPECT_VERSION}' in pyproject
    assert f"pi-agent-bench-sandbox:{FRAMEWORK_VERSION}" == SANDBOX_IMAGE
    assert "ARG PI_VERSION" in dockerfile


def test_result_record_contains_composed_profile_cohort_and_path_usage(tmp_path):
    paths = write_run_records(
        [log(model_usage={"openai/resource": {
            "input_tokens": 10,
            "input_tokens_cache_read": 2,
            "output_tokens": 3,
            "reasoning_tokens": 1,
            "total_cost": None,
        }})],
        tmp_path,
        agent_profile(),
        run_name="test",
        harness_identity=HARNESS_IDENTITY,
        cohort_identity=COHORT_IDENTITY,
    )
    record = json.loads(paths[0].read_text(encoding="utf-8"))

    assert record["schema_version"] == 5
    assert record["agent_profile"]["profile"] == "test-agent"
    assert record["cohort"]["cohort_fingerprint"] == "test-cohort"
    assert record["harness"]["harness_source_fingerprint"] == "test-harness"
    assert record["usage"]["bridged"]["input_tokens"] == 10
    assert record["usage"]["direct"]["call_count"] == 0
    assert record["usage"]["total"]["input_tokens"] == 10
    assert record["usage"]["cost_coverage"] == "complete"


def test_current_record_schema_requires_campaign_and_cohort_v2(tmp_path):
    [path] = write_run_records(
        [log()],
        tmp_path,
        agent_profile(),
        benchmark_id="campaign-1",
        run_name="test",
        harness_identity=CURRENT_HARNESS_IDENTITY,
        cohort_identity=CURRENT_COHORT_IDENTITY,
    )
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["schema_version"] == 6
    assert record["benchmark_id"] == "campaign-1"
    validate_record(record, path)
    runs_path, _metrics_path = write_visualizer_exports(tmp_path)
    [run] = list(csv.DictReader(runs_path.open()))
    assert run["execution_protocol_fingerprint"] == "test-execution"
    assert run["harness_source_fingerprint"] == "test-harness"


def test_log_export_prunes_valid_records_absent_from_canonical_logs(
    tmp_path,
    monkeypatch,
):
    [stale] = write_run_records(
        [log()],
        tmp_path,
        agent_profile(),
        run_name="stale",
        harness_identity=HARNESS_IDENTITY,
        cohort_identity=COHORT_IDENTITY,
    )
    monkeypatch.setattr("inspect_ai.log.list_eval_logs", lambda _path: [])

    assert export_inspect_logs(tmp_path / "logs", tmp_path) == []
    assert not stale.exists()


def test_log_export_preserves_previous_record_when_source_log_is_skipped(
    tmp_path,
    monkeypatch,
):
    source = log()
    [record] = write_run_records(
        [source],
        tmp_path,
        agent_profile(),
        run_name="previous",
        harness_identity=HARNESS_IDENTITY,
        cohort_identity=COHORT_IDENTITY,
    )
    source.eval.metadata = {}
    monkeypatch.setattr(
        "inspect_ai.log.list_eval_logs",
        lambda _path: [SimpleNamespace(name=source.location)],
    )
    monkeypatch.setattr("inspect_ai.log.read_eval_log", lambda _name: source)

    with pytest.warns(UserWarning, match="without Pi Agent Bench metadata"):
        assert export_inspect_logs(tmp_path / "logs", tmp_path) == []

    assert record.exists()


def test_hosted_missing_cost_is_unavailable_not_zero(tmp_path):
    paths = write_run_records(
        [log(model_usage={"openai/resource": {
            "input_tokens": 10,
            "input_tokens_cache_read": 0,
            "output_tokens": 3,
            "reasoning_tokens": 0,
            "total_cost": None,
        }})],
        tmp_path,
        agent_profile(kind="hosted"),
        run_name="test",
        harness_identity=HARNESS_IDENTITY,
        cohort_identity=COHORT_IDENTITY,
    )
    usage = json.loads(paths[0].read_text(encoding="utf-8"))["usage"]
    assert usage["bridged"]["reported_cost"] is None
    assert usage["total"]["reported_cost"] is None
    assert usage["cost_coverage"] == "unavailable"


def test_partial_cost_keeps_only_the_reported_lower_bound(tmp_path):
    metadata = {
        "pi_direct_usage": {
            "call_count": 1,
            "input_tokens": 20,
            "cached_input_tokens": 2,
            "output_tokens": 4,
            "reasoning_tokens": 1,
            "model_seconds": 0.5,
            "reported_cost": 0,
        },
        "pi_direct_cost_reported_calls": 0,
        "pi_observed_models": [
            {"provider": "openai-codex", "model": "review", "call_count": 1}
        ],
        "pi_unattributed_assistant_calls": 0,
    }
    [path] = write_run_records(
        [
            log(
                model_usage={
                    "openai/resource": {
                        "input_tokens": 10,
                        "input_tokens_cache_read": 1,
                        "output_tokens": 3,
                        "reasoning_tokens": 0,
                        "total_cost": 0.02,
                    }
                },
                score_value=score(metadata=metadata),
            )
        ],
        tmp_path,
        hybrid_agent_profile(),
        run_name="test",
        harness_identity=HARNESS_IDENTITY,
        cohort_identity=COHORT_IDENTITY,
    )

    usage = json.loads(path.read_text(encoding="utf-8"))["usage"]
    assert usage["direct"]["reported_cost"] is None
    assert usage["total"]["reported_cost"] == pytest.approx(0.02)
    assert usage["cost_coverage"] == "partial"


def test_hybrid_usage_merges_sources_without_counting_bridge_pi_events(tmp_path):
    metadata = {
        "pi_direct_usage": {
            "call_count": 1,
            "input_tokens": 20,
            "cached_input_tokens": 2,
            "output_tokens": 4,
            "reasoning_tokens": 1,
            "model_seconds": 0.5,
            "reported_cost": 0.03,
        },
        "pi_direct_cost_reported_calls": 1,
        "pi_observed_models": [
            {
                "provider": "openai-codex",
                "model": "review",
                "call_count": 1,
            }
        ],
        "pi_unattributed_assistant_calls": 0,
    }
    paths = write_run_records(
        [
            log(
                model_usage={
                    "openai/resource": {
                        "input_tokens": 10,
                        "input_tokens_cache_read": 1,
                        "output_tokens": 3,
                        "reasoning_tokens": 0,
                        "total_cost": 0.02,
                    }
                },
                score_value=score(metadata=metadata),
            )
        ],
        tmp_path,
        hybrid_agent_profile(),
        run_name="test",
        harness_identity=HARNESS_IDENTITY,
        cohort_identity=COHORT_IDENTITY,
    )
    usage = json.loads(paths[0].read_text(encoding="utf-8"))["usage"]
    assert usage["bridged"]["input_tokens"] == 10
    assert usage["direct"]["input_tokens"] == 20
    assert usage["total"]["input_tokens"] == 30
    assert usage["total"]["reported_cost"] == pytest.approx(0.05)
    assert usage["cost_coverage"] == "complete"


def test_incomplete_log_is_recorded_but_excluded(tmp_path):
    with pytest.warns(UserWarning, match="excluded incomplete"):
        paths = write_run_records(
            [log(status="error")],
            tmp_path,
            agent_profile(),
            run_name="test",
            harness_identity=HARNESS_IDENTITY,
            cohort_identity=COHORT_IDENTITY,
        )
    assert paths == []
    invalid = list((tmp_path / "_invalid").glob("*.invalid.json"))
    assert len(invalid) == 1
    assert json.loads(invalid[0].read_text())["validity"]["valid"] is False
