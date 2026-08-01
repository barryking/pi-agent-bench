"""Argument parser for the Pi Agent Bench command."""

from __future__ import annotations

import argparse
from pathlib import Path


class _ExactArgumentParser(argparse.ArgumentParser):
    """Reject shortened flags so similarly named profile options stay clear."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


def _add_agent_profile_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agent-profile",
        required=True,
        help="name of the complete runnable agent setup",
    )
    parser.add_argument(
        "--agent-profiles-file",
        type=Path,
        default=Path("configs/agent-profiles.local.json"),
        help="JSON file containing composed agent profiles",
    )
    parser.add_argument(
        "--pi-profiles-file",
        type=Path,
        default=Path("configs/pi-profiles.local.json"),
        help="JSON file containing reusable Pi profiles",
    )
    parser.add_argument(
        "--model-profiles-file",
        type=Path,
        default=Path("configs/model-baselines.local.json"),
        help="JSON file containing model profiles",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env.local"),
        help="optional ignored KEY=VALUE file, normally .env.local",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _ExactArgumentParser(prog="pi-bench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser(
        "init",
        help="create ignored local configuration files without overwriting",
    )
    init.add_argument("--root", type=Path, default=Path.cwd())

    new_case = subparsers.add_parser(
        "new-case",
        help="scaffold one draft candidate repository-outcome case",
    )
    new_case.add_argument("--id", required=True)
    new_case.add_argument("--dataset", type=Path, required=True)
    new_case.add_argument("--dataset-version", default="draft-1")

    validate = subparsers.add_parser("validate", help="validate an outcome-case JSONL dataset")
    validate.add_argument("dataset", type=Path)

    model_profiles = subparsers.add_parser(
        "model-profiles",
        help="list public-safe model profiles",
    )
    model_profiles.add_argument(
        "--model-profiles-file",
        type=Path,
        default=Path("configs/model-baselines.local.json"),
        help="JSON file containing model profiles",
    )

    agent_profiles = subparsers.add_parser(
        "agent-profiles",
        help="list complete runnable agent profiles",
    )
    agent_profiles.add_argument(
        "--agent-profiles-file",
        type=Path,
        default=Path("configs/agent-profiles.local.json"),
        help="JSON file containing composed agent profiles",
    )
    agent_profiles.add_argument(
        "--pi-profiles-file",
        type=Path,
        default=Path("configs/pi-profiles.local.json"),
    )
    agent_profiles.add_argument(
        "--model-profiles-file",
        type=Path,
        default=Path("configs/model-baselines.local.json"),
    )

    pi_profiles = subparsers.add_parser(
        "pi-profiles",
        help="list reusable Pi harness profiles",
    )
    pi_profiles.add_argument(
        "--pi-profiles-file",
        type=Path,
        default=Path("configs/pi-profiles.local.json"),
    )

    subparsers.add_parser("versions", help="show pinned framework and harness versions")
    subparsers.add_parser(
        "build-sandbox",
        help="build and fingerprint the protected Docker sandbox",
    )

    doctor = subparsers.add_parser(
        "doctor",
        help="check local prerequisites and one complete agent profile",
    )
    _add_agent_profile_arguments(doctor)

    run = subparsers.add_parser("run", help="run an Inspect outcome suite")
    _add_agent_profile_arguments(run)
    run.add_argument("--logs-dir", type=Path, default=Path("logs"))
    run.add_argument("--results-dir", type=Path, default=Path("results"))
    run.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/sample/cases.jsonl"),
        help="outcome dataset to run",
    )
    run.add_argument("--epochs", type=int, default=1)
    run.add_argument(
        "--run-name",
        default="default",
        help="short name for this benchmark run",
    )
    run.add_argument(
        "--benchmark-id",
        help="campaign ID shared by comparison arms; generated automatically when omitted",
    )
    run.add_argument(
        "--cache-state",
        choices=["unspecified", "cold", "warm"],
        default="unspecified",
        help="record whether model inference used a cold or warm cache",
    )
    run.add_argument(
        "--build",
        action="store_true",
        help="build the pinned sandbox image before evaluating",
    )
    run.add_argument(
        "--cost-limit",
        type=float,
        help="optional provider-reported cost ceiling for each Inspect task",
    )
    run.add_argument(
        "--resume",
        action="store_true",
        help="run as an Inspect eval set so an interrupted benchmark run can resume",
    )
    run.add_argument(
        "--retry-attempts",
        type=int,
        default=1,
        help="task attempts for --resume benchmark runs (default: 1)",
    )

    benchmark = subparsers.add_parser(
        "benchmark",
        help="run the same suite across several complete agent profiles",
    )
    benchmark.add_argument(
        "--agent-profile",
        action="append",
        required=True,
        help="complete agent profile to run; repeat to compare profiles",
    )
    benchmark.add_argument(
        "--agent-profiles-file",
        type=Path,
        default=Path("configs/agent-profiles.local.json"),
        help="JSON file containing composed agent profiles",
    )
    benchmark.add_argument(
        "--pi-profiles-file",
        type=Path,
        default=Path("configs/pi-profiles.local.json"),
    )
    benchmark.add_argument(
        "--model-profiles-file",
        type=Path,
        default=Path("configs/model-baselines.local.json"),
        help="JSON file containing reusable model resources",
    )
    benchmark.add_argument("--env-file", type=Path, default=Path(".env.local"))
    benchmark.add_argument("--logs-dir", type=Path, default=Path("logs"))
    benchmark.add_argument("--results-dir", type=Path, default=Path("results"))
    benchmark.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/starter/cases.jsonl"),
    )
    benchmark.add_argument("--epochs", type=int, default=3)
    benchmark.add_argument(
        "--run-name",
        required=True,
        help="short name shared by every setup in this benchmark run",
    )
    benchmark.add_argument(
        "--benchmark-id",
        help="campaign ID to resume or extend; generated automatically when omitted",
    )
    benchmark.add_argument(
        "--cache-state",
        choices=["unspecified", "cold", "warm"],
        default="unspecified",
    )
    benchmark.add_argument("--cost-limit", type=float)
    benchmark.add_argument(
        "--build",
        action="store_true",
        help="rebuild and fingerprint the sandbox before the first setup",
    )
    benchmark.add_argument("--resume", action="store_true")
    benchmark.add_argument("--retry-attempts", type=int, default=1)

    replay = subparsers.add_parser(
        "replay-outcome",
        help="reapply a saved repository diff and rerun its protected verifier",
    )
    replay.add_argument("log_file", type=Path)
    replay.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/replay"),
    )

    prove = subparsers.add_parser(
        "prove-case",
        help="maintainer check: prove a case fails before and passes after a known-good patch",
    )
    prove.add_argument("dataset", type=Path)
    prove.add_argument("--known-good-diff", type=Path, required=True)
    prove.add_argument(
        "--output",
        type=Path,
        default=Path("results/case-proofs/proof.json"),
    )

    export = subparsers.add_parser(
        "export",
        help="rebuild disposable dashboard records from Inspect logs",
    )
    export.add_argument("--logs-dir", type=Path, default=Path("logs"))
    export.add_argument("--results-dir", type=Path, default=Path("results"))

    report = subparsers.add_parser("report", help="aggregate local run records")
    report.add_argument("--results-dir", type=Path, default=Path("results"))
    report.add_argument(
        "--output",
        type=Path,
        help="summary path; defaults to <results-dir>/summary.md",
    )

    view = subparsers.add_parser("view", help="open the local metrics dashboard")
    view.add_argument("--results-dir", type=Path, default=Path("results"))
    view.add_argument("--host", default="127.0.0.1")
    view.add_argument("--port", type=int, default=8765)
    view.add_argument(
        "--no-open",
        action="store_true",
        help="start the server without opening a browser",
    )
    view.add_argument(
        "--inspect",
        action="store_true",
        help="also start Inspect's detailed trajectory viewer",
    )
    view.add_argument("--logs-dir", type=Path, default=Path("logs"))
    view.add_argument("--inspect-port", type=int, default=7575)

    return parser
