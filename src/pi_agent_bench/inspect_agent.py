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

from .agent_profiles import AgentProfile
from .pi_profiles import PiProfile, PiResource
from .pi_runner import (
    PiRunConfig,
    build_command,
    build_models_config,
    model_patterns,
    model_selector,
    parse_json_events,
    summarise_direct_usage,
    summarise_events,
    unconfigured_models,
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
    direct_usage: dict[str, Any] = Field(default_factory=dict)
    direct_cost_reported_calls: int = 0
    observed_models: list[dict[str, Any]] = Field(default_factory=list)
    unattributed_assistant_calls: int = 0


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
    agent_profile: AgentProfile | None = None,
    bridged_models: dict[str, Any] | None = None,
    direct_auth_files: dict[str, str] | None = None,
    agent_runtime_env: dict[str, str] | None = None,
) -> Agent:
    """Run one complete agent profile through bridge and/or Pi-direct resources."""
    if agent_profile is None:
        raise ValueError("pi_agent requires a composed agent profile")
    selected_agent = agent_profile
    selected_pi = selected_agent.pi_profile
    configured_bridged_models = dict(bridged_models or {})
    expected_bridged = {
        resource.name
        for resource in selected_agent.model_resources
        if resource.execution_mode == "inspect-bridge"
    }
    if set(configured_bridged_models) != expected_bridged:
        raise ValueError("bridged Inspect models do not match the agent profile resources")
    configured_direct_auth_files = dict(direct_auth_files or {})
    expected_direct = {
        resource.name
        for resource in selected_agent.model_resources
        if resource.execution_mode == "pi-direct"
    }
    if set(configured_direct_auth_files) != expected_direct:
        raise ValueError("direct authentication files do not match the agent profile resources")
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
        await _stage_pi_profile(selected_pi, config_dir)
        if selected_pi.mcp_servers:
            runtime_env["PI_BENCH_MCP_CONFIG"] = f"{config_dir}/mcp-servers.json"
        await _stage_direct_auth(
            selected_agent,
            configured_direct_auth_files,
            config_dir,
        )
        guard_source = Path(__file__).with_name("pi_guard.py")
        guard_path = f"{config_dir}/pi-guard.py"
        await sandbox().write_file(
            guard_path,
            guard_source.read_text(encoding="utf-8"),
        )

        async def run_pi(port: int | None):
            await sandbox().write_file(
                f"{config_dir}/models.json",
                json.dumps(
                    build_models_config(
                        selected_agent.model_resources,
                        port=port,
                        context_tokens=sample_context,
                    )
                ),
            )
            provider, model = model_selector(selected_agent.default_model)
            thinking_level = selected_agent.default_model.thinking_level
            if thinking_level == "none":
                thinking_level = "off"
            config = PiRunConfig(
                provider=provider,
                model=model,
                timeout_seconds=sample_timeout,
                tools=selected_pi.tools,
                model_patterns=model_patterns(selected_agent.model_resources),
                context_files_enabled=True,
                skills_enabled=bool(selected_pi.skills),
                extensions_enabled=bool(selected_pi.extensions),
                prompt_templates_enabled=bool(selected_pi.prompt_templates),
                thinking_level=thinking_level,
            )
            command = build_command(config, prompt)
            telemetry.command = list(command)
            guarded_command = [
                "python3",
                guard_path,
                "--max-turns",
                str(limits.turns),
                "--max-tokens",
                str(limits.total_tokens),
                "--",
                *command,
            ]
            result = await _execute_pi(
                guarded_command,
                pi_home,
                sample_timeout,
                telemetry,
                {"OPENAI_API_KEY": "inspect", **runtime_env},
            )
            events, non_json_lines = parse_json_events(result.stdout)
            _record_telemetry(
                telemetry,
                result,
                events,
                non_json_lines,
                selected_agent,
            )
            _reject_unconfigured_models(events, selected_agent)
            if not result.success:
                detail = result.stderr.strip() or "no stderr was produced"
                if result.returncode == 75:
                    raise RuntimeError(f"Pi profile-wide limit exceeded: {detail}")
                raise RuntimeError(f"Pi exited with code {result.returncode}: {detail}")
            return events

        if configured_bridged_models:
            async with sandbox_agent_bridge(
                state,
                model_aliases=configured_bridged_models,
                forward_generation_config=False,
            ) as bridge:
                events = await run_pi(bridge.port)
                _append_direct_final_message(bridge.state, events, selected_agent)
                return bridge.state

        events = await run_pi(None)
        final_text = _final_assistant_text(events)
        if final_text:
            provider, model = model_selector(selected_agent.default_model)
            state.messages.append(
                ChatMessageAssistant(content=final_text, model=f"{provider}/{model}")
            )
        return state

    return execute


