#!/usr/bin/env python3
"""Prove the owned Pi resources load and both example tools execute in Docker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import (
    ChatCompletionChoice,
    ChatMessageAssistant,
    ModelOutput,
    get_model,
)
from inspect_ai.tool import ToolCall

from pi_agent_bench.agent_profiles import load_agent_profiles
from pi_agent_bench.inspect_tasks import coding_tasks

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROFILES = ROOT / "examples" / "agent-profiles" / "agent-profiles.example.json"
SAMPLE_DATASET = ROOT / "evals" / "coding" / "sample.jsonl"


def assistant_tool_calls() -> ModelOutput:
    return ModelOutput(
        model="mockllm/model",
        choices=[
            ChatCompletionChoice(
                message=ChatMessageAssistant(
                    content="",
                    model="mockllm/model",
                    tool_calls=[
                        ToolCall(
                            id="repository-info-call",
                            function="repository_info",
                            arguments={},
                        ),
                        ToolCall(
                            id="mcp-catalog-call",
                            function="example_catalog_lookup",
                            arguments={"query": "widget"},
                        ),
                    ],
                ),
                stop_reason="tool_calls",
            )
        ],
    )


def main() -> int:
    observations = {
        "guidance": False,
        "skill": False,
        "template": False,
        "extension_tool": False,
        "mcp_tool": False,
        "extension_result": False,
        "mcp_result": False,
    }

    def scripted_model(messages, tools, _tool_choice, _config):
        tool_names = {tool.name for tool in tools}
        observations["extension_tool"] |= "repository_info" in tool_names
        observations["mcp_tool"] |= "example_catalog_lookup" in tool_names
        text_by_role: dict[str, str] = {}
        for message in messages:
            text_by_role.setdefault(message.role, "")
            text_by_role[message.role] += f"\n{message.text}"
        system_text = text_by_role.get("system", "")
        user_text = text_by_role.get("user", "")
        tool_text = text_by_role.get("tool", "")
        observations["guidance"] |= "BENCHMARK_GUIDANCE_MARKER" in system_text
        observations["skill"] |= "benchmark-test-first" in system_text
        observations["template"] |= "BENCHMARK_TEMPLATE_MARKER" in user_text
        observations["extension_result"] |= (
            "BENCHMARK_EXTENSION_MARKER" in tool_text
        )
        observations["mcp_result"] |= "BENCHMARK_MCP_MARKER" in tool_text
        if "BENCHMARK_MCP_MARKER" not in tool_text:
            return assistant_tool_calls()
        return ModelOutput.from_content(
            model="mockllm/model",
            content="The owned extension and MCP tools both returned evidence.",
        )

    with tempfile.TemporaryDirectory(prefix="pi-agent-profile-examples-") as temp:
        temporary = Path(temp)
        [case_line, *_] = SAMPLE_DATASET.read_text(encoding="utf-8").splitlines()
        case = json.loads(case_line)
        case["instruction"] = "/benchmark-review README.md"
        dataset = temporary / "example.jsonl"
        dataset.write_text(json.dumps(case) + "\n", encoding="utf-8")
        agent_profile = load_agent_profiles(EXAMPLE_PROFILES)["example-everything"]
        model = get_model(
            "mockllm/model",
            custom_outputs=scripted_model,
            memoize=False,
        )
        logs = inspect_eval(
            coding_tasks(
                dataset=str(dataset),
                agent_profile=agent_profile,
                agent_runtime_env={},
            ),
            model=model,
            log_dir=str(temporary / "logs"),
            display="none",
            max_samples=1,
        )
        if not logs or any(str(log.status) != "success" for log in logs):
            raise RuntimeError("owned agent-profile integration run did not finish")

    missing = [name for name, observed in observations.items() if not observed]
    if missing:
        raise RuntimeError("missing agent-profile evidence: " + ", ".join(missing))
    print("proved: AGENTS.md guidance reached Pi")
    print("proved: the skill appeared in Pi's system prompt")
    print("proved: the prompt template expanded before the model call")
    print("proved: the owned extension tool ran")
    print("proved: the owned MCP extension called its stdio server")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
