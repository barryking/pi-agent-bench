"""Run an isolated Pi agent inside an Inspect task sandbox."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from inspect_ai.agent import Agent, AgentState, agent, sandbox_agent_bridge
from inspect_ai.model import ChatMessageAssistant, user_prompt
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import StoreModel, sandbox, store_as
from pydantic import Field

from .agent_profiles import AgentProfile, AgentResource, vanilla_agent_profile
from .pi_runner import (
    PiRunConfig,
    build_bridge_models_config,
    build_command,
    parse_json_events,
    summarise_events,
)
from .versions import PI_VERSION


class PiTelemetry(StoreModel):
    """Pi process data retained in the Inspect log for the current sample."""

    command: list[str] = Field(default_factory=list)
    pi_version: str = ""
    return_code: int | None = None
    wall_seconds: float = 0.0
    events: list[dict[str, Any]] = Field(default_factory=list)
    non_json_lines: list[str] = Field(default_factory=list)
    stderr: str = ""
    summary: dict[str, int] = Field(default_factory=dict)


class PiCaseLimits(StoreModel):
    """Per-sample limits copied from TaskState for the custom agent."""

    seconds: int = 600
    turns: int = 30
    context_tokens: int = 32768
    total_tokens: int = 32768


@solver
def configure_pi_case() -> Solver:
    """Make sample metadata available to the narrower AgentState interface."""

    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        limits = state.metadata.get("limits", {})
        case_limits = store_as(PiCaseLimits)
        case_limits.seconds = int(limits.get("seconds", case_limits.seconds))
        case_limits.turns = int(limits.get("turns", case_limits.turns))
        case_limits.context_tokens = int(limits.get("context_tokens", case_limits.context_tokens))
        case_limits.total_tokens = int(limits.get("total_tokens", case_limits.context_tokens))
        return state

    return solve


@agent
def pi_agent(
    timeout_seconds: int | None = None,
    context_tokens: int | None = None,
    direct_provider: str | None = None,
    direct_model: str | None = None,
    direct_auth_file: str | None = None,
    thinking_level: str | None = None,
    agent_profile: AgentProfile | None = None,
    agent_runtime_env: dict[str, str] | None = None,
) -> Agent:
    """Run Pi through Inspect's bridge or an isolated Pi subscription login."""
    selected_agent = agent_profile or vanilla_agent_profile()
    tools = selected_agent.tools
    configured_runtime_env = dict(agent_runtime_env or {})

    async def execute(state: AgentState) -> AgentState:
        runtime_env = dict(configured_runtime_env)
        limits = store_as(PiCaseLimits)
        sample_timeout = timeout_seconds or limits.seconds
        sample_context = context_tokens or limits.context_tokens
        telemetry = store_as(PiTelemetry)
        prompt = user_prompt(state.messages).text
        version_result = await sandbox().exec(["pi", "--version"], timeout=30)
        if not version_result.success:
            raise RuntimeError(f"could not read Pi version: {version_result.stderr}")
        telemetry.pi_version = version_result.stdout.strip()
        if telemetry.pi_version != PI_VERSION:
            raise RuntimeError(
                f"sandbox Pi version {telemetry.pi_version!r} does not match "
                f"framework pin {PI_VERSION!r}"
            )
        pi_home = "/tmp/pi-bench-pi-home"
        config_dir = f"{pi_home}/.pi/agent"
        mkdir = await sandbox().exec(["mkdir", "-p", config_dir])
        if not mkdir.success:
            raise RuntimeError(f"could not create isolated Pi home: {mkdir.stderr}")
        await _stage_agent_profile(selected_agent, config_dir)
        if selected_agent.mcp_servers:
            runtime_env["PI_BENCH_MCP_CONFIG"] = f"{config_dir}/mcp-servers.json"

        if direct_provider or direct_model or direct_auth_file:
            if not all((direct_provider, direct_model, direct_auth_file)):
                raise RuntimeError("direct Pi execution configuration is incomplete")
            auth_source = Path(direct_auth_file)
            try:
                auth = json.loads(auth_source.read_text(encoding="utf-8"))
                provider_auth = auth[direct_provider]
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                raise RuntimeError(
                    f"could not load {direct_provider} credentials from the configured Pi auth file"
                ) from exc
            await sandbox().write_file(
                f"{config_dir}/auth.json",
                json.dumps({direct_provider: provider_auth}),
            )
            await sandbox().exec(["chmod", "600", f"{config_dir}/auth.json"])
            guard_source = Path(__file__).with_name("pi_guard.py")
            await sandbox().write_file(
                "/tmp/pi-bench-pi-guard.py",
                guard_source.read_text(encoding="utf-8"),
            )
            config = PiRunConfig(
                provider=direct_provider,
                model=direct_model,
                timeout_seconds=sample_timeout,
                trust_mode=selected_agent.trust_mode,
                tools=tools,
                context_files_enabled=bool(selected_agent.context_files),
                skills_enabled=bool(selected_agent.skills),
                extensions_enabled=bool(selected_agent.extensions),
                prompt_templates_enabled=bool(selected_agent.prompt_templates),
                thinking_level=thinking_level,
            )
            command = build_command(config, prompt)
            guarded_command = [
                "python3",
                "/tmp/pi-bench-pi-guard.py",
                "--max-turns",
                str(limits.turns),
                "--max-tokens",
                str(limits.total_tokens),
                "--",
                *command,
            ]
            telemetry.command = list(command)
            result = await _execute_pi(
                guarded_command,
                pi_home,
                sample_timeout,
                telemetry,
                runtime_env,
            )
            events, non_json_lines = parse_json_events(result.stdout)
            _record_telemetry(telemetry, result, events, non_json_lines)
            final_text = _final_assistant_text(events)
            state.messages.append(
                ChatMessageAssistant(
                    content=final_text,
                    model=f"{direct_provider}/{direct_model}",
                )
            )
            if not result.success and result.returncode != 75:
                detail = result.stderr.strip() or "no stderr was produced"
                raise RuntimeError(f"Pi exited with code {result.returncode}: {detail}")
            return state

        async with sandbox_agent_bridge(
            state,
            forward_generation_config=False,
        ) as bridge:
            await sandbox().write_file(
                f"{config_dir}/models.json",
                json.dumps(
                    build_bridge_models_config(
                        port=bridge.port,
                        context_tokens=sample_context,
                    )
                ),
            )

            config = PiRunConfig(
                provider="inspect-bridge",
                model="inspect",
                timeout_seconds=sample_timeout,
                trust_mode=selected_agent.trust_mode,
                tools=tools,
                context_files_enabled=bool(selected_agent.context_files),
                skills_enabled=bool(selected_agent.skills),
                extensions_enabled=bool(selected_agent.extensions),
                prompt_templates_enabled=bool(selected_agent.prompt_templates),
            )
            command = build_command(config, prompt)
            telemetry.command = list(command)
            result = await _execute_pi(
                list(command),
                pi_home,
                sample_timeout,
                telemetry,
                {"OPENAI_API_KEY": "inspect", **runtime_env},
            )
            events, non_json_lines = parse_json_events(result.stdout)
            _record_telemetry(telemetry, result, events, non_json_lines)

            if not result.success:
                detail = result.stderr.strip() or "no stderr was produced"
                raise RuntimeError(f"Pi exited with code {result.returncode}: {detail}")
            return bridge.state

    return execute


