"""Validated, reproducible Pi agent profiles."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .pi_runner import TrustMode

Phase = Literal["planning", "coding"]
RESOURCE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TOOL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESOURCE_KINDS = (
    "context_files",
    "skills",
    "extensions",
    "prompt_templates",
    "append_system_prompts",
)
FORBIDDEN_SETTING_KEYS = {
    "defaultmodel",
    "defaultprovider",
    "defaultthinkinglevel",
    "extensions",
    "packages",
    "prompts",
    "skills",
    "themes",
}
SECRET_MARKERS = ("apikey", "password", "secret", "credential")
PROTECTED_RUNTIME_ENV = {
    "HOME",
    "NO_COLOR",
    "PI_BENCH_MCP_CONFIG",
    "PI_CODING_AGENT_DIR",
    "PI_CODING_AGENT_SESSION_DIR",
    "PI_OFFLINE",
    "PI_SKIP_VERSION_CHECK",
    "PI_TELEMETRY",
}


@dataclass(frozen=True)
class AgentResource:
    """One explicitly selected file or directory."""

    name: str
    path: Path

    def files(self) -> tuple[tuple[Path, Path], ...]:
        """Return source files and stable relative names."""
        if self.path.is_symlink():
            raise ValueError(f"{self.name}: resource paths cannot be symbolic links")
        if self.path.is_file():
            return ((self.path, Path(self.path.name)),)
        if not self.path.is_dir():
            raise ValueError(f"{self.name}: resource does not exist: {self.path}")
        files: list[tuple[Path, Path]] = []
        for source in sorted(self.path.rglob("*")):
            if source.is_symlink():
                raise ValueError(
                    f"{self.name}: resource trees cannot contain symbolic links: {source}"
                )
            if source.is_file():
                files.append((source, source.relative_to(self.path)))
        if not files:
            raise ValueError(f"{self.name}: resource directory is empty: {self.path}")
        return tuple(files)

    def public_identity(self) -> dict[str, Any]:
        fingerprint = hashlib.sha256()
        files = self.files()
        for source, relative in files:
            fingerprint.update(relative.as_posix().encode())
            fingerprint.update(b"\0")
            fingerprint.update(source.read_bytes())
            fingerprint.update(b"\0")
            fingerprint.update(b"x" if os.access(source, os.X_OK) else b"-")
        return {
            "name": self.name,
            "sha256": fingerprint.hexdigest(),
            "files": len(files),
        }

    def text(self, expected_name: str) -> str:
        """Read one UTF-8 context or prompt resource."""
        files = self.files()
        if len(files) != 1:
            raise ValueError(
                f"{self.name}: {expected_name} resource must contain one text file"
            )
        try:
            return files[0][0].read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"{self.name}: prompt and context files must be UTF-8"
            ) from exc


@dataclass(frozen=True)
class AgentProfile:
    """One exact Pi setup, separate from the inference model setup."""

    name: str
    description: str
    trust_mode: TrustMode
    tools: dict[str, tuple[str, ...]]
    runtime_env: dict[str, str]
    settings: dict[str, Any]
    context_files: tuple[AgentResource, ...] = ()
    system_prompt: AgentResource | None = None
    append_system_prompts: tuple[AgentResource, ...] = ()
    skills: tuple[AgentResource, ...] = ()
    extensions: tuple[AgentResource, ...] = ()
    prompt_templates: tuple[AgentResource, ...] = ()
    mcp_servers: tuple[dict[str, Any], ...] = ()

    def tools_for(self, phase: Phase) -> tuple[str, ...]:
        return self.tools[phase]

    def resolved_runtime_env(self, environ: Mapping[str, str]) -> dict[str, str]:
        missing = sorted(
            source for source in self.runtime_env.values() if not environ.get(source)
        )
        if missing:
            raise ValueError(
                f"{self.name}: missing required agent environment variable(s): "
                + ", ".join(missing)
            )
        return {target: environ[source] for target, source in self.runtime_env.items()}

    def public_identity(self) -> dict[str, Any]:
        configuration = {
            "trust_mode": self.trust_mode,
            "tools": {
                phase: list(tools) for phase, tools in sorted(self.tools.items())
            },
            "runtime_environment": sorted(self.runtime_env),
            "settings": self.settings,
            "resources": {
                kind: [
                    resource.public_identity()
                    for resource in getattr(self, kind)
                ]
                for kind in RESOURCE_KINDS
            },
            "system_prompt": (
                self.system_prompt.public_identity() if self.system_prompt else None
            ),
            "mcp_servers": list(self.mcp_servers),
        }
        encoded = json.dumps(
            configuration,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return {
            "profile": self.name,
            "description": self.description,
            "configuration": configuration,
            "configuration_fingerprint": hashlib.sha256(encoded).hexdigest(),
        }

    def readiness_errors(self) -> list[str]:
        errors: list[str] = []
        text_resources = [
            *((resource, "AGENTS.md") for resource in self.context_files),
            *((resource, "APPEND_SYSTEM.md") for resource in self.append_system_prompts),
        ]
        if self.system_prompt:
            text_resources.append((self.system_prompt, "SYSTEM.md"))
        for resource, expected_name in text_resources:
            try:
                resource.text(expected_name)
            except ValueError as exc:
                errors.append(str(exc))
        resources = [
            *self.skills,
            *self.extensions,
            *self.prompt_templates,
        ]
        for resource in resources:
            try:
                resource.files()
            except ValueError as exc:
                errors.append(str(exc))
        extension_names = {resource.name for resource in self.extensions}
        enabled_tools = set(self.tools["planning"]) | set(self.tools["coding"])
        for server in self.mcp_servers:
            if server["extension"] not in extension_names:
                errors.append(
                    f"{self.name}: MCP server {server['name']!r} names missing "
                    f"extension {server['extension']!r}"
                )
            missing_tools = sorted(set(server["tools"]) - enabled_tools)
            if missing_tools:
                errors.append(
                    f"{self.name}: MCP server {server['name']!r} has tools that "
                    "are not enabled for planning or coding: "
                    + ", ".join(missing_tools)
                )
        return errors


def vanilla_agent_profile() -> AgentProfile:
    """Return the clean baseline used when old logs have no agent identity."""
    return AgentProfile(
        name="vanilla",
        description="Clean Pi with no personal or project extras.",
        trust_mode="no-approve",
        tools={
            "planning": ("read", "grep", "find", "ls"),
            "coding": ("read", "bash", "edit", "write", "grep", "find", "ls"),
        },
        runtime_env={},
        settings={},
    )


def load_agent_profiles(path: str | Path) -> dict[str, AgentProfile]:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"{source}: agent profile document version must be 1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"{source}: profiles must be a non-empty object")
    return {
        name: _load_profile(name, value, source.parent)
        for name, value in profiles.items()
    }


def _load_profile(name: Any, value: Any, root: Path) -> AgentProfile:
    if not isinstance(name, str) or not RESOURCE_NAME.fullmatch(name):
        raise ValueError("agent profile names must use lowercase letters, numbers, ._-")
    if not isinstance(value, dict):
        raise ValueError(f"{name}: agent profile must be an object")
    allowed = {
        "description",
        "trust_mode",
        "tools",
        "runtime_env",
        "settings",
        *RESOURCE_KINDS,
        "system_prompt",
        "mcp_servers",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{name}: unknown agent profile fields: {', '.join(sorted(unknown))}")
    description = value.get("description", "")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{name}: description must be a non-empty string")
    trust_mode = value.get("trust_mode", "no-approve")
    if trust_mode not in {"approve", "no-approve"}:
        raise ValueError(f"{name}: trust_mode must be approve or no-approve")
    tools = _tools(name, value.get("tools"))
    runtime_env = _runtime_env(name, value.get("runtime_env", {}))
    settings = value.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError(f"{name}: settings must be an object")
    _validate_settings(name, settings)
    resources = {
        kind: _resources(name, kind, value.get(kind, []), root)
        for kind in RESOURCE_KINDS
    }
    system_prompt_value = value.get("system_prompt")
    system_prompt = (
        _resource(name, "system_prompt", system_prompt_value, root)
        if system_prompt_value is not None
        else None
    )
    mcp_servers = _mcp_servers(name, value.get("mcp_servers", []))
    return AgentProfile(
        name=name,
        description=description.strip(),
        trust_mode=trust_mode,
        tools=tools,
        runtime_env=runtime_env,
        settings=dict(settings),
        context_files=resources["context_files"],
        system_prompt=system_prompt,
        append_system_prompts=resources["append_system_prompts"],
        skills=resources["skills"],
        extensions=resources["extensions"],
        prompt_templates=resources["prompt_templates"],
        mcp_servers=mcp_servers,
    )


def _tools(name: str, value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict) or set(value) != {"planning", "coding"}:
        raise ValueError(f"{name}: tools must contain planning and coding lists")
    result: dict[str, tuple[str, ...]] = {}
    for phase in ("planning", "coding"):
        tools = value[phase]
        if (
            not isinstance(tools, list)
            or not tools
            or not all(isinstance(tool, str) and TOOL_NAME.fullmatch(tool) for tool in tools)
            or len(tools) != len(set(tools))
        ):
            raise ValueError(
                f"{name}: tools.{phase} must contain unique, non-empty tool names"
            )
        result[phase] = tuple(tools)
    return result


def _runtime_env(name: str, value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(target, str)
        and ENVIRONMENT_NAME.fullmatch(target)
        and isinstance(source, str)
        and ENVIRONMENT_NAME.fullmatch(source)
        for target, source in value.items()
    ):
        raise ValueError(
            f"{name}: runtime_env must map container variable names to host variable names"
        )
    protected = sorted(PROTECTED_RUNTIME_ENV.intersection(value))
    if protected:
        raise ValueError(
            f"{name}: runtime_env cannot replace protected variable(s): "
            + ", ".join(protected)
        )
    return dict(value)


def _resources(
    profile: str,
    kind: str,
    values: Any,
    root: Path,
) -> tuple[AgentResource, ...]:
    if not isinstance(values, list):
        raise ValueError(f"{profile}: {kind} must be a list")
    resources = tuple(_resource(profile, kind, value, root) for value in values)
    names = [resource.name for resource in resources]
    if len(names) != len(set(names)):
        raise ValueError(f"{profile}: {kind} resource names must be unique")
    return resources


def _resource(
    profile: str,
    kind: str,
    value: Any,
    root: Path,
) -> AgentResource:
    if not isinstance(value, dict) or set(value) != {"name", "path"}:
        raise ValueError(f"{profile}: every {kind} resource needs name and path")
    name = value["name"]
    path = value["path"]
    if not isinstance(name, str) or not RESOURCE_NAME.fullmatch(name):
        raise ValueError(f"{profile}: invalid {kind} resource name")
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{profile}: {kind}.{name} path must be a non-empty string")
    requested = Path(path).expanduser()
    absolute = requested.absolute() if requested.is_absolute() else (root / requested).absolute()
    return AgentResource(name=name, path=absolute)


def _mcp_servers(profile: str, values: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(values, list):
        raise ValueError(f"{profile}: mcp_servers must be a list")
    servers: list[dict[str, Any]] = []
    names: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            raise ValueError(f"{profile}: every MCP server must be an object")
        required = {"name", "extension", "transport", "server", "tools"}
        if set(value) != required:
            raise ValueError(
                f"{profile}: every MCP server needs exactly "
                "name, extension, transport, server, and tools"
            )
        name = value["name"]
        extension = value["extension"]
        transport = value["transport"]
        server = value["server"]
        tools = value["tools"]
        if not isinstance(name, str) or not RESOURCE_NAME.fullmatch(name):
            raise ValueError(f"{profile}: invalid MCP server name")
        if name in names:
            raise ValueError(f"{profile}: MCP server names must be unique")
        if not isinstance(extension, str) or not RESOURCE_NAME.fullmatch(extension):
            raise ValueError(f"{profile}: MCP server extension must name a profile extension")
        if transport not in {"stdio", "http", "sse"}:
            raise ValueError(f"{profile}: MCP transport must be stdio, http, or sse")
        if not isinstance(server, str) or not RESOURCE_NAME.fullmatch(server):
            raise ValueError(
                f"{profile}: MCP server identity must be a public-safe name"
            )
        if (
            not isinstance(tools, list)
            or not tools
            or not all(isinstance(tool, str) and TOOL_NAME.fullmatch(tool) for tool in tools)
            or len(tools) != len(set(tools))
        ):
            raise ValueError(
                f"{profile}: MCP tools must be a unique, non-empty tool-name list"
            )
        names.add(name)
        servers.append(dict(value))
    return tuple(servers)


def _validate_settings(profile: str, settings: dict[str, Any]) -> None:
    for key, item in _walk_items(settings):
        folded = key.casefold()
        if folded in FORBIDDEN_SETTING_KEYS:
            raise ValueError(
                f"{profile}: settings.{key} belongs in the model or resource profile"
            )
        if _looks_like_secret_key(key):
            raise ValueError(
                f"{profile}: settings cannot contain secrets; use runtime_env"
            )
        if not isinstance(item, (dict, list, str, int, float, bool)) and item is not None:
            raise ValueError(f"{profile}: settings.{key} is not JSON-compatible")


def _walk_items(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("agent settings keys must be non-empty strings")
            yield key, item
            yield from _walk_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_items(item)


def _looks_like_secret_key(key: str) -> bool:
    folded = re.sub(r"[^a-z0-9]", "", key.casefold())
    return any(marker in folded for marker in SECRET_MARKERS) or folded.endswith(
        "token"
    )
