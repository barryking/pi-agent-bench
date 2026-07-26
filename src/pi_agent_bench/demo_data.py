"""Safe fake results for previewing the Pi Agent Bench dashboard."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEMO_PROFILES = {
    "local-fast-35b": {
        "kind": "local",
        "model": "mock/local-fast-35b",
        "quality": 0.68,
        "seconds": 78.0,
        "tokens": 7600,
        "cost": None,
        "configuration": {
            "hardware": "local-accelerator",
            "quantization": "FP8",
            "runtime": "vLLM",
            "context_limit": 131072,
        },
    },
    "local-quality-120b": {
        "kind": "local",
        "model": "mock/local-quality-120b",
        "quality": 0.79,
        "seconds": 156.0,
        "tokens": 8900,
        "cost": None,
        "configuration": {
            "hardware": "local-accelerator",
            "quantization": "FP8",
            "runtime": "vLLM",
            "context_limit": 131072,
        },
    },
    "cloud-frontier": {
        "kind": "hosted",
        "model": "mock/cloud-frontier",
        "quality": 0.93,
        "seconds": 54.0,
        "tokens": 9800,
        "cost": 0.42,
        "configuration": {
            "provider": "mock-cloud-a",
            "model_snapshot": "demo-2026-07",
            "context_limit": 131072,
            "cost_currency": "USD",
        },
    },
    "cloud-balanced": {
        "kind": "hosted",
        "model": "mock/cloud-balanced",
        "quality": 0.84,
        "seconds": 39.0,
        "tokens": 8200,
        "cost": 0.16,
        "configuration": {
            "provider": "mock-cloud-b",
            "model_snapshot": "demo-2026-07",
            "context_limit": 131072,
            "cost_currency": "USD",
        },
    },
    "cloud-economy": {
        "kind": "hosted",
        "model": "mock/cloud-economy",
        "quality": 0.72,
        "seconds": 27.0,
        "tokens": 6900,
        "cost": 0.035,
        "configuration": {
            "provider": "mock-cloud-c",
            "model_snapshot": "demo-2026-07",
            "context_limit": 65536,
            "cost_currency": "USD",
        },
    },
}

DEMO_CASES = {
    "planning": [
        "plan-auth-migration",
        "plan-rate-limiter",
        "plan-event-recovery",
        "plan-tenant-isolation",
        "plan-observability",
        "plan-zero-downtime",
    ],
    "coding": [
        "code-health-endpoint",
        "code-pagination-fix",
        "code-cache-invalidation",
        "code-webhook-retry",
        "code-schema-migration",
        "code-permission-boundary",
    ],
}


def generate_demo_results(
    output_dir: str | Path,
    *,
    trials: int = 3,
) -> list[Path]:
    """Write a balanced, clearly marked synthetic cohort."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    existing = list(destination.glob("*.json"))
    if existing:
        raise ValueError(
            f"{destination}: contains JSON results; choose an empty demo directory"
        )

    randomizer = random.Random(20260725)
    started = datetime(2026, 5, 30, 9, 0, tzinfo=UTC)
    written: list[Path] = []
    for phase, cases in DEMO_CASES.items():
        phase_adjustment = -0.03 if phase == "coding" else 0.0
        for profile_index, (profile, spec) in enumerate(DEMO_PROFILES.items()):
            for case_index, case_id in enumerate(cases):
                difficulty = (case_index - 2.5) * 0.025
                for trial in range(1, trials + 1):
                    quality = _clamp(
                        spec["quality"]
                        + phase_adjustment
                        - difficulty
                        + randomizer.uniform(-0.07, 0.07)
                    )
                    success = quality >= 0.78
                    wall_seconds = max(
                        8.0,
                        spec["seconds"]
                        * (1 + difficulty)
                        * randomizer.uniform(0.84, 1.18),
                    )
                    total_tokens = int(
                        spec["tokens"]
                        * (1 + difficulty)
                        * randomizer.uniform(0.88, 1.14)
                    )
                    input_tokens = int(total_tokens * randomizer.uniform(0.68, 0.78))
                    output_tokens = total_tokens - input_tokens
                    run_id = (
                        f"demo-{phase}-{profile_index + 1}-{case_index + 1}-{trial}"
                    )
                    timestamp = started + timedelta(
                        days=(trial - 1) * 21 + case_index,
                        minutes=profile_index * 11,
                    )
                    cost = spec["cost"]
                    record = _record(
                        run_id=run_id,
                        case_id=case_id,
                        phase=phase,
                        trial=trial,
                        timestamp=timestamp,
                        profile=profile,
                        spec=spec,
                        quality=quality,
                        success=success,
                        wall_seconds=wall_seconds,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_cost=(
                            cost * total_tokens / spec["tokens"]
                            if cost is not None
                            else None
                        ),
                        randomizer=randomizer,
                    )
                    path = destination / f"{run_id}.json"
                    path.write_text(
                        json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    written.append(path)
    return written


def _record(
    *,
    run_id: str,
    case_id: str,
    phase: str,
    trial: int,
    timestamp: datetime,
    profile: str,
    spec: dict[str, Any],
    quality: float,
    success: bool,
    wall_seconds: float,
    input_tokens: int,
    output_tokens: int,
    total_cost: float | None,
    randomizer: random.Random,
) -> dict[str, Any]:
    tool_calls = randomizer.randint(4, 13) if phase == "coding" else randomizer.randint(1, 5)
    failed_tools = 0 if randomizer.random() > 0.16 else 1
    components = {
        "correctness": quality >= 0.72,
        "completeness": quality >= 0.78,
        "constraints": quality >= 0.66,
        "regressions_avoided": quality >= 0.84,
    }
    usage = {
        spec["model"]: {
            "input_tokens": input_tokens,
            "input_tokens_cache_write": int(input_tokens * 0.08),
            "input_tokens_cache_read": int(input_tokens * 0.22),
            "reasoning_tokens": int(output_tokens * 0.42),
            "output_tokens": output_tokens,
            "total_cost": total_cost,
        }
    }
    return {
        "schema_version": 1,
        "synthetic": True,
        "run_id": run_id,
        "case_id": case_id,
        "dataset_version": "demo-1.0.0",
        "started_at": timestamp.isoformat().replace("+00:00", "Z"),
        "campaign": "synthetic-preview",
        "cache_state": "warm",
        "phase": phase,
        "trial_number": trial,
        "model_configuration": {
            "profile": profile,
            "kind": spec["kind"],
            "configuration_fingerprint": f"demo-config-{profile}",
            "configuration": spec["configuration"],
        },
        "inspect_model": spec["model"],
        "harness": {
            "framework_version": "0.5.0-demo",
            "inspect_version": "0.3.249",
            "pi_version_actual": "0.82.1",
            "sandbox_image": "pi-agent-bench-sandbox:0.5.0",
            "repository_commit": "demo000000000000000000000000000000000000",
            "repository_branch": "synthetic-preview",
            "repository_dirty": False,
            "benchmark_fingerprint": "demo-balanced-cohort-v1",
        },
        "success": success,
        "score": {
            "name": "demo_quality",
            "value": round(quality, 4),
            "explanation": "Synthetic preview value; not produced by an evaluation.",
            "components": components,
            "method": "synthetic-demo",
            "success_threshold": 0.78,
            "grader_model": None,
        },
        "wall_seconds": round(wall_seconds, 3),
        "usage": usage,
        "agent": {
            "wall_seconds": round(wall_seconds * randomizer.uniform(0.88, 0.96), 3),
            "turns": randomizer.randint(3, 9),
            "tool_calls": tool_calls,
            "failed_tool_calls": failed_tools,
            "retries": failed_tools,
            "compactions": 1 if input_tokens > 7000 and randomizer.random() < 0.3 else 0,
            "return_code": 0 if success else 1,
        },
        "verifier": {"return_code": 0 if success else 1},
        "errors": None,
        "artifacts": {
            "inspect_log": f"logs/demo/{run_id}.eval",
        },
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
