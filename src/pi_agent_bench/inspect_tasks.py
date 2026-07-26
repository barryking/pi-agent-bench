"""Inspect tasks for Pi Agent Bench case suites."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import Model

from pi_agent_bench.dataset import GoldenCase, load_cases
from pi_agent_bench.inspect_agent import configure_pi_case, pi_agent
from pi_agent_bench.inspect_scorers import (
    coding_verifier_scorer,
    planning_concept_scorer,
    planning_rubric_scorer,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPOSITORY_ROOT / "docker" / "compose.yaml"
DEFAULT_PLANNING_DATASET = REPOSITORY_ROOT / "evals" / "planning" / "sample.jsonl"
DEFAULT_CODING_DATASET = REPOSITORY_ROOT / "evals" / "coding" / "sample.jsonl"


@task
def planning_suite(
    dataset: str = str(DEFAULT_PLANNING_DATASET),
    grader_model: str | Model | None = None,
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
) -> Task:
    source, cases, version = load_case_suite(dataset, "planning")
    _reject_draft_cases(cases)
    limits = _uniform_limits(cases, source)
    return _planning_task(
        source,
        cases,
        version,
        limits,
        grader_model=grader_model,
        direct_provider=direct_provider,
        direct_model=direct_model,
        direct_auth_file=direct_auth_file,
        thinking_level=thinking_level,
    )


def planning_tasks(
    dataset: str = str(DEFAULT_PLANNING_DATASET),
    grader_model: str | Model | None = None,
    evaluated_model: str | None = None,
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
) -> list[Task]:
    """Build exact-limit tasks, splitting a mixed-limit planning dataset."""
    source, cases, version = load_case_suite(dataset, "planning")
    _reject_draft_cases(cases)
    return [
        _planning_task(
            source,
            group,
            version,
            limits,
            grader_model=grader_model,
            evaluated_model=evaluated_model,
            direct_provider=direct_provider,
            direct_model=direct_model,
            direct_auth_file=direct_auth_file,
            thinking_level=thinking_level,
            name=_task_group_name("planning", limits),
        )
        for limits, group in _limit_groups(cases)
    ]


def _planning_task(
    source: Path,
    cases: list[GoldenCase],
    version: str,
    limits: tuple[int, int, int],
    *,
    grader_model: str | Model | None = None,
    evaluated_model: str | None = None,
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
    name: str | None = None,
) -> Task:
    seconds, turns, total_tokens = limits
    rubric_components = sorted(
        {criterion.id for case in cases for criterion in case.expected.rubric}
    )
    return Task(
        dataset=[
            _planning_sample(case, source, evaluated_model)
            for case in cases
        ],
        solver=[
            configure_pi_case(),
            pi_agent(
                phase="planning",
                direct_provider=direct_provider,
                direct_model=direct_model,
                direct_auth_file=direct_auth_file,
                thinking_level=thinking_level,
            ),
        ],
        scorer=(
            planning_rubric_scorer(rubric_components)
            if grader_model
            else planning_concept_scorer()
        ),
        model_roles={"grader": grader_model} if grader_model else None,
        sandbox=("docker", str(COMPOSE_FILE)),
        time_limit=seconds,
        turn_limit=turns,
        token_limit=total_tokens,
        name=name,
        version=version,
        tags=_suite_tags(cases),
        metadata={
            "dataset_path": str(source),
            "case_limits": _limits_metadata(limits),
            "evaluated_model": evaluated_model,
        },
    )


@task
def coding_suite(
    dataset: str = str(DEFAULT_CODING_DATASET),
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
) -> Task:
    source, cases, version = load_case_suite(dataset, "coding")
    _reject_draft_cases(cases)
    limits = _uniform_limits(cases, source)
    return _coding_task(
        source,
        cases,
        version,
        limits,
        direct_provider=direct_provider,
        direct_model=direct_model,
        direct_auth_file=direct_auth_file,
        thinking_level=thinking_level,
    )


def coding_tasks(
    dataset: str = str(DEFAULT_CODING_DATASET),
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
) -> list[Task]:
    """Build exact-limit tasks, splitting a mixed-limit coding dataset."""
    source, cases, version = load_case_suite(dataset, "coding")
    _reject_draft_cases(cases)
    return [
        _coding_task(
            source,
            group,
            version,
            limits,
            direct_provider=direct_provider,
            direct_model=direct_model,
            direct_auth_file=direct_auth_file,
            thinking_level=thinking_level,
            name=_task_group_name("coding", limits),
        )
        for limits, group in _limit_groups(cases)
    ]


def _coding_task(
    source: Path,
    cases: list[GoldenCase],
    version: str,
    limits: tuple[int, int, int],
    *,
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
    name: str | None = None,
) -> Task:
    seconds, turns, total_tokens = limits
    score_components = sorted(
        {
            component
            for case in cases
            for component in _declared_score_components(case)
        }
    )
    return Task(
        dataset=[_coding_sample(case, source) for case in cases],
        solver=[
            configure_pi_case(),
            pi_agent(
                phase="coding",
                direct_provider=direct_provider,
                direct_model=direct_model,
                direct_auth_file=direct_auth_file,
                thinking_level=thinking_level,
            ),
        ],
        scorer=coding_verifier_scorer(score_components),
        sandbox=("docker", str(COMPOSE_FILE)),
        time_limit=seconds,
        turn_limit=turns,
        token_limit=total_tokens,
        name=name,
        version=version,
        tags=_suite_tags(cases),
        metadata={
            "dataset_path": str(source),
            "case_limits": _limits_metadata(limits),
        },
    )


def planning_smoke(grader_model: str | None = None) -> Task:
    """Compatibility wrapper for the original public planning task name."""
    return planning_suite(grader_model=grader_model)


def coding_smoke() -> Task:
    """Compatibility wrapper for the original public coding task name."""
    return coding_suite()


def load_case_suite(
    dataset: str | Path,
    phase: Literal["planning", "coding"],
) -> tuple[Path, list[GoldenCase], str]:
    """Load a phase-homogeneous suite and validate its local assets."""
    source = Path(dataset).expanduser()
    if not source.is_absolute():
        source = REPOSITORY_ROOT / source
    source = source.resolve()
    cases = load_cases(source)
    wrong_phase = [case.id for case in cases if case.phase != phase]
    if wrong_phase:
        raise ValueError(
            f"{source}: expected only {phase} cases; wrong phase: "
            + ", ".join(wrong_phase)
        )
    versions = {
        str(case.metadata.get("dataset_version", "")).strip() for case in cases
    }
    if "" in versions or len(versions) != 1:
        raise ValueError(
            f"{source}: every case must use one non-empty metadata.dataset_version"
        )
    if phase == "coding":
        for case in cases:
            _coding_assets(case, source)
            declared = set(_declared_score_components(case))
            unknown_required = set(case.expected.required_components) - declared
            if unknown_required:
                raise ValueError(
                    f"{case.id}: expected.required_components are not declared in "
                    "metadata.score_components: "
                    + ", ".join(sorted(unknown_required))
                )
    else:
        for case in cases:
            if case.metadata.get("fixture"):
                _repository_fixture(case, source)
    return source, cases, versions.pop()


def _planning_sample(
    case: GoldenCase,
    source: Path,
    evaluated_model: str | None = None,
) -> Sample:
    fixture_value = case.metadata.get("fixture")
    files = None
    setup = None
    if fixture_value:
        fixture = _repository_fixture(case, source)
        files = {"/workspace": str(fixture)}
        setup = _workspace_setup()
    return Sample(
        id=case.id,
        input=case.instruction,
        metadata={
            **_case_metadata(case),
            "evaluated_model": evaluated_model,
        },
        files=files,
        setup=setup,
    )


def _coding_sample(case: GoldenCase, source: Path) -> Sample:
    fixture, _ = _coding_assets(case, source)
    return Sample(
        id=case.id,
        input=case.instruction,
        metadata=_case_metadata(case),
        files={"/workspace": str(fixture)},
        setup=_workspace_setup(),
    )


def _coding_assets(case: GoldenCase, source: Path) -> tuple[Path, Path]:
    fixture = _repository_fixture(case, source)

    expected_verifier = f"/opt/verifiers/{case.id}/verify.py"
    if expected_verifier not in case.expected.verifier_command:
        raise ValueError(
            f"{case.id}: verifier_command must reference {expected_verifier}"
        )
    verifier = REPOSITORY_ROOT / "verifiers" / case.id / "verify.py"
    if not verifier.is_file():
        raise ValueError(f"{case.id}: verifier source does not exist: {verifier}")
    return fixture, verifier.resolve()


def _repository_fixture(case: GoldenCase, source: Path) -> Path:
    fixture_value = case.metadata.get("fixture")
    if not isinstance(fixture_value, str) or not fixture_value:
        raise ValueError(f"{case.id}: metadata.fixture must be a path")
    fixture = _resolve_asset(fixture_value, source)
    if not fixture.is_dir():
        raise ValueError(f"{case.id}: fixture directory does not exist: {fixture}")
    if (fixture / ".git").exists():
        _validate_git_fixture(case, fixture)
    return fixture


def _workspace_setup() -> str:
    return (
        "cd /workspace\n"
        "if [ -e .git ]; then\n"
        "  git reset --hard -q HEAD\n"
        "  git clean -ffdqx\n"
        "else\n"
        "  git init -q\n"
        "  git config user.name 'Agent Eval Baseline'\n"
        "  git config user.email 'eval@example.invalid'\n"
        "  git add .\n"
        "  git commit -qm baseline\n"
        "fi\n"
    )


def _validate_git_fixture(case: GoldenCase, fixture: Path) -> None:
    source_commit = case.metadata.get("source_commit")
    if not isinstance(source_commit, str) or not source_commit:
        raise ValueError(
            f"{case.id}: cloned repository fixtures require metadata.source_commit"
        )
    head = subprocess.run(
        ["git", "-C", str(fixture), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != source_commit:
        raise ValueError(
            f"{case.id}: fixture HEAD {head} does not match source_commit "
            f"{source_commit}"
        )
    status = subprocess.run(
        ["git", "-C", str(fixture), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise ValueError(f"{case.id}: cloned repository fixture must be clean")


def _resolve_asset(value: str, dataset: Path) -> Path:
    requested = Path(value).expanduser()
    candidates = (
        [requested]
        if requested.is_absolute()
        else [dataset.parent / requested, REPOSITORY_ROOT / requested]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[-1].resolve()


def _suite_tags(cases: list[GoldenCase]) -> list[str]:
    return sorted({tag for case in cases for tag in case.tags})


def _limit_groups(
    cases: list[GoldenCase],
) -> list[tuple[tuple[int, int, int], list[GoldenCase]]]:
    groups: dict[tuple[int, int, int], list[GoldenCase]] = defaultdict(list)
    for case in cases:
        groups[_case_limits(case)].append(case)
    return sorted(groups.items())


def _uniform_limits(cases: list[GoldenCase], source: Path) -> tuple[int, int, int]:
    groups = _limit_groups(cases)
    if len(groups) != 1:
        raise ValueError(
            f"{source}: cases have different execution limits; use "
            "planning_tasks() or coding_tasks() so Inspect can enforce each group exactly"
        )
    return groups[0][0]


def _case_limits(case: GoldenCase) -> tuple[int, int, int]:
    return (
        case.limits.seconds,
        case.limits.turns,
        case.limits.total_tokens,
    )


def _task_group_name(phase: str, limits: tuple[int, int, int]) -> str:
    seconds, turns, total_tokens = limits
    return f"{phase}_suite_{seconds}s_{turns}turns_{total_tokens}tokens"


def _limits_metadata(limits: tuple[int, int, int]) -> dict[str, int]:
    seconds, turns, total_tokens = limits
    return {
        "seconds": seconds,
        "turns": turns,
        "total_tokens": total_tokens,
    }


def _declared_score_components(case: GoldenCase) -> tuple[str, ...]:
    value = case.metadata.get("score_components", [])
    if not isinstance(value, list) or not all(
        isinstance(component, str) and component for component in value
    ):
        raise ValueError(f"{case.id}: metadata.score_components must be string list")
    if len(value) != len(set(value)):
        raise ValueError(
            f"{case.id}: metadata.score_components must contain unique names"
        )
    return tuple(value)


def _reject_draft_cases(cases: list[GoldenCase]) -> None:
    drafts = [case.id for case in cases if case.metadata.get("draft") is not False]
    if drafts:
        raise ValueError(
            "refusing to run draft case(s): "
            + ", ".join(drafts)
            + "; finish the evidence contract and set metadata.draft to false"
        )


def _case_metadata(case: GoldenCase) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "phase": case.phase,
        "dataset_version": case.metadata.get("dataset_version"),
        "limits": {
            "seconds": case.limits.seconds,
            "turns": case.limits.turns,
            "context_tokens": case.limits.context_tokens,
            "total_tokens": case.limits.total_tokens,
        },
        "expected": {
            "required_concepts": list(case.expected.required_concepts),
            "forbidden_concepts": list(case.expected.forbidden_concepts),
            "verifier_command": list(case.expected.verifier_command),
            "rubric": [
                {
                    "id": criterion.id,
                    "description": criterion.description,
                    "weight": criterion.weight,
                }
                for criterion in case.expected.rubric
            ],
            "success_threshold": case.expected.success_threshold,
            "required_components": list(case.expected.required_components),
        },
        **case.metadata,
    }
