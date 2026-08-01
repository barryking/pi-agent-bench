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
    ModelUsage,
    get_model,
)
from inspect_ai.tool import ToolCall

from pi_agent_bench.agent_profiles import load_agent_profiles
from pi_agent_bench.harness_identity import capture_harness_identity, cohort_identity
from pi_agent_bench.inspect_tasks import outcome_tasks
from pi_agent_bench.model_profiles import load_profiles
from pi_agent_bench.pi_profiles import load_pi_profiles
from pi_agent_bench.reporting import build_report, write_visualizer_exports
from pi_agent_bench.run_records import write_run_records

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROFILES = ROOT / "examples" / "agent-profiles" / "agent-profiles.example.json"
EXAMPLE_PI_PROFILES = ROOT / "examples" / "agent-profiles" / "pi-profiles.example.json"
EXAMPLE_MODELS = ROOT / "examples" / "agent-profiles" / "model-profiles.example.json"
SAMPLE_DATASET = ROOT / "evals" / "sample" / "cases.jsonl"


def assistant_tool_calls(model: str) -> ModelOutput:
    return ModelOutput(
        model=model,
        usage=ModelUsage(input_tokens=20, output_tokens=8, total_tokens=28),
        choices=[
            ChatCompletionChoice(
                message=ChatMessageAssistant(
                    content="",
                    model=model,
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
        "primary_model": False,
        "review_model": False,
    }

    def scripted_model(output_model, messages, tools, _tool_choice, _config):
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
            return assistant_tool_calls(output_model)
        output = ModelOutput.from_content(
            model=output_model,
            content="The owned extension and MCP tools both returned evidence.",
        )
        output.usage = ModelUsage(input_tokens=30, output_tokens=10, total_tokens=40)
        return output

    with tempfile.TemporaryDirectory(prefix="pi-agent-profile-examples-") as temp:
        temporary = Path(temp)
        [case_line, *_] = SAMPLE_DATASET.read_text(encoding="utf-8").splitlines()
        case = json.loads(case_line)
        case["instruction"] = "/benchmark-review README.md"
        dataset = temporary / "example.jsonl"
        dataset.write_text(json.dumps(case) + "\n", encoding="utf-8")
        agent_profile = load_agent_profiles(
            EXAMPLE_PROFILES,
            pi_profiles=load_pi_profiles(EXAMPLE_PI_PROFILES),
            model_profiles=load_profiles(EXAMPLE_MODELS),
        )["example-everything-agent"]

        def primary_model(*args):
            observations["primary_model"] = True
            return scripted_model("mockllm/primary", *args)

        def review_model(*args):
            observations["review_model"] = True
            return scripted_model("mockllm/reviewer", *args)

        primary = get_model(
            "mockllm/primary",
            custom_outputs=primary_model,
            memoize=False,
        )
        reviewer = get_model(
            "mockllm/reviewer",
            custom_outputs=review_model,
            memoize=False,
        )
        logs = inspect_eval(
            outcome_tasks(
                dataset=str(dataset),
                agent_profile=agent_profile,
                bridged_models={
                    "example-model": primary,
                    "review-model": reviewer,
                },
                agent_runtime_env={},
            ),
            model=primary,
            log_dir=str(temporary / "logs"),
            display="none",
            max_samples=1,
        )
        if not logs or any(str(log.status) != "success" for log in logs):
            raise RuntimeError("owned agent-profile integration run did not finish")
        sample = logs[0].samples[0]
        used_models = set(sample.model_usage)
        expected_models = {"mockllm/primary", "mockllm/reviewer"}
        if not expected_models.issubset(used_models):
            raise RuntimeError(
                "Inspect model usage did not retain both bridged models: "
                + ", ".join(sorted(used_models))
            )
        transcript_models = {
            message.model
            for message in sample.messages
            if isinstance(message, ChatMessageAssistant) and message.model
        }
        transcript_models.update(
            model
            for event in sample.events
            if isinstance((model := getattr(event, "model", None)), str) and model
        )
        if not expected_models.issubset(transcript_models):
            raise RuntimeError(
                "Inspect transcript did not retain both bridged models: "
                + ", ".join(sorted(transcript_models))
            )
        results = temporary / "results"
        harness = capture_harness_identity(ROOT)
        cohort = cohort_identity(
            dataset,
            cache_state="cold",
            cost_limit=None,
            harness=harness,
            root=ROOT,
        )
        records = write_run_records(
            logs,
            results,
            agent_profile,
            benchmark_id="ci-integration",
            run_name="ci",
            cache_state="cold",
            harness_identity=harness,
            cohort_identity=cohort,
        )
        report = build_report(results)
        runs_csv, metrics_jsonl = write_visualizer_exports(results)
        if len(records) != 1 or report["records"] != 1:
            raise RuntimeError("integration run did not create one dashboard record")
        if not runs_csv.is_file() or not metrics_jsonl.is_file():
            raise RuntimeError("integration run did not create visualizer exports")

    missing = [name for name, observed in observations.items() if not observed]
    if missing:
        raise RuntimeError("missing agent-profile evidence: " + ", ".join(missing))
    print("proved: AGENTS.md guidance reached Pi")
    print("proved: the skill appeared in Pi's system prompt")
    print("proved: the prompt template expanded before the model call")
    print("proved: the owned extension tool ran")
    print("proved: the owned MCP extension called its stdio server")
    print("proved: an owned extension switched between two bridged models")
    print("proved: Inspect logs became dashboard records and visualizer exports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
