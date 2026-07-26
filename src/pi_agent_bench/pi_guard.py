"""Guard one Pi Agent Bench JSON run."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
from contextlib import suppress


def _usage_tokens(event: dict[str, object]) -> int:
    if event.get("type") != "message_end":
        return 0
    message = event.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return 0
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return 0
    total = usage.get("totalTokens")
    if isinstance(total, int) and not isinstance(total, bool):
        return total
    values = [usage.get("input"), usage.get("output")]
    return sum(
        value
        for value in values
        if isinstance(value, int) and not isinstance(value, bool)
    )


def _terminate(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)


def run(command: list[str], max_turns: int, max_tokens: int) -> int:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stderr: list[str] = []
    stderr_thread = threading.Thread(
        target=lambda: stderr.extend(process.stderr.readlines()),
        daemon=True,
    )
    stderr_thread.start()

    turns = 0
    tokens = 0
    seen_assistant_messages: set[str] = set()
    exceeded = ""
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn_start":
            turns += 1
        message = event.get("message")
        message_key = ""
        if (
            event.get("type") == "message_end"
            and isinstance(message, dict)
            and message.get("role") == "assistant"
        ):
            response_id = message.get("responseId")
            timestamp = message.get("timestamp")
            message_key = (
                f"response:{response_id}"
                if isinstance(response_id, str) and response_id
                else f"timestamp:{timestamp}"
            )
        if not message_key or message_key not in seen_assistant_messages:
            tokens += _usage_tokens(event)
            if message_key:
                seen_assistant_messages.add(message_key)
        if turns > max_turns:
            exceeded = f"Pi exceeded the {max_turns}-turn case limit"
        elif tokens > max_tokens:
            exceeded = (
                f"Pi exceeded the {max_tokens:,}-token case limit "
                f"(observed {tokens:,})"
            )
        if exceeded:
            sys.stdout.write(
                json.dumps(
                    {
                        "type": "pi_agent_bench_limit",
                        "limit": "turns" if turns > max_turns else "tokens",
                        "observed_turns": turns,
                        "observed_tokens": tokens,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            sys.stdout.flush()
            _terminate(process)
            break

    return_code = process.wait()
    stderr_thread.join(timeout=2)
    if stderr:
        sys.stderr.write("".join(stderr))
    if exceeded:
        sys.stderr.write(f"\n{exceeded}\n")
        return 75
    return return_code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-turns", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    raise SystemExit(run(command, args.max_turns, args.max_tokens))


if __name__ == "__main__":
    main()
