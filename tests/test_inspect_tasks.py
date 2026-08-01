import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from pi_agent_bench.agent_profiles import AgentProfile
from pi_agent_bench.dataset import load_cases
from pi_agent_bench.inspect_tasks import (
    _validate_git_starting_repository,
    load_case_suite,
    outcome_suite,
    outcome_tasks,
)
from pi_agent_bench.model_profiles import ModelProfile
from pi_agent_bench.pi_profiles import vanilla_pi_profile

ROOT = Path(__file__).resolve().parents[1]


def _sample_cases():
    return [
        json.loads(line) for line in (ROOT / "evals/sample/cases.jsonl").read_text().splitlines()
    ]


def _agent_args():
    resource = ModelProfile.from_dict(
        "test-model",
        {
            "kind": "local",
            "model": "openai/test",
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
            "configuration": {"revision": "test"},
        },
    )
    profile = AgentProfile(
        name="test-agent",
        description="Test agent.",
        pi_profile=vanilla_pi_profile(),
        model_resources=(resource,),
        default_model_resource="test-model",
    )
    return {"agent_profile": profile, "bridged_models": {"test-model": object()}}


def test_suite_loads_complete_outcomes_with_docker_sandbox():
    suite = outcome_suite(**_agent_args())

    assert suite.sandbox.type == "docker"
    assert len(suite.dataset) == 2
    assert all(sample.files for sample in suite.dataset)
    assert "if [ -e .git ]" in suite.dataset[0].setup
    assert {sample.id for sample in suite.dataset} == {
        "sample-health-endpoint",
        "sample-version-endpoint",
    }


def test_owned_starter_suite_has_five_complete_outcomes():
    tasks = outcome_tasks("evals/starter/cases.jsonl", **_agent_args())

    assert sum(len(task.dataset) for task in tasks) == 5
    assert all(sample.metadata["owned"] is True for task in tasks for sample in task.dataset)
    assert all(
        sample.metadata["expected"]["required_components"]
        for task in tasks
        for sample in task.dataset
    )


@pytest.mark.parametrize(
    ("name", "case_id"),
    (
        ("user-list-filter", "user-list-filter"),
        ("user-idempotency", "user-idempotency"),
    ),
)
def test_external_candidates_are_tracked_as_non_runnable_drafts(name, case_id):
    [case] = load_cases(ROOT / "evals" / "candidates" / name / "cases.jsonl")

    assert case.id == case_id
    assert case.metadata["draft"] is True
    assert case.metadata["dataset_version"].endswith("-draft-1")
    assert case.metadata["starting_repository"].startswith("local-repos/")
    assert case.expected.verifier_command == (
        "python3",
        f"/opt/verifiers/{case_id}/verify.py",
    )
    assert (ROOT / "verifiers" / case.id / "verify.py").is_file()


def test_suite_rejects_mixed_dataset_versions(tmp_path):
    cases = _sample_cases()
    cases[0]["metadata"]["dataset_version"] = "1"
    cases[1]["metadata"]["dataset_version"] = "2"
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in cases))

    with pytest.raises(ValueError, match="one non-empty"):
        load_case_suite(path)


def test_task_builder_splits_mixed_execution_limits(tmp_path):
    cases = _sample_cases()
    cases[0]["limits"].update(seconds=60, turns=3, total_tokens=4096)
    cases[1]["limits"].update(seconds=120, turns=5, total_tokens=8192)
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in cases))

    with pytest.raises(ValueError, match="different execution limits"):
        outcome_suite(str(path), **_agent_args())

    tasks = outcome_tasks(str(path), **_agent_args())

    assert len(tasks) == 2
    assert {(task.time_limit, task.turn_limit, task.token_limit) for task in tasks} == {
        (60, 3, 4096),
        (120, 5, 8192),
    }


def test_draft_case_validates_but_cannot_run(tmp_path):
    case = _sample_cases()[0]
    case["metadata"]["draft"] = True
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(case))

    _, cases, _ = load_case_suite(path)
    assert cases[0].metadata["draft"] is True
    with pytest.raises(ValueError, match="refusing to run draft"):
        outcome_tasks(str(path), **_agent_args())


def test_suite_rejects_missing_starting_repository(tmp_path):
    case = _sample_cases()[0]
    case["metadata"]["starting_repository"] = "missing-starting_repository"
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(case))

    with pytest.raises(ValueError, match="starting repository directory does not exist"):
        load_case_suite(path)


def test_cloned_starting_repository_requires_pinned_clean_commit(tmp_path):
    starting_repository = tmp_path / "repo"
    starting_repository.mkdir()
    subprocess.run(["git", "-C", str(starting_repository), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(starting_repository), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(starting_repository), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (starting_repository / "README.md").write_text("baseline\n")
    subprocess.run(["git", "-C", str(starting_repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(starting_repository), "commit", "-qm", "baseline"], check=True)
    head = subprocess.run(
        ["git", "-C", str(starting_repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    case = SimpleNamespace(id="outcome-real-001", metadata={"source_commit": head})

    _validate_git_starting_repository(case, starting_repository)

    (starting_repository / "README.md").write_text("dirty\n")
    with pytest.raises(ValueError, match="must be clean"):
        _validate_git_starting_repository(case, starting_repository)
