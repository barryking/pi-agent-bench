import json
import subprocess
from types import SimpleNamespace

import pytest

from pi_agent_bench.inspect_tasks import (
    _validate_git_fixture,
    coding_suite,
    coding_tasks,
    load_case_suite,
    planning_suite,
    planning_tasks,
)


def test_suites_load_multiple_cases_with_docker_sandbox():
    planning = planning_suite()
    coding = coding_suite()

    assert planning.sandbox.type == "docker"
    assert coding.sandbox.type == "docker"
    assert len(planning.dataset) == 2
    assert len(coding.dataset) == 2
    assert planning.dataset[0].metadata["phase"] == "planning"
    assert planning.dataset[0].metadata["expected"]["success_threshold"] == 0.75
    assert len(planning.dataset[0].metadata["expected"]["rubric"]) == 5
    assert coding.dataset[0].metadata["phase"] == "coding"
    assert all(sample.files for sample in coding.dataset)
    assert "if [ -e .git ]" in coding.dataset[0].setup
    assert {sample.id for sample in coding.dataset} == {
        "code-health-endpoint-001",
        "code-version-endpoint-002",
    }


def test_owned_starter_suite_has_five_planning_and_coding_cases():
    planning = planning_tasks("evals/starter/planning.jsonl")
    coding = coding_tasks("evals/starter/coding.jsonl")

    assert sum(len(task.dataset) for task in planning) == 5
    assert sum(len(task.dataset) for task in coding) == 5
    assert all(
        sample.metadata["owned"] is True
        for task in [*planning, *coding]
        for sample in task.dataset
    )
    assert all(
        sample.metadata["expected"]["required_components"]
        for task in coding
        for sample in task.dataset
    )


def test_suite_rejects_mixed_dataset_versions(tmp_path):
    cases = [
        {
            "id": f"plan-{index}",
            "phase": "planning",
            "instruction": "Write a plan.",
            "limits": {"seconds": 60, "turns": 3, "context_tokens": 4096},
            "expected": {"required_concepts": ["rollout"]},
                "metadata": {
                    "dataset_version": version,
                    "draft": False,
                    "synthetic": True,
                },
        }
        for index, version in enumerate(("1", "2"), start=1)
    ]
    path = tmp_path / "planning.jsonl"
    path.write_text(
        "\n".join(json.dumps(case) for case in cases),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="one non-empty"):
        load_case_suite(path, "planning")


def test_cli_task_builder_splits_mixed_execution_limits(tmp_path):
    cases = [
        {
            "id": f"plan-{index}",
            "phase": "planning",
            "instruction": "Write a plan.",
            "limits": {
                "seconds": seconds,
                "turns": turns,
                "context_tokens": 4096,
                "total_tokens": tokens,
            },
            "expected": {"required_concepts": ["rollout"]},
                "metadata": {
                    "dataset_version": "1",
                    "draft": False,
                    "synthetic": True,
                },
        }
        for index, (seconds, turns, tokens) in enumerate(
            ((60, 3, 4096), (120, 5, 8192)),
            start=1,
        )
    ]
    path = tmp_path / "planning.jsonl"
    path.write_text(
        "\n".join(json.dumps(case) for case in cases),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="different execution limits"):
        planning_suite(str(path))

    tasks = planning_tasks(str(path))

    assert len(tasks) == 2
    assert {
        (task.time_limit, task.turn_limit, task.token_limit)
        for task in tasks
    } == {(60, 3, 4096), (120, 5, 8192)}


def test_planning_grader_is_an_inspect_model_role():
    task = planning_suite(grader_model="mockllm/grader")

    assert str(task.model_roles["grader"]) == "mockllm/grader"


def test_draft_case_validates_but_cannot_run(tmp_path):
    case = {
        "id": "plan-draft",
        "phase": "planning",
        "instruction": "Write a plan.",
        "limits": {"seconds": 60, "turns": 3, "context_tokens": 4096},
        "expected": {"required_concepts": ["rollout"]},
        "metadata": {
            "dataset_version": "draft-1",
            "draft": True,
            "synthetic": True,
        },
    }
    path = tmp_path / "planning.jsonl"
    path.write_text(json.dumps(case), encoding="utf-8")

    _, cases, _ = load_case_suite(path, "planning")
    assert cases[0].metadata["draft"] is True
    with pytest.raises(ValueError, match="refusing to run draft"):
        planning_tasks(str(path))


def test_suite_rejects_missing_coding_fixture(tmp_path):
    case = {
        "id": "code-missing",
        "phase": "coding",
        "instruction": "Make a change.",
        "limits": {"seconds": 60, "turns": 3, "context_tokens": 4096},
        "expected": {
            "verifier_command": [
                "python3",
                "/opt/verifiers/code-missing/verify.py",
            ]
        },
        "metadata": {
            "dataset_version": "1",
            "fixture": "missing-fixture",
            "draft": False,
            "synthetic": True,
        },
    }
    path = tmp_path / "coding.jsonl"
    path.write_text(json.dumps(case), encoding="utf-8")

    with pytest.raises(ValueError, match="fixture directory does not exist"):
        load_case_suite(path, "coding")


def test_cloned_fixture_requires_pinned_clean_commit(tmp_path):
    fixture = tmp_path / "repo"
    fixture.mkdir()
    subprocess.run(["git", "-C", str(fixture), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(fixture), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(fixture), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (fixture / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(fixture), "add", "."], check=True)
    subprocess.run(["git", "-C", str(fixture), "commit", "-qm", "baseline"], check=True)
    head = subprocess.run(
        ["git", "-C", str(fixture), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    case = SimpleNamespace(id="code-real-001", metadata={"source_commit": head})

    _validate_git_fixture(case, fixture)

    (fixture / "README.md").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be clean"):
        _validate_git_fixture(case, fixture)
