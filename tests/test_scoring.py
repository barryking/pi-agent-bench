from dgx_agent_evals.dataset import Expected
from dgx_agent_evals.scoring import score_concepts


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
