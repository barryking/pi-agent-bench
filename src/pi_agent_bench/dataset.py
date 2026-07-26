"""Pi Agent Bench case loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Phase = Literal["planning", "coding", "end_to_end"]


@dataclass(frozen=True)
class RubricCriterion:
    id: str
    description: str
    weight: float = 1.0

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RubricCriterion:
        criterion_id = _required_string(value, "id")
        description = _required_string(value, "description")
        weight = value.get("weight", 1.0)
        if (
            not isinstance(weight, (int, float))
            or isinstance(weight, bool)
            or weight <= 0
        ):
            raise ValueError(f"{criterion_id}: rubric weight must be positive")
        return cls(id=criterion_id, description=description, weight=float(weight))


@dataclass(frozen=True)
class Limits:
    seconds: int
    turns: int
    context_tokens: int
    total_tokens: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Limits:
        context_tokens = _positive_int(value, "context_tokens")
        total_tokens = value.get("total_tokens", context_tokens)
        if (
            not isinstance(total_tokens, int)
            or isinstance(total_tokens, bool)
            or total_tokens <= 0
        ):
            raise ValueError("total_tokens must be a positive integer")
        limits = cls(
            seconds=_positive_int(value, "seconds"),
            turns=_positive_int(value, "turns"),
            context_tokens=context_tokens,
            total_tokens=total_tokens,
        )
        return limits


@dataclass(frozen=True)
class Expected:
    required_concepts: tuple[str, ...] = ()
    forbidden_concepts: tuple[str, ...] = ()
    verifier_command: tuple[str, ...] = ()
    rubric: tuple[RubricCriterion, ...] = ()
    success_threshold: float = 1.0

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Expected:
        rubric_value = value.get("rubric", [])
        if not isinstance(rubric_value, list) or not all(
            isinstance(item, dict) for item in rubric_value
        ):
            raise ValueError("rubric must be a list of objects")
        rubric = tuple(RubricCriterion.from_dict(item) for item in rubric_value)
        rubric_ids = [criterion.id for criterion in rubric]
        if len(rubric_ids) != len(set(rubric_ids)):
            raise ValueError("rubric criterion ids must be unique")
        success_threshold = value.get("success_threshold", 1.0)
        if (
            not isinstance(success_threshold, (int, float))
            or isinstance(success_threshold, bool)
            or not 0 < success_threshold <= 1
        ):
            raise ValueError("success_threshold must be greater than 0 and at most 1")
        return cls(
            required_concepts=_string_tuple(value.get("required_concepts", [])),
            forbidden_concepts=_string_tuple(value.get("forbidden_concepts", [])),
            verifier_command=_string_tuple(value.get("verifier_command", [])),
            rubric=rubric,
            success_threshold=float(success_threshold),
        )


@dataclass(frozen=True)
class GoldenCase:
    id: str
    phase: Phase
    instruction: str
    limits: Limits
    expected: Expected
    context_files: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GoldenCase:
        case_id = _required_string(value, "id")
        phase = value.get("phase")
        if phase not in {"planning", "coding", "end_to_end"}:
            raise ValueError(f"{case_id}: phase must be planning, coding, or end_to_end")

        expected = Expected.from_dict(_required_dict(value, "expected"))
        if phase == "planning" and not expected.required_concepts:
            raise ValueError(f"{case_id}: planning cases need required_concepts")
        if phase == "coding" and not expected.verifier_command:
            raise ValueError(f"{case_id}: coding cases need verifier_command")

        return cls(
            id=case_id,
            phase=phase,
            instruction=_required_string(value, "instruction"),
            limits=Limits.from_dict(_required_dict(value, "limits")),
            expected=expected,
            context_files=_string_tuple(value.get("context_files", [])),
            tags=_string_tuple(value.get("tags", [])),
            metadata=_optional_dict(value.get("metadata", {}), "metadata"),
        )


def load_cases(path: str | Path) -> list[GoldenCase]:
    """Load and validate newline-delimited golden cases."""
    source = Path(path)
    cases: list[GoldenCase] = []
    seen_ids: set[str] = set()

    with source.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{source}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{source}:{line_number}: each case must be a JSON object")

            case = GoldenCase.from_dict(payload)
            if case.id in seen_ids:
                raise ValueError(f"{source}:{line_number}: duplicate id {case.id!r}")
            seen_ids.add(case.id)
            cases.append(case)

    if not cases:
        raise ValueError(f"{source}: dataset contains no cases")
    return cases


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item.strip()


def _required_dict(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be an object")
    return item


def _optional_dict(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _positive_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return item


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError("expected a list of non-empty strings")
    return tuple(value)