async def _stage_direct_auth(
    profile: AgentProfile,
    auth_files: dict[str, str],
    config_dir: str,
) -> None:
    staged: dict[str, Any] = {}
    for resource in profile.model_resources:
        if resource.execution_mode != "pi-direct":
            continue
        provider = resource.direct_provider
        assert provider is not None
        auth_source = Path(auth_files[resource.name])
        try:
            payload = json.loads(auth_source.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("authentication document must be an object")
            provider_auth = payload[provider]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError(
                f"could not load {provider} credentials for resource {resource.name}"
            ) from exc
        if provider in staged and staged[provider] != provider_auth:
            raise RuntimeError(
                f"direct resources supplied conflicting authentication for {provider}"
            )
        staged[provider] = provider_auth
    if not staged:
        return
    destination = f"{config_dir}/auth.json"
    await sandbox().write_file(destination, json.dumps(staged))
    changed = await sandbox().exec(["chmod", "600", destination])
    if not changed.success:
        raise RuntimeError(f"could not protect staged Pi authentication: {changed.stderr}")


def _append_direct_final_message(
    state: AgentState,
    events: tuple[dict[str, Any], ...],
    profile: AgentProfile,
) -> None:
    """Retain a final direct response that did not pass through Inspect's bridge."""
    direct_models = {
        (resource.direct_provider, resource.direct_model)
        for resource in profile.model_resources
        if resource.execution_mode == "pi-direct"
    }
    for event in reversed(events):
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        provider = message.get("provider")
        model = message.get("model")
        if (provider, model) not in direct_models:
            return
        text = _assistant_text(message)
        if text:
            state.messages.append(
                ChatMessageAssistant(content=text, model=f"{provider}/{model}")
            )
        return


async def _stage_pi_profile(profile: PiProfile, config_dir: str) -> None:
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


def _single_text_resource(resource: PiResource, expected_name: str) -> str:
    return resource.text(expected_name)


def _joined_text_resources(
    resources: tuple[PiResource, ...],
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
    resources: tuple[PiResource, ...],
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


def _record_telemetry(
    telemetry,
    result,
    events,
    non_json_lines,
    profile: AgentProfile,
) -> None:
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
    direct_models = {
        (resource.direct_provider, resource.direct_model)
        for resource in profile.model_resources
        if resource.execution_mode == "pi-direct"
    }
    direct = summarise_direct_usage(events, direct_models)
    telemetry.direct_usage = direct.aggregate
    telemetry.direct_cost_reported_calls = direct.cost_reported_calls
    telemetry.observed_models = list(direct.observed_models)
    telemetry.unattributed_assistant_calls = direct.unattributed_assistant_calls


def _reject_unconfigured_models(
    events: tuple[dict[str, Any], ...],
    profile: AgentProfile,
) -> None:
    unexpected = unconfigured_models(events, profile.model_resources)
    if unexpected:
        raise RuntimeError(
            "Pi used model(s) outside the composed agent profile: "
            + ", ".join(unexpected)
        )


def _final_assistant_text(events: tuple[dict[str, Any], ...]) -> str:
    for event in reversed(events):
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        text = _assistant_text(message)
        if text:
            return text
    return ""


def _assistant_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
