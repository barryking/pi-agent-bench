import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from inspect_ai.scorer import Score

from pi_agent_bench.model_profiles import ModelProfile
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
    "benchmark_fingerprint": "test-benchmark",
    "sandbox_image": SANDBOX_IMAGE,
    "sandbox_image_id": "sha256:test-image",
    "sandbox_repo_digests": [],
    "sandbox_source_fingerprint": "test-sandbox-source",
}


def test_pins_match_package_and_sandbox_contract():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")

    assert pyproject["project"]["version"] == FRAMEWORK_VERSION
    assert f"inspect-ai=={INSPECT_VERSION}" in pyproject["project"]["dependencies"]
    assert "ARG PI_VERSION" in dockerfile
    assert 'dev.pi.version="${PI_VERSION}"' in dockerfile
    assert 'org.opencontainers.image.version="${FRAMEWORK_VERSION}"' in dockerfile
    assert "ARG BENCHMARK_SOURCE_FINGERPRINT=unknown" in dockerfile
    assert 'dev.pi.benchmark-source="${BENCHMARK_SOURCE_FINGERPRINT}"' in dockerfile
    assert SANDBOX_IMAGE in compose


def test_result_record_contains_actual_harness_and_model_versions(tmp_path):
    score = Score(
        value=1.0,
        metadata={
            "pi_version": PI_VERSION,
            "pi": {"turns": 2, "input_tokens": 10, "output_tokens": 3},
        },
    )
    sample = SimpleNamespace(
        id="case-1",
        epoch=1,
        scores={"quality": score},
        metadata={},
        started_at="2026-07-25T00:00:00Z",
        total_time=1.5,
        model_usage={},
        turn_count=2,
        error=None,
        events=[
            SimpleNamespace(
                event="model",
                role=None,
                working_time=2.0,
                output=SimpleNamespace(
                    usage=SimpleNamespace(output_tokens=8),
                ),
            ),
            SimpleNamespace(event="tool", working_time=0.5),
        ],
        working_time=3.0,
    )
    log = SimpleNamespace(
        eval=SimpleNamespace(
            run_id="run-1",
            task_version="dataset-1",
            model="openai/exact-model",
        ),
        samples=[sample],
        location="/tmp/run.eval",
    )
    profile = ModelProfile(
        name="dgx",
        kind="local",
        model="openai/exact-model",
        runtime_env={},
        configuration={
            "weights": "model@revision",
            "runtime": "vllm",
            "runtime_version": "26.05.post1",
        },
    )

    [record_path] = write_run_records(
        [log],
        tmp_path,
        profile,
        run_name="nightly",
        cache_state="warm",
        harness_identity=HARNESS_IDENTITY,
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))

    assert record["inspect_model"] == "openai/exact-model"
    assert record["model_configuration"]["configuration"]["weights"] == "model@revision"
    assert record["harness"]["pi_version_actual"] == PI_VERSION
    assert record["harness"]["inspect_version"] == INSPECT_VERSION
    assert record["run_name"] == "nightly"
    assert record["cache_state"] == "warm"
    assert record["harness"]["benchmark_fingerprint"]
    assert record["harness"]["repository_commit"] == "test-commit"
    assert record["harness"]["sandbox_image_id"] == "sha256:test-image"
    assert record["model_configuration"]["configuration_fingerprint"]
    assert record["agent_configuration"]["profile"] == "vanilla"
    assert record["agent_configuration"]["configuration_fingerprint"]
    assert record["timing"]["inspect_working_seconds"] == 3.0
    assert record["timing"]["model_working_seconds"] == 2.0
    assert record["timing"]["tool_working_seconds"] == 0.5
    assert record["timing"]["observed_output_tokens_per_model_second"] == 4.0


def test_export_uses_historical_identity_from_the_inspect_log(tmp_path, monkeypatch):
    score = Score(value=1.0, metadata={"success_threshold": 1.0})
    sample = SimpleNamespace(
        id="historical-case",
        epoch=1,
        scores={"quality": score},
        metadata={},
        started_at="2026-07-20T00:00:00Z",
        total_time=1.0,
        model_usage={},
        turn_count=1,
        error=None,
        events=[],
        working_time=0.8,
    )
    profile = ModelProfile(
        name="historical-model",
        kind="hosted",
        model="openai/historical",
        runtime_env={},
        configuration={},
    )
    historical = {
        **HARNESS_IDENTITY,
        "repository_commit": "commit-from-original-run",
        "benchmark_fingerprint": "fingerprint-from-original-run",
        "sandbox_image_id": "sha256:image-from-original-run",
    }
    log = SimpleNamespace(
        status="success",
        eval=SimpleNamespace(
            run_id="historical-run",
            task_version="dataset-1",
            model="openai/historical",
            metadata={
                "pi_agent_bench": {
                    "profile": profile.public_identity(),
                    "agent_profile": {
                        "profile": "vanilla",
                        "configuration": {},
                        "configuration_fingerprint": "vanilla",
                    },
                    "run_name": "historical-baseline",
                    "cache_state": "cold",
                    "harness": historical,
                }
            },
        ),
        samples=[sample],
        location="/logs/historical.eval",
    )
    monkeypatch.setattr(
        "inspect_ai.log.list_eval_logs",
        lambda _logs_dir: [SimpleNamespace(name="/logs/historical.eval")],
    )
    monkeypatch.setattr("inspect_ai.log.read_eval_log", lambda _name: log)

    [path] = export_inspect_logs(tmp_path / "logs", tmp_path / "results")
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["run_name"] == "historical-baseline"
    assert record["harness"]["repository_commit"] == "commit-from-original-run"
    assert record["harness"]["benchmark_fingerprint"] == "fingerprint-from-original-run"
    assert record["harness"]["sandbox_image_id"] == "sha256:image-from-original-run"


