"""Inspect tasks for complete repository outcomes."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from pi_agent_bench.agent_profiles import AgentProfile, vanilla_agent_profile
from pi_agent_bench.dataset import GoldenCase, load_cases
from pi_agent_bench.inspect_agent import configure_pi_case, pi_agent
from pi_agent_bench.inspect_scorers import outcome_verifier_scorer

from .repository import REPOSITORY_ROOT

COMPOSE_FILE = REPOSITORY_ROOT / "docker" / "compose.yaml"
DEFAULT_DATASET = REPOSITORY_ROOT / "evals" / "sample" / "cases.jsonl"


@task
def outcome_suite(
    dataset: str = str(DEFAULT_DATASET),
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
    agent_profile: AgentProfile | None = None,
    agent_runtime_env: dict[str, str] | None = None,
) -> Task:
    source, cases, version = load_case_suite(dataset)
    _reject_draft_cases(cases)
    limits = _uniform_limits(cases, source)
    return _outcome_task(
        source,
        cases,
        version,
        limits,
        direct_provider=direct_provider,
        direct_model=direct_model,
        direct_auth_file=direct_auth_file,
        thinking_level=thinking_level,
        agent_profile=agent_profile,
        agent_runtime_env=agent_runtime_env,
    )


def outcome_tasks(
    dataset: str = str(DEFAULT_DATASET),
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
    agent_profile: AgentProfile | None = None,
    agent_runtime_env: dict[str, str] | None = None,
) -> list[Task]:
    """Build exact-limit tasks, splitting a mixed-limit outcome dataset."""
    source, cases, version = load_case_suite(dataset)
    _reject_draft_cases(cases)
    return [
        _outcome_task(
            source,
            group,
            version,
            limits,
            direct_provider=direct_provider,
            direct_model=direct_model,
            direct_auth_file=direct_auth_file,
            thinking_level=thinking_level,
            agent_profile=agent_profile,
            agent_runtime_env=agent_runtime_env,
            name=_task_group_name(limits),
        )
        for limits, group in _limit_groups(cases)
    ]


def _outcome_task(
    source: Path,
    cases: list[GoldenCase],
    version: str,
    limits: tuple[int, int, int],
    *,
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
    agent_profile: AgentProfile | None = None,
    agent_runtime_env: dict[str, str] | None = None,
    name: str | None = None,
) -> Task:
    selected_agent = agent_profile or vanilla_agent_profile()
    seconds, turns, total_tokens = limits
    score_components = sorted(
        {component for case in cases for component in _declared_score_components(case)}
    )
    return Task(
        dataset=[_outcome_sample(case, source) for case in cases],
        solver=[
            configure_pi_case(),
            pi_agent(
                direct_provider=direct_provider,
                direct_model=direct_model,
                direct_auth_file=direct_auth_file,
                thinking_level=thinking_level,
                agent_profile=selected_agent,
                agent_runtime_env=agent_runtime_env,
            ),
        ],
        scorer=outcome_verifier_scorer(score_components),
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
            "agent_profile": selected_agent.public_identity(),
        },
    )


def load_case_suite(
    dataset: str | Path,
) -> tuple[Path, list[GoldenCase], str]:
    """Load one outcome suite and validate its starting repositories and verifiers."""
    source = Path(dataset).expanduser()
    if not source.is_absolute():
        source = REPOSITORY_ROOT / source
    source = source.resolve()
    cases = load_cases(source)
    versions = {str(case.metadata.get("dataset_version", "")).strip() for case in cases}
    if "" in versions or len(versions) != 1:
        raise ValueError(f"{source}: every case must use one non-empty metadata.dataset_version")
    for case in cases:
        _outcome_assets(case, source)
        declared = set(_declared_score_components(case))
        unknown_required = set(case.expected.required_components) - declared
        if unknown_required:
            raise ValueError(
                f"{case.id}: expected.required_components are not declared in "
                "metadata.score_components: " + ", ".join(sorted(unknown_required))
            )
    return source, cases, versions.pop()


def _outcome_sample(case: GoldenCase, source: Path) -> Sample:
    starting_repository, _ = _outcome_assets(case, source)
    return Sample(
        id=case.id,
        input=case.instruction,
        metadata=_case_metadata(case),
        files={"/workspace": str(starting_repository)},
        setup=_workspace_setup(),
    )


def _outcome_assets(case: GoldenCase, source: Path) -> tuple[Path, Path]:
    starting_repository = _starting_repository(case, source)
    expected_verifier = f"/opt/verifiers/{case.id}/verify.py"
    if expected_verifier not in case.expected.verifier_command:
        raise ValueError(f"{case.id}: verifier_command must reference {expected_verifier}")
    verifier = REPOSITORY_ROOT / "verifiers" / case.id / "verify.py"
    if not verifier.is_file():
        raise ValueError(f"{case.id}: verifier source does not exist: {verifier}")
    return starting_repository, verifier.resolve()


def _starting_repository(case: GoldenCase, source: Path) -> Path:
    starting_repository_value = case.metadata.get("starting_repository")
    if not isinstance(starting_repository_value, str) or not starting_repository_value:
        raise ValueError(f"{case.id}: metadata.starting_repository must be a path")
    starting_repository = _resolve_asset(starting_repository_value, source)
    if not starting_repository.is_dir():
        raise ValueError(
            f"{case.id}: starting repository directory does not exist: "
            f"{starting_repository}"
        )
    if (starting_repository / ".git").exists():
        _validate_git_starting_repository(case, starting_repository)
    return starting_repository


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


def _validate_git_starting_repository(case: GoldenCase, starting_repository: Path) -> None:
    source_commit = case.metadata.get("source_commit")
    if not isinstance(source_commit, str) or not source_commit:
        raise ValueError(f"{case.id}: cloned starting repositories require metadata.source_commit")
    head = subprocess.run(
        ["git", "-C", str(starting_repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != source_commit:
        raise ValueError(
            f"{case.id}: starting repository HEAD {head} does not match "
            f"source_commit {source_commit}"
        )
    status = subprocess.run(
        ["git", "-C", str(starting_repository), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise ValueError(f"{case.id}: cloned starting repository must be clean")


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
            "outcome_tasks() so Inspect can enforce each group exactly"
        )
    return groups[0][0]


def _case_limits(case: GoldenCase) -> tuple[int, int, int]:
    return (case.limits.seconds, case.limits.turns, case.limits.total_tokens)


def _task_group_name(limits: tuple[int, int, int]) -> str:
    seconds, turns, total_tokens = limits
    return f"outcome_suite_{seconds}s_{turns}turns_{total_tokens}tokens"


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
        raise ValueError(f"{case.id}: metadata.score_components must contain unique names")
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
        "dataset_version": case.metadata.get("dataset_version"),
        "limits": {
            "seconds": case.limits.seconds,
            "turns": case.limits.turns,
            "context_tokens": case.limits.context_tokens,
            "total_tokens": case.limits.total_tokens,
        },
        "expected": {
            "verifier_command": list(case.expected.verifier_command),
            "success_threshold": case.expected.success_threshold,
            "required_components": list(case.expected.required_components),
        },
        **case.metadata,
    }
