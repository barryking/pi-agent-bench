"""Pi Agent Bench command-line entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from .cli_commands import (
    _command_agent_profiles,
    _command_build_sandbox,
    _command_export,
    _command_init,
    _command_model_profiles,
    _command_new_case,
    _command_prove,
    _command_replay,
    _command_report,
    _command_validate,
    _command_versions,
)
from .cli_execution import (
    _benchmark,
    _doctor,
    _resolve_agent_profile,
    _resolve_model_profile,
    _run,
)
from .cli_parser import build_parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {
        "init": _command_init,
        "new-case": _command_new_case,
        "validate": _command_validate,
        "model-profiles": _command_model_profiles,
        "agent-profiles": _command_agent_profiles,
        "versions": _command_versions,
        "build-sandbox": _command_build_sandbox,
        "doctor": _command_doctor,
        "run": _run,
        "benchmark": _benchmark,
        "replay-outcome": _command_replay,
        "prove-case": _command_prove,
        "export": _command_export,
        "report": _command_report,
        "view": _command_view,
    }
    handlers[args.command](args)


def _command_doctor(args: argparse.Namespace) -> None:
    profile = _resolve_model_profile(args)
    agent_profile = _resolve_agent_profile(args)
    failures = _doctor(profile, agent_profile)
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"ready: model-profile={profile.name}; agent-profile={agent_profile.name}; "
        f"model={profile.model}"
    )


def _command_view(args: argparse.Namespace) -> None:
    from .viewer import serve_dashboard

    inspect_process = (
        _start_inspect_view(
            args.logs_dir,
            host=args.host,
            port=args.inspect_port,
            open_browser=not args.no_open,
        )
        if args.inspect
        else None
    )
    try:
        serve_dashboard(
            args.results_dir,
            host=args.host,
            port=args.port,
            open_browser=not args.no_open,
        )
    finally:
        if inspect_process is not None:
            inspect_process.terminate()
            try:
                inspect_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                inspect_process.kill()


def _start_inspect_view(
    logs_dir: Path,
    *,
    host: str,
    port: int,
    open_browser: bool,
) -> subprocess.Popen:
    inspect_executable = Path(sys.executable).with_name("inspect")
    if not inspect_executable.is_file():
        raise SystemExit("Inspect CLI is missing from this environment; reinstall Pi Agent Bench")
    source = logs_dir.expanduser().resolve()
    source.mkdir(parents=True, exist_ok=True)
    command = [
        str(inspect_executable),
        "view",
        "--log-dir",
        str(source),
        "--host",
        host,
        "--port",
        str(port),
    ]
    process = subprocess.Popen(command)
    url = f"http://{host}:{port}/"
    print(f"inspect viewer: {url}")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    return process
