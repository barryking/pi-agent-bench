"""Inspect scorers used by Pi Agent Bench."""

from __future__ import annotations

import math
from typing import Any

from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox, store_as

from .dataset import Expected
from .inspect_agent import PiTelemetry
from .verification import verifier_payload

SCORE_METRICS = {"*": [mean(), stderr(cluster="case_id")]}


@scorer(metrics=SCORE_METRICS)
def outcome_verifier_scorer(component_names: list[str] | None = None):
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
                "pi_direct_usage": telemetry.direct_usage,
                "pi_direct_cost_reported_calls": telemetry.direct_cost_reported_calls,
                "pi_observed_models": telemetry.observed_models,
                "pi_unattributed_assistant_calls": telemetry.unattributed_assistant_calls,
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
    critical_passed = all(_component_passed(supplied.get(name)) for name in required_components)
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
