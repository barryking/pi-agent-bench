import json

import pytest

from dgx_agent_evals.dataset import load_cases


def write_cases(tmp_path, *cases):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in cases), encoding="utf-8")
    return path


def planning_case(case_id="plan-1"):
    return {
        "id": case_id,
        "phase": "planning",
        "instruction": "Write a plan.",
        "limits": {"seconds": 60, "turns": 3, "context_tokens": 4096},
        "expected": {
            "required_concepts": ["rollout"],
            "forbidden_concepts": [],
            "verifier_command": [],
        },
    }


def test_loads_valid_case(tmp_path):
    cases = load_cases(write_cases(tmp_path, planning_case()))

    assert len(cases) == 1
    assert cases[0].id == "plan-1"
    assert cases[0].expected.required_concepts == ("rollout",)


def test_rejects_duplicate_ids(tmp_path):
    path = write_cases(tmp_path, planning_case(), planning_case())

    with pytest.raises(ValueError, match="duplicate id"):
        load_cases(path)


def test_coding_case_requires_verifier(tmp_path):
    case = planning_case("code-1")
    case["phase"] = "coding"
    case["expected"]["verifier_command"] = []

    with pytest.raises(ValueError, match="coding cases need verifier_command"):
        load_cases(write_cases(tmp_path, case))
