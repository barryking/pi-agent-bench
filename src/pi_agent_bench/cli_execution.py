"""Model checks and Inspect evaluation command execution."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .model_profiles import load_env_file, load_profiles, profile_environment


def _resolve_profile(args: argparse.Namespace):
    if args.env_file:
        load_env_file(args.env_file)
    profiles = load_profiles(args.profiles)
    try:
        profile = profiles[args.profile]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise SystemExit(f"unknown profile {args.profile!r}; available: {available}") from exc
    return profile


def _doctor(profile) -> list[str]:
    failures: list[str] = profile.readiness_errors()
    if shutil.which("docker") is None:
        failures.append("Docker is missing; install Docker Desktop and start it.")
    else:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            failures.append("Docker is installed but its daemon is not available.")
    if shutil.which("git") is None:
        failures.append("Git is missing; run `xcode-select --install`.")
    try:
        resolved = profile.resolved_runtime_env(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
        resolved = {}
    try:
        pi_auth_file = profile.resolved_pi_auth_file(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
        pi_auth_file = None
    if profile.pi_direct and pi_auth_file is not None:
        if not pi_auth_file.is_file():
            failures.append(
                f"{profile.name}: Pi auth file does not exist: {pi_auth_file}"
            )
        else:
            try:
                auth = json.loads(pi_auth_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                failures.append(f"{profile.name}: Pi auth file is not valid JSON")
            else:
                provider = profile.pi_direct["provider"]
                if provider not in auth:
                    failures.append(
                        f"{profile.name}: Pi auth file has no {provider} login"
                    )
    if profile.kind == "local" and resolved.get("OPENAI_BASE_URL"):
        models_url = f"{resolved['OPENAI_BASE_URL'].rstrip('/')}/models"
        request = urllib.request.Request(models_url)
        api_key = resolved.get("OPENAI_API_KEY")
        if api_key:
            request.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 400:
                    failures.append(
                        f"Local model endpoint returned HTTP {response.status}."
                    )
        except (urllib.error.URLError, TimeoutError) as exc:
            failures.append(
                f"Local model endpoint is unreachable at {models_url}: {exc}"
            )
    return failures


def _run(args: argparse.Namespace) -> None:
    _validate_run_args(args)
    profile = _resolve_profile(args)
    grader_model = _resolve_grader_model(args)
    grader_identity = (
        args.grader_profile
        and _profile_by_name(args.profiles, args.grader_profile).model
    ) or args.grader_model
    if grader_identity == profile.model:
        raise SystemExit("the evaluated model cannot be its own planning grader")
    failures = _doctor(profile)
    if failures:
        raise SystemExit("\n".join(failures))
    if args.build:
        subprocess.run(
            ["docker", "compose", "-f", "docker/compose.yaml", "build"],
            check=True,
        )

    from inspect_ai import Epochs, eval_set
    from inspect_ai import eval as inspect_eval
    from inspect_ai.scorer import mean_score, pass_at, pass_k

    from .inspect_tasks import coding_tasks, planning_tasks
    from .run_records import write_run_records

    direct = profile.pi_direct or {}
    direct_auth_file = profile.resolved_pi_auth_file(os.environ)
    thinking_level = profile.configuration.get("thinking_level")
    if thinking_level is not None and not isinstance(thinking_level, str):
        raise SystemExit(f"{profile.name}: configuration.thinking_level must be a string")

    tasks = []
    if args.phase in {"planning", "all"}:
        planning_dataset = (
            args.dataset if args.phase == "planning" and args.dataset else args.planning_dataset
        )
        tasks.extend(
            planning_tasks(
                dataset=str(planning_dataset),
                grader_model=grader_model,
                evaluated_model=profile.model,
                direct_provider=direct.get("provider"),
                direct_model=direct.get("model"),
                direct_auth_file=str(direct_auth_file) if direct_auth_file else None,
                thinking_level=thinking_level,
            )
        )
    if args.phase in {"coding", "all"}:
        coding_dataset = (
            args.dataset if args.phase == "coding" and args.dataset else args.coding_dataset
        )
        tasks.extend(
            coding_tasks(
                dataset=str(coding_dataset),
                direct_provider=direct.get("provider"),
                direct_model=direct.get("model"),
                direct_auth_file=str(direct_auth_file) if direct_auth_file else None,
                thinking_level=thinking_level,
            )
        )
    profile_logs_dir = (
        args.logs_dir / _eval_set_id(args.campaign, profile.name)
        if args.resume
        else args.logs_dir
    )
    profile_logs_dir.mkdir(parents=True, exist_ok=True)
    reducers = [mean_score()]
    if args.epochs > 1:
        reducers.extend(
            [
                pass_at(args.epochs),
                pass_k(args.epochs),
            ]
        )
    epochs = Epochs(args.epochs, reducers)
    eval_metadata = {
        "pi_agent_bench": {
            "profile": profile.public_identity(),
            "campaign": args.campaign,
            "cache_state": args.cache_state,
        }
    }
    with profile_environment(profile):
        eval_args = {
            "model": "mockllm/model" if profile.pi_direct else profile.model,
            "epochs": epochs,
            "log_model_api": True,
            "cost_limit": args.cost_limit,
            "metadata": eval_metadata,
        }
        if args.resume:
            complete, logs = eval_set(
                tasks,
                log_dir=str(profile_logs_dir),
                retry_attempts=args.retry_attempts,
                eval_set_id=_eval_set_id(args.campaign, profile.name),
                **eval_args,
            )
            logs = _load_full_logs(logs)
        else:
            logs = inspect_eval(
                tasks,
                log_dir=str(profile_logs_dir),
                **eval_args,
            )
            complete = all(str(log.status) == "success" for log in logs)
    paths = write_run_records(
        logs,
        args.results_dir,
        profile,
        campaign=args.campaign,
        cache_state=args.cache_state,
    )
    for path in paths:
        print(f"result: {path}")
    if not complete:
        raise SystemExit(
            "one or more Inspect tasks were incomplete; details were written "
            f"under {args.results_dir / '_invalid'}"
        )


def _validate_run_args(args: argparse.Namespace) -> None:
    if args.epochs < 1:
        raise SystemExit("--epochs must be a positive integer")
    if args.phase == "all" and args.dataset:
        raise SystemExit(
            "--dataset is only valid for planning or coding; use "
            "--planning-dataset and --coding-dataset with phase=all"
        )
    if args.grader_model and args.grader_profile:
        raise SystemExit("--grader-model and --grader-profile are mutually exclusive")
    if args.cost_limit is not None and args.cost_limit <= 0:
        raise SystemExit("--cost-limit must be positive")
    if args.retry_attempts < 1:
        raise SystemExit("--retry-attempts must be a positive integer")


def _resolve_grader_model(args: argparse.Namespace):
    if args.grader_profile:
        profile = _profile_by_name(args.profiles, args.grader_profile)
        errors = profile.readiness_errors()
        if errors:
            raise SystemExit("\n".join(errors))
        from inspect_ai.model import get_model

        try:
            with profile_environment(profile):
                return get_model(profile.model)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    return args.grader_model


def _profile_by_name(path: Path, name: str):
    profiles = load_profiles(path)
    try:
        return profiles[name]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise SystemExit(
            f"unknown grader profile {name!r}; available: {available}"
        ) from exc


def _eval_set_id(campaign: str, profile: str) -> str:
    value = f"{campaign}-{profile}"
    return "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value
    )


def _load_full_logs(logs):
    """Materialize samples when Inspect eval sets return header-only logs."""
    from inspect_ai.log import read_eval_log

    return [
        log if log.samples is not None else read_eval_log(log.location)
        for log in logs
    ]


def _campaign(args: argparse.Namespace) -> None:
    profiles = list(dict.fromkeys(args.run_profile))
    print(
        f"campaign {args.campaign}: {len(profiles)} profile(s), "
        f"phase={args.phase}, epochs={args.epochs}"
    )
    for index, profile_name in enumerate(profiles, start=1):
        print(f"\n[{index}/{len(profiles)}] profile={profile_name}")
        values = vars(args).copy()
        values.update(
            {
                "command": "run",
                "profile": profile_name,
                "build": bool(args.build and index == 1),
            }
        )
        _run(argparse.Namespace(**values))

    from .reporting import build_report, write_report, write_visualizer_exports

    output = args.results_dir / "summary.md"
    markdown, summary = write_report(build_report(args.results_dir), output)
    runs, metrics = write_visualizer_exports(args.results_dir)
    print(f"\nreport: {markdown}")
    print(f"summary: {summary}")
    print(f"runs: {runs}")
    print(f"metrics: {metrics}")
    print(f"dashboard: pi-bench view --results-dir {args.results_dir}")
    print(
        "dashboard + trajectories: "
        f"pi-bench view --results-dir {args.results_dir} "
        f"--logs-dir {args.logs_dir} --inspect"
    )


def _rescore_planning(args: argparse.Namespace) -> None:
    if args.env_file:
        load_env_file(args.env_file)
    source = args.log_file.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Inspect log does not exist: {source}")
    if args.overwrite and args.output_log:
        raise SystemExit("--overwrite and --output-log cannot be used together")

    from inspect_ai import score as inspect_score
    from inspect_ai.log import read_eval_log, write_eval_log

    from .inspect_scorers import planning_rubric_scorer

    log = read_eval_log(source)
    if str(log.status) != "success":
        raise SystemExit(
            f"cannot re-score an incomplete Inspect log with status {log.status}"
        )
    samples = log.samples or []
    if not samples or any(sample.metadata.get("phase") != "planning" for sample in samples):
        raise SystemExit("rescore-planning requires a completed planning log")
    component_names = sorted(
        {
            str(criterion["id"])
            for sample in samples
            for criterion in sample.metadata.get("expected", {}).get("rubric", [])
            if isinstance(criterion, dict) and criterion.get("id")
        }
    )
    grader_model = _resolve_grader_model(args)
    rescored = inspect_score(
        log,
        planning_rubric_scorer(component_names),
        model_roles={"grader": grader_model},
        action="overwrite",
    )
    output = (
        source
        if args.overwrite
        else (
            args.output_log.expanduser().resolve()
            if args.output_log
            else source.with_name(f"{source.stem}.rescored{source.suffix}")
        )
    )
    write_eval_log(rescored, output)
    print(f"rescored log: {output}")
