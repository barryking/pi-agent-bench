import json

from inspect_ai import Task, eval, score
from inspect_ai.dataset import Sample
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.solver import generate

from pi_agent_bench.cli_execution import _eval_set_id, _load_full_logs
from pi_agent_bench.inspect_scorers import planning_rubric_scorer


def test_eval_set_ids_are_safe_and_profile_specific():
    sol = _eval_set_id("pilot v1", "gpt-5.6-sol")
    luna = _eval_set_id("pilot v1", "gpt-5.6-luna")
    guided = _eval_set_id("pilot v1", "gpt-5.6-sol", "team tools")

    assert sol == "pilot-v1-gpt-5-6-sol"
    assert luna == "pilot-v1-gpt-5-6-luna"
    assert guided == "pilot-v1-gpt-5-6-sol-team-tools"
    assert sol != luna


def test_completed_planning_log_can_be_rescored_with_grader_role(tmp_path):
    sample = Sample(
        id="plan-rescore",
        input="Produce a safe rollout plan.",
        metadata={
            "case_id": "plan-rescore",
            "phase": "planning",
            "evaluated_model": "mockllm/candidate",
            "expected": {
                "required_concepts": ["rollout"],
                "forbidden_concepts": [],
                "verifier_command": [],
                "success_threshold": 0.75,
                "rubric": [
                    {
                        "id": "rollout",
                        "description": "Provides validation and rollback.",
                        "weight": 1,
                    }
                ],
            },
        },
    )
    candidate = get_model(
        "mockllm/candidate",
        custom_outputs=[
            ModelOutput.from_content(
                model="candidate",
                content="Stage the release, validate it, then roll back on failure.",
            )
        ],
    )
    [log] = eval(
        Task(dataset=[sample], solver=generate()),
        model=candidate,
        log_dir=str(tmp_path),
        display="none",
    )
    grader_payload = json.dumps(
        {
            "scores": {"rollout": 3},
            "rationale": "Complete enough for the configured threshold.",
        }
    )
    grader = get_model(
        "mockllm/grader",
        custom_outputs=[
            ModelOutput.from_content(model="grader", content=grader_payload)
        ],
    )

    rescored = score(
        log,
        planning_rubric_scorer(["rollout"]),
        model_roles={"grader": grader},
        action="overwrite",
        display="none",
    )

    rubric_score = next(iter(rescored.samples[0].scores.values()))
    assert rubric_score.value == {
        "quality": 0.75,
        "success": 1.0,
        "component.rollout": 0.75,
    }
    assert rubric_score.metadata["grader_model"] == "mockllm/grader"

    header = read_eval_log(log.location, header_only=True)
    assert header.samples is None
    [materialized] = _load_full_logs([header])
    assert materialized.samples[0].id == "plan-rescore"
