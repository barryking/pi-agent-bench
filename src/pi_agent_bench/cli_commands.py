"""Small, non-execution command handlers."""

from __future__ import annotations

import argparse
import json

from .agent_profiles import load_agent_profiles
from .model_profiles import load_profiles
from .versions import FRAMEWORK_VERSION, INSPECT_VERSION, PI_VERSION, SANDBOX_IMAGE


def _command_init(args: argparse.Namespace) -> None:
    from .workflow import initialize_workspace

    for path, status in initialize_workspace(args.root):
        print(f"{status}: {path}")
    print(
        "next: edit .env.local, configs/model-baselines.local.json, "
        "and configs/agent-profiles.local.json"
    )


def _command_new_case(args: argparse.Namespace) -> None:
    from .workflow import scaffold_case

    try:
        paths = scaffold_case(
            args.id,
            args.dataset,
            dataset_version=args.dataset_version,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for path in paths:
        print(f"created: {path}")
    print(f"next: edit the scaffold, then pi-bench validate {args.dataset}")


def _command_validate(args: argparse.Namespace) -> None:
    from .inspect_tasks import load_case_suite

    try:
        _, cases, version = load_case_suite(args.dataset)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"valid: {len(cases)} outcome case(s); dataset-version={version}")


def _command_model_profiles(args: argparse.Namespace) -> None:
    for profile in load_profiles(args.model_profiles_file).values():
        print(f"{profile.name}: {profile.kind}; model={profile.model}")


def _command_agent_profiles(args: argparse.Namespace) -> None:
    for profile in load_agent_profiles(args.agent_profiles_file).values():
        print(
            f"{profile.name}: tools={','.join(profile.tools)}; "
            f"resources={_agent_resource_count(profile)}"
        )


def _agent_resource_count(profile) -> int:
    return sum(
        len(resources)
        for resources in (
            profile.context_files,
            profile.append_system_prompts,
            profile.skills,
            profile.extensions,
            profile.prompt_templates,
        )
    ) + int(profile.system_prompt is not None)


def _command_versions(_args: argparse.Namespace) -> None:
    print(f"framework={FRAMEWORK_VERSION}")
    print(f"inspect={INSPECT_VERSION}")
    print(f"pi={PI_VERSION}")
    print(f"sandbox={SANDBOX_IMAGE}")


def _command_replay(args: argparse.Namespace) -> None:
    from .replay import replay_outcome_log

    try:
        paths = replay_outcome_log(args.log_file, args.output_dir)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = "MATCH" if payload["score_matches"] else "MISMATCH"
        print(f"{state}: {path}")


def _command_prove(args: argparse.Namespace) -> None:
    from .case_proof import prove_outcome_case

    try:
        path = prove_outcome_case(args.dataset, args.known_good_diff, args.output)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"proved: {path}")


def _command_export(args: argparse.Namespace) -> None:
    from .run_records import export_inspect_logs

    paths = export_inspect_logs(args.logs_dir, args.results_dir)
    print(f"exported: {len(paths)} sample record(s) from Inspect logs")


def _command_report(args: argparse.Namespace) -> None:
    from .reporting import build_report, write_report, write_visualizer_exports

    output = args.output or args.results_dir / "summary.md"
    markdown, summary_json = write_report(build_report(args.results_dir), output)
    runs_csv, metrics_jsonl = write_visualizer_exports(args.results_dir, output.parent)
    print(f"report: {markdown}")
    print(f"summary: {summary_json}")
    print(f"runs: {runs_csv}")
    print(f"metrics: {metrics_jsonl}")


def _command_build_sandbox(_args: argparse.Namespace) -> None:
    from .harness_identity import build_sandbox, sandbox_identity

    build_sandbox()
    identity = sandbox_identity()
    print(f"sandbox: {identity['sandbox_image']}")
    print(f"image-id: {identity['sandbox_image_id']}")
    print(f"source-fingerprint: {identity['sandbox_source_fingerprint']}")