async def _stage_agent_profile(profile: AgentProfile, config_dir: str) -> None:
    await sandbox().write_file(
        f"{config_dir}/settings.json",
        json.dumps(profile.settings, sort_keys=True),
    )
    if profile.context_files:
        contents = _joined_text_resources(profile.context_files, "AGENTS.md")
        await sandbox().write_file(f"{config_dir}/AGENTS.md", contents)
    if profile.system_prompt:
        await sandbox().write_file(
            f"{config_dir}/SYSTEM.md",
            _single_text_resource(profile.system_prompt, "SYSTEM.md"),
        )
    if profile.append_system_prompts:
        contents = _joined_text_resources(
            profile.append_system_prompts,
            "APPEND_SYSTEM.md",
        )
        await sandbox().write_file(f"{config_dir}/APPEND_SYSTEM.md", contents)
    await _stage_resource_group(profile.skills, f"{config_dir}/skills", "SKILL.md")
    await _stage_resource_group(profile.extensions, f"{config_dir}/extensions")
    await _stage_resource_group(
        profile.prompt_templates,
        f"{config_dir}/prompts",
        ".md",
    )
    if profile.mcp_servers:
        await sandbox().write_file(
            f"{config_dir}/mcp-servers.json",
            json.dumps(profile.mcp_servers, indent=2, sort_keys=True),
        )


