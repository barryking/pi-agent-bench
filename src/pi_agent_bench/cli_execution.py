"""Model checks and Inspect evaluation command execution."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request

from .agent_profiles import load_agent_profiles
from .model_profiles import load_env_file, load_profiles, profile_environment


def _resolve_model_profile(args: argparse.Namespace):
    if args.env_file:
        load_env_file(args.env_file)
    profiles = load_profiles(args.model_profiles_file)
    try:
        profile = profiles[args.model_profile]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise SystemExit(
            f"unknown model profile {args.model_profile!r}; available: {available}"
        ) from exc
    return profile


def _resolve_agent_profile(args: argparse.Namespace):
    profiles = load_agent_profiles(args.agent_profiles_file)
    try:
        return profiles[args.agent_profile]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise SystemExit(
            f"unknown agent profile {args.agent_profile!r}; available: {available}"
        ) from exc


def _doctor(profile, agent_profile=None) -> list[str]:
    failures: list[str] = profile.readiness_errors()
    if agent_profile is not None:
        failures.extend(agent_profile.readiness_errors())
        try:
            agent_profile.resolved_runtime_env(os.environ)
        except ValueError as exc:
            failures.append(str(exc))
    failures.extend(_host_readiness_errors())
    resolved = _resolved_profile_environment(profile, failures)
    failures.extend(_pi_auth_errors(profile))
    failures.extend(_local_endpoint_errors(profile, resolved))
    return failures


def _host_readiness_errors() -> list[str]:
    failures: list[str] = []
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
    return failures


def _resolved_profile_environment(profile, failures: list[str]) -> dict[str, str]:
    try:
        return profile.resolved_runtime_env(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
        return {}


def _pi_auth_errors(profile) -> list[str]:
    failures: list[str] = []
    try:
        pi_auth_file = profile.resolved_pi_auth_file(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
        pi_auth_file = None
    if profile.pi_direct and pi_auth_file is not None:
        if not pi_auth_file.is_file():
            failures.append(f"{profile.name}: Pi auth file does not exist: {pi_auth_file}")
        else:
            try:
                auth = json.loads(pi_auth_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                failures.append(f"{profile.name}: Pi auth file is not valid JSON")
            else:
                provider = profile.pi_direct["provider"]
                if provider not in auth:
                    failures.append(f"{profile.name}: Pi auth file has no {provider} login")
    return failures


def _local_endpoint_errors(profile, resolved: dict[str, str]) -> list[str]:
    failures: list[str] = []
    if profile.kind == "local" and resolved.get("OPENAI_BASE_URL"):
        models_url = f"{resolved['OPENAI_BASE_URL'].rstrip('/')}/models"
        request = urllib.request.Request(models_url)
        api_key = resolved.get("OPENAI_API_KEY")
        if api_key:
            request.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 400:
                    failures.append(f"Local model endpoint returned HTTP {response.status}.")
        except (urllib.error.URLError, TimeoutError) as exc:
            failures.append(f"Local model endpoint is unreachable at {models_url}: {exc}")
    return failures


def _run(args: argparse.Namespace) -> None:
    _validate_run_args(args)
    profile = _resolve_model_profile(args)
    agent_profile = _resolve_agent_profile(args)
    failures = _doctor(profile, agent_profile)
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

    from .inspect_tasks import outcome_tasks
    from .run_records import write_run_records

    direct = profile.pi_direct or {}
    direct_auth_file = profile.resolved_pi_auth_file(os.environ)
    agent_runtime_env = agent_profile.resolved_runtime_env(os.environ)
    thinking_level = profile.configuration.get("thinking_level")
    if thinking_level is not None and not isinstance(thinking_level, str):
        raise SystemExit(f"{profile.name}: configuration.thinking_level must be a string")
    allowed_thinking = {
        "none",
        "off",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    }
    if thinking_level is not None and thinking_level not in allowed_thinking:
        raise SystemExit(
            f"{profile.name}: configuration.thinking_level must be one of "
            + ", ".join(sorted(allowed_thinking))
        )

    pi_thinking_level = "off" if thinking_level == "none" else thinking_level
    tasks = outcome_tasks(
        dataset=str(args.dataset),
        direct_provider=direct.get("provider"),
        direct_model=direct.get("model"),
        direct_auth_file=str(direct_auth_file) if direct_auth_file else None,
        thinking_level=pi_thinking_level,
        agent_profile=agent_profile,
        agent_runtime_env=agent_runtime_env,
    )
    profile_logs_dir = (
        args.logs_dir
        / _eval_set_id(
            args.campaign,
            profile.name,
            agent_profile.name,
        )
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
            "agent_profile": agent_profile.public_identity(),
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
        if thinking_level is not None and not profile.pi_direct:
            eval_args["reasoning_effort"] = "none" if thinking_level == "off" else thinking_level
        if args.resume:
            complete, logs = eval_set(
                tasks,
                log_dir=str(profile_logs_dir),
                retry_attempts=args.retry_attempts,
                eval_set_id=_eval_set_id(
                    args.campaign,
                    profile.name,
                    agent_profile.name,
                ),
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
        agent_profile=agent_profile,
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
    if args.cost_limit is not None and args.cost_limit <= 0:
        raise SystemExit("--cost-limit must be positive")
    if args.retry_attempts < 1:
        raise SystemExit("--retry-attempts must be a positive integer")


def _eval_set_id(campaign: str, profile: str, agent_profile: str = "vanilla") -> str:
    parts = [campaign, profile]
    if agent_profile != "vanilla":
        parts.append(agent_profile)
    value = "-".join(parts)
    return "".join(
        character if character.isalnum() or character in "-_" else "-" for character in value
    )


def _load_full_logs(logs):
    """Materialize samples when Inspect eval sets return header-only logs."""
    from inspect_ai.log import read_eval_log

    return [log if log.samples is not None else read_eval_log(log.location) for log in logs]


def _campaign(args: argparse.Namespace) -> None:
    profiles = list(dict.fromkeys(args.model_profile))
    agent_profiles = list(dict.fromkeys(args.agent_profile or ["vanilla"]))
    combinations = [
        (profile, agent_profile) for profile in profiles for agent_profile in agent_profiles
    ]
    print(
        f"campaign {args.campaign}: {len(combinations)} model/agent combination(s), "
        f"outcome suite, epochs={args.epochs}"
    )
    for index, (profile_name, agent_profile_name) in enumerate(
        combinations,
        start=1,
    ):
        print(
            f"\n[{index}/{len(combinations)}] model-profile={profile_name}; "
            f"agent-profile={agent_profile_name}"
        )
        values = vars(args).copy()
        values.update(
            {
                "command": "run",
                "model_profile": profile_name,
                "agent_profile": agent_profile_name,
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
