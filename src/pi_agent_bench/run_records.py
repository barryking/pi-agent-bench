"""Build small Pi Agent Bench records from Inspect logs."""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .agent_profiles import AgentProfile
from .harness_identity import validate_harness_identity
from .schema_versions import (
    RUN_RECORD_SCHEMA_VERSION,
    SUPPORTED_RUN_RECORD_SCHEMA_VERSIONS,
)
from .usage_records import inspect_timing, json_value, usage_record
from .verification import primary_score, quality_value


def export_inspect_logs(
    logs_dir: str | Path,
    results_dir: str | Path,
) -> list[Path]:
    """Rebuild disposable dashboard records from canonical Inspect logs."""
    from inspect_ai.log import list_eval_logs, read_eval_log

    destination = Path(results_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    previous_records = _managed_valid_records(destination)
    previous_by_log = _records_by_inspect_log(previous_records)
    preserved_records: set[Path] = set()
    written: list[Path] = []
    for info in list_eval_logs(str(Path(logs_dir).expanduser().resolve())):
        log = read_eval_log(info.name)
        source_records = previous_by_log.get(str(log.location), set())
        metadata = getattr(log.eval, "metadata", None) or {}
        benchmark = metadata.get("pi_agent_bench")
        if not isinstance(benchmark, dict):
            warnings.warn(
                f"skipped Inspect log without Pi Agent Bench metadata: {info.name}",
                stacklevel=2,
            )
            preserved_records.update(source_records)
            continue
        agent_profile = benchmark.get("agent_profile")
        cohort_identity = benchmark.get("cohort")
        benchmark_id = benchmark.get("benchmark_id") or log.eval.run_id
        run_name = benchmark.get("run_name")
        cache_state = benchmark.get("cache_state")
        harness_identity = benchmark.get("harness")
        if not isinstance(run_name, str) or not run_name:
            warnings.warn(
                f"skipped Inspect log without a run name: {info.name}",
                stacklevel=2,
            )
            preserved_records.update(source_records)
            continue
        if cache_state not in {"unspecified", "cold", "warm"}:
            warnings.warn(
                f"skipped Inspect log with an invalid cache state: {info.name}",
                stacklevel=2,
            )
            preserved_records.update(source_records)
            continue
        try:
            written.extend(
                write_run_records(
                    [log],
                    destination,
                    agent_profile,
                    benchmark_id=benchmark_id,
                    run_name=run_name,
                    cache_state=cache_state,
                    harness_identity=harness_identity,
                    cohort_identity=cohort_identity,
                )
            )
        except ValueError as exc:
            warnings.warn(f"skipped {info.name}: {exc}", stacklevel=2)
            preserved_records.update(source_records)
    current_records = {path.resolve() for path in written}
    for stale in sorted(previous_records - current_records - preserved_records):
        _remove_record_and_artifacts(stale)
    return written


def write_run_records(
    logs: Iterable[Any],
    results_dir: str | Path,
    agent_profile: AgentProfile | dict[str, Any],
    *,
    run_name: str,
    cache_state: str = "unspecified",
    harness_identity: dict[str, Any],
    cohort_identity: dict[str, Any],
    benchmark_id: str | None = None,
) -> list[Path]:
    destination = Path(results_dir)
    destination.mkdir(parents=True, exist_ok=True)
    harness = validate_harness_identity(harness_identity)
    agent_identity = _agent_profile_identity(agent_profile)
    cohort = _cohort_identity(cohort_identity)
    record_schema_version = (
        RUN_RECORD_SCHEMA_VERSION
        if cohort.get("cohort_schema_version") == 2
        else 5
    )
    written: list[Path] = []
    for log in logs:
        effective_benchmark_id = benchmark_id or str(log.eval.run_id)
        log_status = str(getattr(log, "status", "success"))
        if log_status != "success":
            invalid_path = _write_invalid_record(
                destination,
                log,
                agent_identity,
                reason=f"Inspect log status is {log_status}",
                benchmark_id=effective_benchmark_id,
                record_schema_version=record_schema_version,
                run_name=run_name,
                cache_state=cache_state,
                harness_identity=harness,
                cohort_identity=cohort,
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
                    agent_identity,
                    sample=sample,
                    reason="Inspect sample has an execution error",
                    benchmark_id=effective_benchmark_id,
                    record_schema_version=record_schema_version,
                    run_name=run_name,
                    cache_state=cache_state,
                    harness_identity=harness,
                    cohort_identity=cohort,
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
                    agent_identity,
                    sample=sample,
                    reason="Inspect sample has no score",
                    benchmark_id=effective_benchmark_id,
                    record_schema_version=record_schema_version,
                    run_name=run_name,
                    cache_state=cache_state,
                    harness_identity=harness,
                    cohort_identity=cohort,
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
                    agent_identity,
                    sample=sample,
                    reason="Inspect primary score has no finite quality value",
                    benchmark_id=effective_benchmark_id,
                    record_schema_version=record_schema_version,
                    run_name=run_name,
                    cache_state=cache_state,
                    harness_identity=harness,
                    cohort_identity=cohort,
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
            timing = inspect_timing(sample)
            record = {
                "schema_version": record_schema_version,
                "run_id": log.eval.run_id,
                "benchmark_id": effective_benchmark_id,
                "case_id": str(sample.id),
                "dataset_version": log.eval.task_version,
                "trial_number": sample.epoch,
                "synthetic": bool((sample.metadata or {}).get("synthetic", False)),
                "run_name": run_name,
                "cache_state": cache_state,
                "agent_profile": agent_identity,
                "inspect_model": str(log.eval.model),
                "cohort": cohort,
                "harness": {
                    "pi_version_actual": score_metadata.get("pi_version"),
                    **harness,
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
                    "value": json_value(score_value),
                    "fields": json_value(selected_score.value),
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
                        "value": json_value(score.value),
                        "explanation": score.explanation,
                    }
                    for name, score in scores.items()
                },
                "verifier": {
                    "return_code": score_metadata.get("verifier_return_code"),
                    "stdout": score_metadata.get("verifier_stdout"),
                    "stderr": score_metadata.get("verifier_stderr"),
                },
                "usage": usage_record(
                    sample,
                    score_metadata,
                    agent_identity,
                    timing,
                ),
                "agent": {
                    **score_metadata.get("pi", {}),
                    "wall_seconds": score_metadata.get("pi_wall_seconds"),
                    "return_code": score_metadata.get("pi_return_code"),
                },
                "turn_count": sample.turn_count,
                "errors": json_value(sample.error),
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
    agent_profile: AgentProfile | dict[str, Any],
    *,
    reason: str,
    benchmark_id: str,
    record_schema_version: int,
    run_name: str,
    cache_state: str,
    harness_identity: dict[str, Any],
    cohort_identity: dict[str, Any],
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
                "schema_version": record_schema_version,
                "run_id": log.eval.run_id,
                "benchmark_id": benchmark_id,
                "case_id": sample_id if sample is not None else None,
                "trial_number": epoch if sample is not None else None,
                "run_name": run_name,
                "cache_state": cache_state,
                "agent_profile": _agent_profile_identity(agent_profile),
                "inspect_model": str(log.eval.model),
                "harness": harness_identity,
                "cohort": cohort_identity,
                "validity": {
                    "valid": False,
                    "reason": reason,
                    "inspect_log_status": str(getattr(log, "status", "unknown")),
                    "log_error": json_value(getattr(log, "error", None)),
                    "sample_error": json_value(
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
                component_value = json_value(component)
                if component_value is not None:
                    components[name.removeprefix("component.")] = component_value
    return components




def _agent_profile_identity(
    profile: AgentProfile | dict[str, Any],
) -> dict[str, Any]:
    if isinstance(profile, AgentProfile):
        return profile.public_identity()
    required = {
        "profile",
        "pi_profile",
        "model_resources",
        "default_model_resource",
        "configuration_fingerprint",
    }
    if not isinstance(profile, dict) or not required.issubset(profile):
        raise ValueError("Inspect log has no complete agent profile identity")
    return dict(profile)


def _cohort_identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(
        value.get("cohort_fingerprint"), str
    ):
        raise ValueError("Inspect log has no complete comparison cohort identity")
    return dict(value)


def _managed_valid_records(destination: Path) -> set[Path]:
    """Find only Pi Agent Bench run records that a log rebuild owns."""
    records: set[Path] = set()
    for path in destination.glob("*.json"):
        if path.name == "summary.json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(value, dict)
            and value.get("schema_version") in SUPPORTED_RUN_RECORD_SCHEMA_VERSIONS
            and isinstance(value.get("run_id"), str)
            and isinstance(value.get("case_id"), str)
            and value.get("validity", {}).get("valid") is not False
        ):
            records.add(path.resolve())
    return records


def _records_by_inspect_log(records: set[Path]) -> dict[str, set[Path]]:
    """Index managed records by the canonical log that produced them."""
    indexed: dict[str, set[Path]] = {}
    for path in records:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        artifacts = value.get("artifacts") if isinstance(value, dict) else None
        location = artifacts.get("inspect_log") if isinstance(artifacts, dict) else None
        if isinstance(location, str) and location:
            indexed.setdefault(location, set()).add(path)
    return indexed


def _remove_record_and_artifacts(record_path: Path) -> None:
    """Prune one stale derived record and only artifacts explicitly owned by it."""
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        record = {}
    artifacts = record.get("artifacts", {}) if isinstance(record, dict) else {}
    final_diff = artifacts.get("final_diff") if isinstance(artifacts, dict) else None
    if isinstance(final_diff, str) and final_diff:
        diff_path = Path(final_diff)
        if diff_path.parent.resolve() == record_path.parent.resolve():
            diff_path.unlink(missing_ok=True)
    record_path.unlink(missing_ok=True)


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
