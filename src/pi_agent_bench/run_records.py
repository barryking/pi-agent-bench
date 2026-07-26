"""Build small Pi Agent Bench records from Inspect logs."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .agent_profiles import AgentProfile, vanilla_agent_profile
from .model_profiles import ModelProfile
from .verification import finite_number, primary_score, quality_value
from .versions import FRAMEWORK_VERSION, INSPECT_VERSION, PI_VERSION, SANDBOX_IMAGE


def export_inspect_logs(
    logs_dir: str | Path,
    results_dir: str | Path,
) -> list[Path]:
    """Rebuild disposable dashboard records from canonical Inspect logs."""
    from inspect_ai.log import list_eval_logs, read_eval_log

    written: list[Path] = []
    for info in list_eval_logs(str(Path(logs_dir).expanduser().resolve())):
        log = read_eval_log(info.name)
        metadata = getattr(log.eval, "metadata", None) or {}
        benchmark = metadata.get("pi_agent_bench") or metadata.get("agent_evals")
        if not isinstance(benchmark, dict):
            warnings.warn(
                f"skipped Inspect log without Pi Agent Bench metadata: {info.name}",
                stacklevel=2,
            )
            continue
        profile = benchmark.get("profile")
        agent_profile = benchmark.get("agent_profile")
        try:
            written.extend(
                write_run_records(
                    [log],
                    results_dir,
                    profile,
                    agent_profile=agent_profile,
                    campaign=str(benchmark.get("campaign", "default")),
                    cache_state=str(benchmark.get("cache_state", "unspecified")),
                )
            )
        except ValueError as exc:
            warnings.warn(f"skipped {info.name}: {exc}", stacklevel=2)
    return written


def write_run_records(
    logs: Iterable[Any],
    results_dir: str | Path,
    profile: ModelProfile | dict[str, Any],
    *,
    agent_profile: AgentProfile | dict[str, Any] | None = None,
    campaign: str = "default",
    cache_state: str = "unspecified",
) -> list[Path]:
    destination = Path(results_dir)
    destination.mkdir(parents=True, exist_ok=True)
    repository = _repository_identity()
    profile_identity = _profile_identity(profile)
    agent_identity = _agent_profile_identity(agent_profile)
    written: list[Path] = []
    for log in logs:
        log_status = str(getattr(log, "status", "success"))
        if log_status != "success":
            invalid_path = _write_invalid_record(
                destination,
                log,
                profile,
                agent_profile=agent_identity,
                reason=f"Inspect log status is {log_status}",
                campaign=campaign,
                cache_state=cache_state,
            )
            warnings.warn(
                f"excluded incomplete Inspect log from rankings: {invalid_path}",
                stacklevel=2,
            )
            continue
        for sample in log.samples or []:
            if sample.error is not None:
                invalid_path = _write_invalid_record(
                    destination,
                    log,
                    profile,
                    agent_profile=agent_identity,
                    sample=sample,
                    reason="Inspect sample has an execution error",
                    campaign=campaign,
                    cache_state=cache_state,
                )
                warnings.warn(
                    f"excluded errored Inspect sample from rankings: {invalid_path}",
                    stacklevel=2,
                )
                continue
            scores = sample.scores or {}
            score_name, selected_score = primary_score(scores)
            if selected_score is None:
                invalid_path = _write_invalid_record(
                    destination,
                    log,
                    profile,
                    agent_profile=agent_identity,
                    sample=sample,
                    reason="Inspect sample has no score",
                    campaign=campaign,
                    cache_state=cache_state,
                )
                warnings.warn(
                    f"excluded unscored Inspect sample from rankings: {invalid_path}",
                    stacklevel=2,
                )
                continue
            score_metadata = dict(selected_score.metadata or {})
            artifact_stem = f"{log.eval.run_id}__{sample.id}__trial-{sample.epoch}"
            artifacts: dict[str, str] = {"inspect_log": str(log.location)}
            final_diff = score_metadata.pop("final_diff", "")
            if final_diff:
                diff_path = destination / f"{artifact_stem}.diff"
                diff_path.write_text(str(final_diff), encoding="utf-8")
                artifacts["final_diff"] = str(diff_path.resolve())

            score_value = quality_value(selected_score.value)
            if score_value is None:
                invalid_path = _write_invalid_record(
                    destination,
                    log,
                    profile,
                    agent_profile=agent_identity,
                    sample=sample,
                    reason="Inspect primary score has no finite quality value",
                    campaign=campaign,
                    cache_state=cache_state,
                )
                warnings.warn(
                    f"excluded invalid Inspect score from rankings: {invalid_path}",
                    stacklevel=2,
                )
                continue
            threshold = score_metadata.get("success_threshold", 1.0)
            score_components = _score_components(
                selected_score.value,
                score_metadata.get("components"),
            )
            timing = _inspect_timing(sample)
            record = {
                "schema_version": 3,
                "run_id": log.eval.run_id,
                "case_id": str(sample.id),
                "dataset_version": log.eval.task_version,
                "trial_number": sample.epoch,
                "campaign": campaign,
                "cache_state": cache_state,
                "model_configuration": profile_identity,
                "agent_configuration": agent_identity,
                "inspect_model": str(log.eval.model),
                "harness": {
                    "framework_version": FRAMEWORK_VERSION,
                    "pi_version_expected": PI_VERSION,
                    "pi_version_actual": score_metadata.get("pi_version"),
                    "inspect_version": INSPECT_VERSION,
                    "sandbox_image": SANDBOX_IMAGE,
                    **repository,
                },
                "started_at": sample.started_at,
                "wall_seconds": sample.total_time,
                "timing": timing,
                "validity": {
                    "valid": True,
                    "inspect_log_status": log_status,
                    "sample_error": None,
                },
                "success": _score_success(
                    selected_score.value,
                    score_value,
                    threshold,
                ),
                "score": {
                    "name": score_name,
                    "value": _json_value(score_value),
                    "fields": _json_value(selected_score.value),
                    "explanation": selected_score.explanation,
                    "components": score_components,
                    "method": score_metadata.get("scoring_method"),
                    "success_threshold": threshold,
                    "required_components": score_metadata.get(
                        "required_components",
                        [],
                    ),
                },
                "inspect_scores": {
                    name: {
                        "value": _json_value(score.value),
                        "explanation": score.explanation,
                    }
                    for name, score in scores.items()
                },
                "verifier": {
                    "return_code": score_metadata.get("verifier_return_code"),
                    "stdout": score_metadata.get("verifier_stdout"),
                    "stderr": score_metadata.get("verifier_stderr"),
                },
                "usage": _json_value(sample.model_usage or {}),
                "agent": {
                    **score_metadata.get("pi", {}),
                    "wall_seconds": score_metadata.get("pi_wall_seconds"),
                    "return_code": score_metadata.get("pi_return_code"),
                },
                "turn_count": sample.turn_count,
                "errors": _json_value(sample.error),
                "artifacts": artifacts,
            }
            record_path = destination / f"{artifact_stem}.json"
            record_path.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            written.append(record_path)
    return written


def _write_invalid_record(
    destination: Path,
    log: Any,
    profile: ModelProfile | dict[str, Any],
    *,
    agent_profile: AgentProfile | dict[str, Any] | None = None,
    reason: str,
    campaign: str,
    cache_state: str,
    sample: Any | None = None,
) -> Path:
    invalid_dir = destination / "_invalid"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    sample_id = str(sample.id) if sample is not None else "log"
    epoch = getattr(sample, "epoch", 0)
    path = invalid_dir / (f"{log.eval.run_id}__{sample_id}__trial-{epoch}.invalid.json")
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "run_id": log.eval.run_id,
                "case_id": sample_id if sample is not None else None,
                "trial_number": epoch if sample is not None else None,
                "campaign": campaign,
                "cache_state": cache_state,
                "model_configuration": _profile_identity(profile),
                "agent_configuration": _agent_profile_identity(agent_profile),
                "inspect_model": str(log.eval.model),
                "validity": {
                    "valid": False,
                    "reason": reason,
                    "inspect_log_status": str(getattr(log, "status", "unknown")),
                    "log_error": _json_value(getattr(log, "error", None)),
                    "sample_error": _json_value(
                        getattr(sample, "error", None) if sample is not None else None
                    ),
                },
                "artifacts": {"inspect_log": str(log.location)},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _score_success(value: Any, quality: float, threshold: Any) -> bool:
    if isinstance(value, dict):
        success = value.get("success")
        if isinstance(success, bool):
            return success
        if isinstance(success, (int, float)) and not isinstance(success, bool):
            return success >= 1
    return _is_success(quality, threshold)


def _score_components(value: Any, metadata_components: Any) -> dict[str, Any]:
    components = dict(metadata_components) if isinstance(metadata_components, dict) else {}
    if isinstance(value, dict):
        for name, component in value.items():
            if name.startswith("component."):
                component_value = _json_value(component)
                if component_value is not None:
                    components[name.removeprefix("component.")] = component_value
    return components


def _inspect_timing(sample: Any) -> dict[str, float | int | None]:
    """Build small timing facts from Inspect events, which remain the source."""
    model_seconds = 0.0
    tool_seconds = 0.0
    model_output_tokens = 0
    model_calls = 0
    tool_calls = 0
    for event in getattr(sample, "events", None) or []:
        event_type = getattr(event, "event", None)
        seconds = getattr(event, "working_time", None)
        if event_type == "model" and getattr(event, "role", None) in {None, ""}:
            model_calls += 1
            if finite_number(seconds) is not None:
                model_seconds += float(seconds)
            output = getattr(event, "output", None)
            usage = getattr(output, "usage", None)
            tokens = getattr(usage, "output_tokens", None)
            if isinstance(tokens, int) and not isinstance(tokens, bool):
                model_output_tokens += tokens
        elif event_type == "tool":
            tool_calls += 1
            if finite_number(seconds) is not None:
                tool_seconds += float(seconds)
    working_seconds = getattr(sample, "working_time", None)
    return {
        "inspect_working_seconds": (
            float(working_seconds) if finite_number(working_seconds) is not None else None
        ),
        "model_working_seconds": model_seconds if model_calls else None,
        "tool_working_seconds": tool_seconds if tool_calls else None,
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "model_output_tokens": model_output_tokens if model_calls else None,
        "observed_output_tokens_per_model_second": (
            model_output_tokens / model_seconds
            if model_output_tokens and model_seconds > 0
            else None
        ),
    }


def _profile_identity(profile: ModelProfile | dict[str, Any]) -> dict[str, Any]:
    if isinstance(profile, ModelProfile):
        return profile.public_identity()
    required = {"profile", "kind", "model", "configuration"}
    if not isinstance(profile, dict) or not required.issubset(profile):
        raise ValueError("Inspect log has no complete benchmark profile identity")
    return dict(profile)


def _agent_profile_identity(
    profile: AgentProfile | dict[str, Any] | None,
) -> dict[str, Any]:
    if profile is None:
        return vanilla_agent_profile().public_identity()
    if isinstance(profile, AgentProfile):
        return profile.public_identity()
    required = {"profile", "configuration", "configuration_fingerprint"}
    if not isinstance(profile, dict) or not required.issubset(profile):
        raise ValueError("Inspect log has no complete agent profile identity")
    return dict(profile)


def _repository_identity() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    paths = [
        Path(line)
        for line in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
        if line
    ]
    fingerprint = hashlib.sha256()
    for relative in sorted(paths):
        path = root / relative
        if not path.is_file():
            continue
        fingerprint.update(str(relative).encode())
        fingerprint.update(b"\0")
        fingerprint.update(path.read_bytes())
        fingerprint.update(b"\0")
    status = git("status", "--porcelain=v1")
    return {
        "repository_commit": git("rev-parse", "HEAD") or None,
        "repository_branch": git("branch", "--show-current") or None,
        "repository_dirty": bool(status),
        "benchmark_fingerprint": fingerprint.hexdigest(),
    }


def _is_success(value: Any, threshold: Any = 1.0) -> bool:
    if isinstance(value, bool):
        return value
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isinstance(threshold, (int, float))
        and not isinstance(threshold, bool)
    ):
        return value >= threshold
    return False


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
