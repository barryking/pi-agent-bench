"""Argument parser for the Pi Agent Bench command."""

from __future__ import annotations

import argparse
from pathlib import Path


def _add_profile_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", required=True)
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("configs/model-baselines.example.json"),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="optional ignored KEY=VALUE file, normally .env.local",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi-bench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser(
        "init",
        help="create ignored local configuration files without overwriting",
    )
    init.add_argument("--root", type=Path, default=Path.cwd())

    new_case = subparsers.add_parser(
        "new-case",
        help="scaffold a planning or coding benchmark case",
    )
    new_case.add_argument("phase", choices=["planning", "coding"])
    new_case.add_argument("--id", required=True)
    new_case.add_argument("--dataset", type=Path, required=True)
    new_case.add_argument("--dataset-version", default="draft-1")

    validate = subparsers.add_parser("validate", help="validate a golden JSONL dataset")
    validate.add_argument("dataset", type=Path)

    profiles = subparsers.add_parser("profiles", help="list public-safe model profiles")
    profiles.add_argument(
        "--profiles",
        type=Path,
        default=Path("configs/model-baselines.example.json"),
    )

    subparsers.add_parser("versions", help="show pinned framework and harness versions")

    doctor = subparsers.add_parser("doctor", help="check local prerequisites and a profile")
    _add_profile_arguments(doctor)

    run = subparsers.add_parser("run", help="run Inspect planning or coding suites")
    run.add_argument("phase", choices=["planning", "coding", "all"])
    _add_profile_arguments(run)
    run.add_argument("--logs-dir", type=Path, default=Path("logs"))
    run.add_argument("--results-dir", type=Path, default=Path("results"))
    run.add_argument(
        "--dataset",
        type=Path,
        help="dataset for a planning or coding run; cannot be used with phase=all",
    )
    run.add_argument(
        "--planning-dataset",
        type=Path,
        default=Path("evals/planning/sample.jsonl"),
        help="planning dataset used when phase=all",
    )
    run.add_argument(
        "--coding-dataset",
        type=Path,
        default=Path("evals/coding/sample.jsonl"),
        help="coding dataset used when phase=all",
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
        "--grader-model",
        help=(
            "independent model used for weighted planning-rubric scoring; "
            "omit to use deterministic concept smoke scoring"
        ),
    )
    run.add_argument(
        "--grader-profile",
        help=(
            "profile used as the independent planning grader; recommended when "
            "the evaluated model and grader need different endpoints or credentials"
        ),
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
        help="run the same suite sequentially across several profiles",
    )
    campaign.add_argument("phase", choices=["planning", "coding", "all"])
    campaign.add_argument(
        "--run-profile",
        action="append",
        required=True,
        help="profile to run; repeat for each local or hosted model",
    )
    campaign.add_argument(
        "--profiles",
        type=Path,
        default=Path("configs/model-baselines.local.json"),
    )
    campaign.add_argument("--env-file", type=Path, default=Path(".env.local"))
    campaign.add_argument("--logs-dir", type=Path, default=Path("logs"))
    campaign.add_argument("--results-dir", type=Path, default=Path("results"))
    campaign.add_argument("--dataset", type=Path)
    campaign.add_argument(
        "--planning-dataset",
        type=Path,
        default=Path("evals/planning/sample.jsonl"),
    )
    campaign.add_argument(
        "--coding-dataset",
        type=Path,
        default=Path("evals/coding/sample.jsonl"),
    )
    campaign.add_argument("--epochs", type=int, default=3)
    campaign.add_argument("--campaign", required=True)
    campaign.add_argument(
        "--cache-state",
        choices=["unspecified", "cold", "warm"],
        default="unspecified",
    )
    campaign.add_argument("--grader-profile")
    campaign.add_argument("--grader-model")
    campaign.add_argument("--cost-limit", type=float)
    campaign.add_argument("--build", action="store_true")
    campaign.add_argument("--resume", action="store_true")
    campaign.add_argument("--retry-attempts", type=int, default=1)

    rescore = subparsers.add_parser(
        "rescore-planning",
        help="apply a new independent rubric grader to a completed Inspect log",
    )
    rescore.add_argument("log_file", type=Path)
    grader = rescore.add_mutually_exclusive_group(required=True)
    grader.add_argument("--grader-model")
    grader.add_argument("--grader-profile")
    rescore.add_argument(
        "--profiles",
        type=Path,
        default=Path("configs/model-baselines.example.json"),
    )
    rescore.add_argument("--env-file", type=Path)
    rescore.add_argument("--output-log", type=Path)
    rescore.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the source Inspect log instead of writing *.rescored.eval",
    )

    replay = subparsers.add_parser(
        "replay-coding",
        help="reapply saved coding diffs and rerun protected verifiers",
    )
    replay.add_argument("log_file", type=Path)
    replay.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/replay"),
    )

    prove = subparsers.add_parser(
        "prove-case",
        help="prove that one coding case fails before and passes after a known-good patch",
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