def _single_text_resource(resource: AgentResource, expected_name: str) -> str:
    return resource.text(expected_name)


def _joined_text_resources(
    resources: tuple[AgentResource, ...],
    expected_name: str,
) -> str:
    return (
        "\n\n".join(
            f"<!-- agent profile resource: {resource.name} -->\n"
            f"{_single_text_resource(resource, expected_name).rstrip()}"
            for resource in resources
        )
        + "\n"
    )


async def _stage_resource_group(
    resources: tuple[AgentResource, ...],
    destination_root: str,
    single_name: str | None = None,
) -> None:
    for resource in resources:
        files = resource.files()
        is_single_file = len(files) == 1 and resource.path.is_file()
        for source, relative in files:
            if is_single_file and single_name:
                suffix = single_name if single_name.startswith(".") else ""
                filename = (
                    f"{resource.name}{suffix}" if suffix else f"{resource.name}/{single_name}"
                )
                destination = f"{destination_root}/{filename}"
            elif is_single_file:
                destination = f"{destination_root}/{resource.name}{source.suffix}"
            else:
                destination = f"{destination_root}/{resource.name}/{relative.as_posix()}"
            await sandbox().write_file(destination, source.read_bytes())
            if os.access(source, os.X_OK):
                changed = await sandbox().exec(["chmod", "+x", destination])
                if not changed.success:
                    raise RuntimeError(f"could not make agent resource executable: {destination}")


async def _execute_pi(
    command: list[str],
    pi_home: str,
    timeout_seconds: int,
    telemetry: PiTelemetry,
    extra_env: dict[str, str] | None = None,
):
    started = time.perf_counter()
    try:
        result = await sandbox().exec(
            command,
            cwd="/workspace",
            env={
                "HOME": pi_home,
                "NO_COLOR": "1",
                "PI_OFFLINE": "1",
                "PI_SKIP_VERSION_CHECK": "1",
                "PI_TELEMETRY": "0",
                **(extra_env or {}),
            },
            timeout=timeout_seconds,
            timeout_retry=False,
        )
    except TimeoutError as exc:
        telemetry.wall_seconds = time.perf_counter() - started
        telemetry.stderr = f"Pi exceeded the {timeout_seconds}s case timeout"
        raise RuntimeError(telemetry.stderr) from exc
    telemetry.wall_seconds = time.perf_counter() - started
    return result


def _record_telemetry(telemetry, result, events, non_json_lines) -> None:
    telemetry.return_code = result.returncode
    telemetry.stderr = result.stderr
    telemetry.events = list(events)
    telemetry.non_json_lines = list(non_json_lines)
    summary = summarise_events(events)
    telemetry.summary = {
        "turns": summary.turns,
        "tool_calls": summary.tool_calls,
        "failed_tool_calls": summary.failed_tool_calls,
        "compactions": summary.compactions,
        "retries": summary.retries,
        "input_tokens": summary.input_tokens,
        "cached_input_tokens": summary.cached_input_tokens,
        "output_tokens": summary.output_tokens,
    }


def _final_assistant_text(events: tuple[dict[str, Any], ...]) -> str:
    for event in reversed(events):
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        text = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        if text:
            return text
    return ""