def test_result_record_uses_explicit_success_threshold(tmp_path):
    score = Score(
        value=0.8,
        metadata={
            "success_threshold": 0.75,
            "scoring_method": "deterministic-executable-verifier",
        },
    )
    sample = SimpleNamespace(
        id="case-1",
        epoch=1,
        scores={"quality": score},
        metadata={},
        started_at="2026-07-25T00:00:00Z",
        total_time=1.5,
        model_usage={},
        turn_count=2,
        error=None,
    )
    log = SimpleNamespace(
        eval=SimpleNamespace(
            run_id="run-threshold",
            task_version="dataset-1",
            model="openai/evaluated-model",
        ),
        samples=[sample],
        location="/tmp/run.eval",
    )
    profile = ModelProfile(
        name="local-candidate",
        kind="local",
        model="openai/evaluated-model",
        runtime_env={},
        configuration={},
    )

    [record_path] = write_run_records(
        [log],
        tmp_path,
        profile,
        run_name="default",
        harness_identity=HARNESS_IDENTITY,
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))

    assert record["success"] is True
    assert record["score"]["success_threshold"] == 0.75
    assert record["score"]["method"] == "deterministic-executable-verifier"


def test_result_record_can_be_rebuilt_from_profile_identity(tmp_path):
    score = Score(value=1.0, metadata={"success_threshold": 1.0})
    sample = SimpleNamespace(
        id="case-from-log",
        epoch=1,
        scores={"quality": score},
        metadata={},
        started_at="2026-07-25T00:00:00Z",
        total_time=1.0,
        model_usage={},
        turn_count=1,
        error=None,
        events=[],
        working_time=0.8,
    )
    log = SimpleNamespace(
        status="success",
        eval=SimpleNamespace(
            run_id="run-from-log",
            task_version="dataset-1",
            model="openai/exact-model",
        ),
        samples=[sample],
        location="/tmp/run.eval",
    )
    identity = {
        "profile": "local",
        "kind": "local",
        "model": "openai/exact-model",
        "configuration": {"runtime": "vllm"},
        "configuration_fingerprint": "local-vllm",
    }

    [record_path] = write_run_records(
        [log],
        tmp_path,
        identity,
        run_name="default",
        harness_identity=HARNESS_IDENTITY,
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))

    assert record["model_configuration"] == identity


def test_result_record_extracts_structured_inspect_score(tmp_path):
    score = Score(
        value={
            "quality": 0.8,
            "success": 1.0,
            "component.tests": 1.0,
            "component.docs": 0.5,
        },
        metadata={
            "success_threshold": 0.75,
            "components": {"verifier_metadata": 1.0},
        },
    )
    sample = SimpleNamespace(
        id="case-structured",
        epoch=1,
        scores={"outcome_verifier_scorer": score},
        metadata={},
        started_at="2026-07-25T00:00:00Z",
        total_time=1.5,
        model_usage={},
        turn_count=2,
        error=None,
    )
    log = SimpleNamespace(
        status="success",
        eval=SimpleNamespace(
            run_id="run-structured",
            task_version="dataset-1",
            model="openai/evaluated-model",
        ),
        samples=[sample],
        location="/tmp/run.eval",
    )
    profile = ModelProfile(
        name="local-candidate",
        kind="local",
        model="openai/evaluated-model",
        runtime_env={},
        configuration={},
    )

    [record_path] = write_run_records(
        [log],
        tmp_path,
        profile,
        run_name="default",
        harness_identity=HARNESS_IDENTITY,
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))

    assert record["validity"]["valid"] is True
    assert record["score"]["value"] == 0.8
    assert record["success"] is True
    assert record["score"]["components"] == {
        "docs": 0.5,
        "verifier_metadata": 1.0,
        "tests": 1.0,
    }
    assert (
        record["inspect_scores"]["outcome_verifier_scorer"]["value"]["quality"]
        == 0.8
    )


def test_incomplete_log_is_recorded_but_excluded_from_rankings(tmp_path):
    log = SimpleNamespace(
        status="cancelled",
        error=SimpleNamespace(message="interrupted"),
        eval=SimpleNamespace(
            run_id="run-cancelled",
            task_version="dataset-1",
            model="openai/evaluated-model",
        ),
        samples=[],
        location="/tmp/cancelled.eval",
    )
    profile = ModelProfile(
        name="local-candidate",
        kind="local",
        model="openai/evaluated-model",
        runtime_env={},
        configuration={},
    )

    with pytest.warns(UserWarning, match="excluded incomplete"):
        paths = write_run_records(
            [log],
            tmp_path,
            profile,
            run_name="default",
            harness_identity=HARNESS_IDENTITY,
        )

    assert paths == []
    [invalid_path] = list((tmp_path / "_invalid").glob("*.invalid.json"))
    invalid = json.loads(invalid_path.read_text(encoding="utf-8"))
    assert invalid["validity"]["valid"] is False
    assert list(tmp_path.glob("*.json")) == []
