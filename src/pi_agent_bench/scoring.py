"""Small deterministic Pi Agent Bench scorers."""

from __future__ import annotations

from dataclasses import dataclass

from .dataset import Expected


@dataclass(frozen=True)
class ConceptScore:
    score: float
    matched_required: tuple[str, ...]
    missing_required: tuple[str, ...]
    matched_forbidden: tuple[str, ...]


def score_concepts(output: str, expected: Expected) -> ConceptScore:
    """Score explicit concept presence.

    This is intentionally simple. It is suitable for objective terms and smoke
    tests, not as a replacement for a calibrated planning rubric.
    """
    normalised = output.casefold()
    matched_required = tuple(
        concept for concept in expected.required_concepts if concept.casefold() in normalised
    )
    missing_required = tuple(
        concept for concept in expected.required_concepts if concept.casefold() not in normalised
    )
    matched_forbidden = tuple(
        concept for concept in expected.forbidden_concepts if concept.casefold() in normalised
    )

    required_total = len(expected.required_concepts)
    required_score = len(matched_required) / required_total if required_total else 1.0
    forbidden_penalty = len(matched_forbidden) / max(len(expected.forbidden_concepts), 1)
    score = max(0.0, required_score - forbidden_penalty)

    return ConceptScore(
        score=score,
        matched_required=matched_required,
        missing_required=missing_required,
        matched_forbidden=matched_forbidden,
    )
