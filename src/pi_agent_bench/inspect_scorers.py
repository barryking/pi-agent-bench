"""Inspect scorers used by Pi Agent Bench."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from inspect_ai.model import GenerateConfig, get_model
from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox, store_as

from .dataset import Expected
from .inspect_agent import PiTelemetry
from .scoring import score_concepts
from .verification import verifier_payload

SCORE_METRICS = {"*": [mean(), stderr(cluster="case_id")]}


@scorer(metrics=SCORE_METRICS)
def planning_concept_scorer():
    async def score(state: TaskState, target: Target) -> Score:
        expected = Expected.from_dict(_expected_metadata(state))
        result = score_concepts(state.output.completion, expected)
        telemetry = store_as(PiTelemetry)
        values = _score_values(
            result.score,
            expected.success_threshold,
            required_components=expected.required_components,
        )
        return Score(
            value=values,
            answer=state.output.completion,
            explanation=(
                f"matched {len(result.matched_required)} required concepts; "
                f"missing {len(result.missing_required)}; "
                f"matched {len(result.matched_forbidden)} forbidden concepts"
            ),
            metadata={
                "scoring_method": "deterministic-concept-smoke",
                "success_threshold": expected.success_threshold,
                "matched_required": list(result.matched_required),
                "missing_required": list(result.missing_required),
                "matched_forbidden": list(result.matched_forbidden),
                "pi": telemetry.summary,
                "pi_version": telemetry.pi_version,
                "pi_wall_seconds": telemetry.wall_seconds,
                "pi_return_code": telemetry.return_code,
            },
        )

    return score


@scorer(metrics=SCORE_METRICS)
def planning_rubric_scorer(component_names: list[str] | None = None):
    """Grade planning output against a weighted rubric using an independent model."""

    async def score(state: TaskState, target: Target) -> Score:
        expected = Expected.from_dict(_expected_metadata(state))
        if not expected.rubric:
            raise ValueError("planning rubric scorer requires expected.rubric")
        grader = get_model(
            role="grader",
            required=True,
            config=GenerateConfig(temperature=0, seed=42, max_tokens=1200),
        )
        grader_model = str(grader)
        evaluated_model = str(
            state.metadata.get("evaluated_model") or state.model
        )
        if grader_model == evaluated_model:
            raise ValueError("the evaluated model cannot grade its own planning output")
        rubric = [
            {
                "id": criterion.id,
                "description": criterion.description,
                "weight": criterion.weight,
            }
            for criterion in expected.rubric
        ]
        prompt = (
            "You are an independent evaluator of a software implementation plan. "
            "Score every rubric criterion from 0 to 4, where 0 is absent or wrong, "
            "1 is materially deficient, 2 is partial, 3 is good, and 4 is complete "
            "and actionable. Judge only the supplied task and answer. Return JSON "
            'only: {\"scores\":{\"criterion-id\":0},\"rationale\":\"brief\"}.\n\n'
            f"TASK:\n{state.input_text}\n\n"
            f"RUBRIC:\n{json.dumps(rubric, sort_keys=True)}\n\n"
            f"ANSWER:\n{state.output.completion}"
        )
        result = await grader.generate(prompt)
        payload = _json_object(result.completion)
        raw_scores = payload.get("scores", {})
        if not isinstance(raw_scores, dict):
            raise ValueError("grader response scores must be an object")
        weighted = 0.0
        total_weight = 0.0
        components: dict[str, float] = {}
        for criterion in expected.rubric:
            raw_value = raw_scores.get(criterion.id)
            if (
                not isinstance(raw_value, (int, float))
                or isinstance(raw_value, bool)
                or not 0 <= raw_value <= 4
            ):
                raise ValueError(
                    f"grader response missing valid 0-4 score for {criterion.id}"
                )
            normalized = float(raw_value) / 4
            components[criterion.id] = normalized
            weighted += normalized * criterion.weight
            total_weight += criterion.weight
        concept_result = score_concepts(state.output.completion, expected)
        forbidden_penalty = (
            len(concept_result.matched_forbidden)
            / max(len(expected.forbidden_concepts), 1)
        )
        value = max(0.0, min(1.0, weighted / total_weight - forbidden_penalty))
        telemetry = store_as(PiTelemetry)
        values = _score_values(
            value,
            expected.success_threshold,
            components,
            component_names,
            expected.required_components,
        )
        return Score(
            value=values,
            answer=state.output.completion,
            explanation=str(payload.get("rationale", "independent rubric grade")),
            metadata={
                "components": components,
                "scoring_method": "independent-model-weighted-rubric",
                "grader_model": grader_model,
                "grader_raw_response": result.completion,
                "success_threshold": expected.success_threshold,
                "required_components": list(expected.required_components),
                "matched_forbidden": list(concept_result.matched_forbidden),
                "pi": telemetry.summary,
                "pi_version": telemetry.pi_version,
                "pi_wall_seconds": telemetry.wall_seconds,
                "pi_return_code": telemetry.return_code,
            },
        )

    return score


@scorer(metrics=SCORE_METRICS)
def coding_verifier_scorer(component_names: list[str] | None = None):
    async def score(state: TaskState, target: Target) -> Score:
        expected = Expected.from_dict(_expected_metadata(state))
        telemetry = store_as(PiTelemetry)
        result = await sandbox().exec(
            list(expected.verifier_command),
            cwd="/workspace",
            user="root",
            timeout=120,
            timeout_retry=False,
        )
        await sandbox().exec(
            ["git", "add", "-N", "."],
            cwd="/workspace",
            timeout=30,
            timeout_retry=False,
        )
        diff_result = await sandbox().exec(
            ["git", "diff", "--binary", "--no-ext-diff", "HEAD"],
            cwd="/workspace",
            timeout=30,
            timeout_retry=False,
        )
        payload = verifier_payload(result.stdout)
        value = float(payload.get("score", 0.0))
        components = payload.get("components", {})
        if not isinstance(components, dict):
            components = {}
        quality = max(0.0, min(1.0, value))
        values = _score_values(
            quality,
            expected.success_threshold,
            components,
            component_names,
            expected.required_components,
        )
        return Score(
            value=values,
            explanation=str(payload.get("explanation", result.stderr or "verification failed")),
            metadata={
                "components": components,
                "scoring_method": "deterministic-executable-verifier",
                "success_threshold": expected.success_threshold,
                "required_components": list(expected.required_components),
                "verifier_return_code": result.returncode,
                "verifier_stdout": result.stdout,
                "verifier_stderr": result.stderr,
                "final_diff": diff_result.stdout if diff_result.success else "",
                "pi": telemetry.summary,
                "pi_version": telemetry.pi_version,
                "pi_wall_seconds": telemetry.wall_seconds,
                "pi_return_code": telemetry.return_code,
            },
        )

    return score


def _score_values(
    quality: float,
    success_threshold: float,
    components: dict[str, Any] | None = None,
    component_names: list[str] | None = None,
    required_components: tuple[str, ...] = (),
) -> dict[str, float]:
    """Return stable first-class Inspect score fields for a task group."""
    supplied = components or {}
    critical_passed = all(
        _component_passed(supplied.get(name)) for name in required_components
    )
    values = {
        "quality": quality,
        "success": float(quality >= success_threshold and critical_passed),
    }
    names = component_names if component_names is not None else sorted(supplied)
    for name in names:
        value = supplied.get(name)
        field = f"component.{name}"
        if isinstance(value, (bool, int, float)):
            values[field] = float(value)
        else:
            values[field] = math.nan
    return values


def _component_passed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 1.0
    )


def _expected_metadata(state: TaskState) -> dict[str, Any]:
    expected = state.metadata.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("sample metadata is missing expected verifier data")
    return expected


def _json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("grader did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("grader JSON must be an object")
    return value
