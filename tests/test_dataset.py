import json

import pytest

from pi_agent_bench.dataset import load_cases


def write_cases(tmp_path, *cases):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in cases))
    return path


def outcome_case(case_id="outcome-1"):
    return {
        "id": case_id,
        "instruction": "Complete the requested repository change.",
        "limits": {"seconds": 60, "turns": 3, "context_tokens": 4096},
        "expected": {
            "verifier_command": [
                "python3",
                f"/opt/verifiers/{case_id}/verify.py",
            ],
        },
        "metadata": {
            "dataset_version": "test-1",
            "starting_repository": f"starting-repos/{case_id}",
            "score_components": ["requirements"],
            "draft": False,
            "synthetic": True,
        },
    }


def test_loads_valid_outcome_case(tmp_path):
    cases = load_cases(write_cases(tmp_path, outcome_case()))

    assert len(cases) == 1
    assert cases[0].id == "outcome-1"
    assert cases[0].limits.total_tokens == 4096


def test_total_token_budget_is_separate_from_context(tmp_path):
    case = outcome_case()
    case["limits"]["total_tokens"] = 12000

    loaded = load_cases(write_cases(tmp_path, case))[0]

    assert loaded.limits.context_tokens == 4096
    assert loaded.limits.total_tokens == 12000


def test_accepts_multi_page_prd_style_instruction(tmp_path):
    case = outcome_case()
    case["instruction"] = "\n\n".join(
        f"Requirement {number}: implement and verify this observable behaviour."
        for number in range(300)
    )

    loaded = load_cases(write_cases(tmp_path, case))[0]

    assert "Requirement 299" in loaded.instruction
    assert len(loaded.instruction) > 10_000


def test_rejects_duplicate_ids(tmp_path):
    path = write_cases(tmp_path, outcome_case(), outcome_case())

    with pytest.raises(ValueError, match="duplicate id"):
        load_cases(path)


def test_outcome_case_requires_verifier(tmp_path):
    case = outcome_case()
    case["expected"]["verifier_command"] = []

    with pytest.raises(ValueError, match="outcome cases need verifier_command"):
        load_cases(write_cases(tmp_path, case))


def test_schema_rejects_unknown_case_fields(tmp_path):
    case = outcome_case()
    case["surprise"] = True

    with pytest.raises(ValueError, match="Additional properties"):
        load_cases(write_cases(tmp_path, case))
