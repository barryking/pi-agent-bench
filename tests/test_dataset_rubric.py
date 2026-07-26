import pytest

from pi_agent_bench.dataset import Expected


def test_weighted_rubric_and_threshold_are_validated():
    expected = Expected.from_dict(
        {
            "required_concepts": ["constraint"],
            "rubric": [
                {
                    "id": "architecture",
                    "description": "Technically coherent design",
                    "weight": 2,
                }
            ],
            "success_threshold": 0.75,
        }
    )

    assert expected.rubric[0].weight == 2
    assert expected.success_threshold == 0.75


def test_duplicate_rubric_ids_are_rejected():
    with pytest.raises(ValueError, match="criterion ids must be unique"):
        Expected.from_dict(
            {
                "rubric": [
                    {"id": "same", "description": "one"},
                    {"id": "same", "description": "two"},
                ]
            }
        )
