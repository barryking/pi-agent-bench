import json
import sys

from pi_agent_bench.pi_guard import run as run_guard
from pi_agent_bench.pi_runner import (
    PiRunConfig,
    build_bridge_models_config,
    build_command,
    parse_json_events,
    summarise_events,
)


def test_builds_ephemeral_json_command():
    command = build_command(
        PiRunConfig(
            provider="dgx-spark",
            model="qwen-coder",
            timeout_seconds=60,
            trust_mode="no-approve",
        ),
        "Inspect the repository.",
    )

    assert command == (
        "pi",
        "--mode",
        "json",
        "--no-session",
        "--no-approve",
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--tools",
        "read,bash,edit,write,grep,find,ls",
        "--provider",
        "dgx-spark",
        "--model",
        "qwen-coder",
        "Inspect the repository.",
    )


def test_builds_minimal_inspect_bridge_provider():
    config = build_bridge_models_config(port=13131, context_tokens=32768)

    provider = config["providers"]["inspect-bridge"]
    assert provider["baseUrl"] == "http://localhost:13131/v1"
    assert provider["models"][0]["id"] == "inspect"
    assert provider["models"][0]["contextWindow"] == 32768


def test_builds_direct_command_with_explicit_thinking_level():
    command = build_command(
        PiRunConfig(
            provider="openai-codex",
            model="gpt-5.6-sol",
            timeout_seconds=60,
            thinking_level="high",
        ),
        "Implement the task.",
    )

    assert command[
        command.index("--thinking") : command.index("--thinking") + 2
    ] == ("--thinking", "high")
    assert command[-4:] == (
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        "Implement the task.",
    )[-4:]


def test_parses_and_summarises_pi_events():
    stdout = "\n".join(
        [
            '{"type":"turn_start"}',
            '{"type":"tool_execution_start","toolName":"read"}',
            '{"type":"tool_execution_end","toolName":"read","isError":false}',
            '{"type":"compaction_start"}',
            (
                '{"type":"message_end","message":{"role":"assistant",'
                '"usage":{"input":10,"cacheRead":4,"output":3}}}'
            ),
            "unexpected output",
        ]
    )

    events, non_json = parse_json_events(stdout)
    summary = summarise_events(events)

    assert non_json == ("unexpected output",)
    assert summary.turns == 1
    assert summary.tool_calls == 1
    assert summary.failed_tool_calls == 0
    assert summary.compactions == 1
    assert summary.input_tokens == 14
    assert summary.cached_input_tokens == 4
    assert summary.output_tokens == 3


def test_guard_deduplicates_streamed_assistant_completion_events():
    event = json.dumps(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "responseId": "response-1",
                "usage": {"totalTokens": 100},
            },
        }
    )

    return_code = run_guard(
        [sys.executable, "-c", f"print({event!r}); print({event!r})"],
        max_turns=10,
        max_tokens=150,
    )

    assert return_code == 0
