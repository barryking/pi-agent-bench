"""Agent-profile checks and Inspect evaluation command execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .agent_profiles import AgentProfile, load_agent_profiles
from .harness_identity import (
    build_sandbox,
    capture_harness_identity,
    cohort_identity,
    sandbox_identity,
)
from .model_profiles import load_env_file, load_profiles
from .pi_profiles import load_pi_profiles


def _resolve_agent_profile(args: argparse.Namespace) -> AgentProfile:
    if args.env_file:
        load_env_file(args.env_file)
    model_profiles = load_profiles(args.model_profiles_file)
    pi_profiles = load_pi_profiles(args.pi_profiles_file)
    profiles = load_agent_profiles(
        args.agent_profiles_file,
        pi_profiles=pi_profiles,
        model_profiles=model_profiles,
    )
    try:
        return profiles[args.agent_profile]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise SystemExit(
            f"unknown agent profile {args.agent_profile!r}; available: {available}"
        ) from exc


def _doctor(profile: AgentProfile) -> list[str]:
    failures = profile.readiness_errors()
    try:
        profile.pi_profile.resolved_runtime_env(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
    failures.extend(_host_readiness_errors())
    for resource in profile.model_resources:
        resolved = _resolved_model_arguments(resource, failures)
        failures.extend(_pi_auth_errors(resource))
        failures.extend(_local_endpoint_errors(resource, resolved))
    if not failures:
        try:
            sandbox_identity()
        except ValueError as exc:
            failures.append(str(exc))
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


def _resolved_model_arguments(resource, failures: list[str]) -> dict[str, object]:
    try:
        return resource.resolved_model_args(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
        return {}


def _pi_auth_errors(resource) -> list[str]:
    if resource.execution_mode != "pi-direct":
        return []
    failures: list[str] = []
    try:
        pi_auth_file = resource.resolved_pi_auth_file(os.environ)
    except ValueError as exc:
        failures.append(str(exc))
        return failures
    assert pi_auth_file is not None
    if not pi_auth_file.is_file():
        failures.append(f"{resource.name}: Pi auth file does not exist: {pi_auth_file}")
        return failures
    try:
        auth = json.loads(pi_auth_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        failures.append(f"{resource.name}: Pi auth file is not valid JSON")
        return failures
    provider = resource.direct_provider
    if provider not in auth:
        failures.append(f"{resource.name}: Pi auth file has no {provider} login")
    return failures


def _local_endpoint_errors(resource, resolved: dict[str, object]) -> list[str]:
    if resource.kind != "local" or resource.execution_mode != "inspect-bridge":
        return []
    base_url = resolved.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        if resource.model.startswith("ollama/"):
            base_url = "http://localhost:11434/v1"
        else:
            return [
                f"{resource.name}: local bridged resources require a base_url "
                "so the configured model can be verified"
            ]
    models_url = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(models_url)
    api_key = resolved.get("api_key")
    if isinstance(api_key, str) and api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                return [f"{resource.name}: local endpoint returned HTTP {response.status}."]
            try:
                payload = json.load(response)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return [f"{resource.name}: local endpoint returned invalid /models JSON"]
    except urllib.error.HTTPError as exc:
        return [f"{resource.name}: local endpoint returned HTTP {exc.code}."]
    except (urllib.error.URLError, TimeoutError) as exc:
        return [f"{resource.name}: local endpoint is unreachable at {models_url}: {exc}"]
    advertised = _advertised_model_ids(payload)
    if advertised is None:
        return [f"{resource.name}: local endpoint returned an invalid /models response"]
    expected = _service_model_name(resource.model)
    if expected not in advertised:
        available = ", ".join(sorted(advertised)[:10]) or "none"
        suffix = " ..." if len(advertised) > 10 else ""
        return [
            f"{resource.name}: configured model {expected!r} is not advertised by "
            f"{models_url}; available: {available}{suffix}"
        ]
    return []


def _advertised_model_ids(payload: object) -> set[str] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return None
    identifiers: set[str] = set()
    for item in payload["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            return None
        identifier = item["id"].strip()
        if not identifier:
            return None
        identifiers.add(identifier)
    return identifiers


def _service_model_name(model: str) -> str:
    _, separator, service_name = model.partition("/")
    return service_name if separator else model


def _run(args: argparse.Namespace) -> None:
    _validate_run_args(args)
    profile = _resolve_agent_profile(args)
    if args.cost_limit is not None and profile.has_direct_resources:
        raise SystemExit(
            "--cost-limit is unavailable for agent profiles containing Pi-direct resources"
        )
    if args.build:
        host_failures = _host_readiness_errors()
        if host_failures:
            raise SystemExit("\n".join(host_failures))
        build_sandbox()
    failures = _doctor(profile)
    if failures:
        raise SystemExit("\n".join(failures))
    harness_identity = capture_harness_identity()
    benchmark_id = _benchmark_id(args)
    cohort = cohort_identity(
        args.dataset,
        cache_state=args.cache_state,
        cost_limit=args.cost_limit,
        harness=harness_identity,
    )
    print(f"benchmark-id: {benchmark_id}")

    from inspect_ai import Epochs, eval_set
    from inspect_ai import eval as inspect_eval
    from inspect_ai.scorer import mean_score, pass_at, pass_k

    from .inspect_tasks import outcome_tasks
    from .run_records import write_run_records

    bridged_models = {
        resource.name: resource.create_inspect_model(os.environ)
        for resource in profile.model_resources
        if resource.execution_mode == "inspect-bridge"
    }
    direct_auth_files = {
        resource.name: str(resource.resolved_pi_auth_file(os.environ))
        for resource in profile.model_resources
        if resource.execution_mode == "pi-direct"
    }
    agent_runtime_env = profile.pi_profile.resolved_runtime_env(os.environ)
    tasks = outcome_tasks(
        dataset=str(args.dataset),
        agent_profile=profile,
        bridged_models=bridged_models,
        direct_auth_files=direct_auth_files,
        agent_runtime_env=agent_runtime_env,
    )
    profile_logs_dir = (
        args.logs_dir / _eval_set_id(args.run_name, profile.name, benchmark_id)
        if args.resume
        else args.logs_dir
    )
    profile_logs_dir.mkdir(parents=True, exist_ok=True)
    reducers = [mean_score()]
    if args.epochs > 1:
        reducers.extend([pass_at(args.epochs), pass_k(args.epochs)])
    epochs = Epochs(args.epochs, reducers)
    eval_metadata = {
        "pi_agent_bench": {
            "agent_profile": profile.public_identity(),
            "benchmark_id": benchmark_id,
            "run_name": args.run_name,
            "cache_state": args.cache_state,
            "harness": harness_identity,
            "cohort": cohort,
            "epochs": args.epochs,
            "campaign": {
                "benchmark_id": benchmark_id,
                "planned_trial_count": args.epochs,
                "resume": args.resume,
                "retry_attempts": args.retry_attempts,
            },
        }
    }
    eval_args = {
        "model": "mockllm/model",
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
            eval_set_id=_eval_set_id(args.run_name, profile.name, benchmark_id),
            **eval_args,
        )
        logs = _load_full_logs(logs)
    else:
        logs = inspect_eval(tasks, log_dir=str(profile_logs_dir), **eval_args)
        complete = all(str(log.status) == "success" for log in logs)
    paths = write_run_records(
        logs,
        args.results_dir,
        profile,
        benchmark_id=benchmark_id,
        run_name=args.run_name,
        cache_state=args.cache_state,
        harness_identity=harness_identity,
        cohort_identity=cohort,
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


def _benchmark_id(args: argparse.Namespace) -> str:
    supplied = getattr(args, "benchmark_id", None)
    if supplied is not None:
        if not isinstance(supplied, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*", supplied
        ):
            raise SystemExit(
                "--benchmark-id must start with a letter or number and use only "
                "letters, numbers, dots, underscores, or hyphens"
            )
        return supplied
    if getattr(args, "resume", False):
        resume_key = (
            f"{Path(args.logs_dir).expanduser().resolve()}::{args.run_name}".encode()
        )
        return "resume-" + hashlib.sha256(resume_key).hexdigest()[:24]
    return uuid.uuid4().hex


def _eval_set_id(
    run_name: str,
    agent_profile: str,
    benchmark_id: str | None = None,
) -> str:
    value = "-".join(
        item for item in (run_name, agent_profile, benchmark_id) if item
    )
    return "".join(
        character if character.isalnum() or character in "-_" else "-" for character in value
    )


def _load_full_logs(logs):
    """Materialize samples when Inspect eval sets return header-only logs."""
    from inspect_ai.log import read_eval_log

    return [log if log.samples is not None else read_eval_log(log.location) for log in logs]


def _benchmark(args: argparse.Namespace) -> None:
    profiles = list(dict.fromkeys(args.agent_profile))
    benchmark_id = _benchmark_id(args)
    print(
        f"benchmark run {args.run_name} ({benchmark_id}): "
        f"{len(profiles)} agent profile(s), "
        f"outcome suite, epochs={args.epochs}"
    )
    for index, profile_name in enumerate(profiles, start=1):
        print(f"\n[{index}/{len(profiles)}] agent-profile={profile_name}")
        values = vars(args).copy()
        values.update(
            {
                "command": "run",
                "agent_profile": profile_name,
                "benchmark_id": benchmark_id,
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
