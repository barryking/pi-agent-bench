"""Argument parser for the Pi Agent Bench command."""

from __future__ import annotations

import argparse
from pathlib import Path


class _ExactArgumentParser(argparse.ArgumentParser):
    """Reject shortened flags so similarly named profile options stay clear."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


def _add_model_and_agent_profile_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model-profile",
        required=True,
        help="name of the model setup to use",
    )
    parser.add_argument(
        "--model-profiles-file",
        type=Path,
        default=Path("configs/model-baselines.example.json"),
        help="JSON file containing model profiles",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="optional ignored KEY=VALUE file, normally .env.local",
    )
    parser.add_argument(
        "--agent-profile",
        default="vanilla",
        help="exact Pi tools and resources to use (default: vanilla)",
    )
    parser.add_argument(
        "--agent-profiles-file",
        type=Path,
        default=Path("configs/agent-profiles.json"),
        help="JSON file containing agent profiles",
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
        help="scaffold one complete repository-outcome benchmark case",
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
        default=Path("configs/model-baselines.example.json"),
        help="JSON file containing model profiles",
    )

    agent_profiles = subparsers.add_parser(
        "agent-profiles",
        help="list reproducible Pi agent profiles",
    )
    agent_profiles.add_argument(
        "--agent-profiles-file",
        type=Path,
        default=Path("configs/agent-profiles.json"),
        help="JSON file containing agent profiles",
    )

    subparsers.add_parser("versions", help="show pinned framework and harness versions")

    doctor = subparsers.add_parser(
        "doctor",
        help="check local prerequisites and one model-and-agent setup",
    )
    _add_model_and_agent_profile_arguments(doctor)

    run = subparsers.add_parser("run", help="run an Inspect outcome suite")
    _add_model_and_agent_profile_arguments(run)
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
        "--campaign",
        default="default",
        help="stable label for a comparable benchmark campaign",
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
        help="run as an Inspect eval set so an interrupted campaign can resume",
    )
    run.add_argument(
        "--retry-attempts",
        type=int,
        default=1,
        help="task attempts for --resume campaigns (default: 1)",
    )

    campaign = subparsers.add_parser(
        "campaign",
        help="run the same suite across several model-and-agent setups",
    )
    campaign.add_argument(
        "--model-profile",
        action="append",
        required=True,
        help="model profile to run; repeat for each local or hosted model",
    )
    campaign.add_argument(
        "--model-profiles-file",
        type=Path,
        default=Path("configs/model-baselines.local.json"),
        help="JSON file containing model profiles",
    )
    campaign.add_argument(
        "--agent-profile",
        action="append",
        help=("agent profile to run; repeat to compare several Pi setups (default: vanilla)"),
    )
    campaign.add_argument(
        "--agent-profiles-file",
        type=Path,
        default=Path("configs/agent-profiles.json"),
        help="JSON file containing agent profiles",
    )
    campaign.add_argument("--env-file", type=Path, default=Path(".env.local"))
    campaign.add_argument("--logs-dir", type=Path, default=Path("logs"))
    campaign.add_argument("--results-dir", type=Path, default=Path("results"))
    campaign.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/starter/cases.jsonl"),
    )
    campaign.add_argument("--epochs", type=int, default=3)
    campaign.add_argument("--campaign", required=True)
    campaign.add_argument(
        "--cache-state",
        choices=["unspecified", "cold", "warm"],
        default="unspecified",
    )
    campaign.add_argument("--cost-limit", type=float)
    campaign.add_argument("--build", action="store_true")
    campaign.add_argument("--resume", action="store_true")
    campaign.add_argument("--retry-attempts", type=int, default=1)

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
        help="prove that one outcome case fails before and passes after a known-good patch",
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

    demo = subparsers.add_parser(
        "demo-data",
        help="generate a balanced synthetic cohort for dashboard preview",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/demo-comparison"),
    )
    demo.add_argument("--trials", type=int, default=3)
    return parser
