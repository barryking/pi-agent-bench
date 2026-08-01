import json
import sys

from pi_agent_bench.model_profiles import ModelProfile
from pi_agent_bench.pi_guard import run as run_guard
from pi_agent_bench.pi_runner import (
    PiRunConfig,
    build_command,
    build_models_config,
    model_patterns,
    parse_json_events,
    summarise_direct_usage,
    summarise_events,
    unconfigured_models,
)


def resource(name, *, direct=False):
    execution = (
        {
            "mode": "pi-direct",
            "provider": "openai-codex",
            "model": name,
            "auth_file_env": "PI_AUTH_FILE",
        }
        if direct
        else {
            "mode": "inspect-bridge",
            "model_args": {},
            "model_args_env": {},
            "generate_config": {},
        }
    )
    return ModelProfile.from_dict(
        name,
        {
            "kind": "hosted" if direct else "local",
            "model": f"openai/{name}",
            "execution": execution,
            "capabilities": {
                "context_tokens": 65536,
                "max_output_tokens": 32768,
                "reasoning": True,
                "input": ["text"],
            },
            "configuration": {"revision": name},
        },
    )


def test_builds_ephemeral_json_command():
    command = build_command(
        PiRunConfig(
            provider="dgx-spark",
            model="qwen-coder",
            timeout_seconds=60,
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
        "--tools",
        "read,bash,edit,write,grep,find,ls",
        "--provider",
        "dgx-spark",
        "--model",
        "qwen-coder",
        "Inspect the repository.",
    )


def test_builds_multi_resource_pi_catalog_with_case_caps():
    resources = (resource("local"), resource("reviewer"), resource("subscription", direct=True))
    config = build_models_config(resources, port=13131, context_tokens=32768)

    provider = config["providers"]["inspect-bridge"]
    assert provider["baseUrl"] == "http://localhost:13131/v1"
    assert [model["id"] for model in provider["models"]] == ["local", "reviewer"]
    assert provider["models"][0]["contextWindow"] == 32768
    assert config["providers"]["openai-codex"]["models"][0]["id"] == "subscription"
    assert model_patterns(resources) == (
        "inspect-bridge/local",
        "inspect-bridge/reviewer",
        "openai-codex/subscription",
    )


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


def test_enables_only_the_selected_agent_resources():
    command = build_command(
        PiRunConfig(
            provider="inspect-bridge",
            model="inspect",
            timeout_seconds=60,
            tools=("read", "custom_tool"),
            context_files_enabled=True,
            skills_enabled=True,
            extensions_enabled=True,
            prompt_templates_enabled=True,
        ),
        "Implement the task.",
    )

    assert "--no-approve" in command
    assert "--approve" not in command
    assert "--no-context-files" not in command
    assert "--no-skills" not in command
    assert "--no-extensions" not in command
    assert "--no-prompt-templates" not in command
    assert "--no-themes" in command
    assert command[command.index("--tools") + 1] == "read,custom_tool"


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


def test_direct_usage_excludes_bridge_events_and_keeps_cost_coverage_evidence():
    events = (
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "inspect-bridge",
                "model": "local",
                "responseId": "bridge",
                "usage": {"input": 100, "output": 10},
            },
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "openai-codex",
                "model": "review",
                "responseId": "direct",
                "durationMs": 500,
                "usage": {
                    "input": 20,
                    "cacheRead": 5,
                    "output": 7,
                    "reasoning": 3,
                    "cost": {"total": 0.04},
                },
            },
        },
    )
    usage = summarise_direct_usage(events, {("openai-codex", "review")})

    assert usage.aggregate == {
        "call_count": 1,
        "input_tokens": 25,
        "cached_input_tokens": 5,
        "output_tokens": 7,
        "reasoning_tokens": 3,
        "model_seconds": 0.5,
        "reported_cost": 0.04,
    }
    assert usage.cost_reported_calls == 1


def test_direct_usage_keeps_distinct_events_without_deduplication_keys():
    events = tuple(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "openai-codex",
                "model": "review",
                "usage": {"input": 10, "output": 2},
            },
        }
        for _ in range(2)
    )

    usage = summarise_direct_usage(events, {("openai-codex", "review")})

    assert usage.aggregate["call_count"] == 2
    assert usage.aggregate["input_tokens"] == 20
    assert usage.aggregate["output_tokens"] == 4


def test_rejects_observed_models_outside_the_composed_profile():
    events = (
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "inspect-bridge",
                "model": "local",
            },
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "inspect-bridge",
                "model": "unconfigured-reviewer",
            },
        },
    )

    assert unconfigured_models(events, (resource("local"),)) == (
        "inspect-bridge/unconfigured-reviewer",
    )


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
