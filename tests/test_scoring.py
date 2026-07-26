from pi_agent_bench.dataset import Expected
from pi_agent_bench.inspect_scorers import _score_values
from pi_agent_bench.scoring import score_concepts


def test_scores_required_and_forbidden_concepts():
    expected = Expected(
        required_concepts=("observability", "rollout"),
        forbidden_concepts=("disable authentication",),
    )

    score = score_concepts(
        "The plan includes observability and a staged rollout.",
        expected,
    )

    assert score.score == 1.0
    assert score.missing_required == ()
    assert score.matched_forbidden == ()


def test_forbidden_concept_reduces_score():
    expected = Expected(
        required_concepts=("observability",),
        forbidden_concepts=("disable authentication",),
    )

    score = score_concepts(
        "Add observability, then disable authentication.",
        expected,
    )

    assert score.score == 0.0
    assert score.matched_forbidden == ("disable authentication",)


def test_critical_component_can_block_success_without_hiding_quality():
    values = _score_values(
        0.9,
        0.8,
        {"core_behaviour": 0.0, "documentation": 1.0},
        ["core_behaviour", "documentation"],
        ("core_behaviour",),
    )

    assert values["quality"] == 0.9
    assert values["success"] == 0.0


def test_success_requires_threshold_and_every_critical_component():
    values = _score_values(
        0.9,
        0.8,
        {"first": 1.0, "second": True},
        ["first", "second"],
        ("first", "second"),
    )

    assert values["success"] == 1.0
