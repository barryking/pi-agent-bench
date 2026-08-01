"""Public-safe reusable model resource definitions."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESOURCE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_MARKERS = ("apikey", "api_key", "password", "secret", "credential")


@dataclass(frozen=True)
class ModelProfile:
    """One concrete inference resource that can be bound into an agent profile."""

    name: str
    kind: str
    model: str
    execution: dict[str, Any]
    capabilities: dict[str, Any]
    configuration: dict[str, Any]

    @classmethod
    def from_dict(cls, name: str, value: dict[str, Any]) -> ModelProfile:
        if not RESOURCE_NAME.fullmatch(name):
            raise ValueError(
                f"{name!r}: model profile names must match [a-z0-9][a-z0-9._-]*"
            )
        allowed = {"kind", "model", "execution", "capabilities", "configuration"}
        if set(value) != allowed:
            unknown = sorted(set(value) - allowed)
            missing = sorted(allowed - set(value))
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unknown:
                details.append("unknown " + ", ".join(unknown))
            raise ValueError(f"{name}: invalid model profile fields ({'; '.join(details)})")
        kind = _required_string(value, "kind", name)
        if kind not in {"local", "hosted"}:
            raise ValueError(f"{name}: kind must be local or hosted")
        model = _required_string(value, "model", name)
        execution = value["execution"]
        capabilities = value["capabilities"]
        configuration = value["configuration"]
        if not isinstance(execution, dict):
            raise ValueError(f"{name}: execution must be an object")
        if not isinstance(capabilities, dict):
            raise ValueError(f"{name}: capabilities must be an object")
        if not isinstance(configuration, dict):
            raise ValueError(f"{name}: configuration must be an object")
        _validate_execution(name, execution)
        _validate_capabilities(name, capabilities)
        _validate_public_json(name, "configuration", configuration)
        return cls(
            name=name,
            kind=kind,
            model=model,
            execution=_json_copy(execution),
            capabilities=_json_copy(capabilities),
            configuration=_json_copy(configuration),
        )

    @property
    def execution_mode(self) -> str:
        return self.execution["mode"]

    @property
    def direct_provider(self) -> str | None:
        value = self.execution.get("provider")
        return value if isinstance(value, str) else None

    @property
    def direct_model(self) -> str | None:
        value = self.execution.get("model")
        return value if isinstance(value, str) else None

    @property
    def auth_file_env(self) -> str | None:
        value = self.execution.get("auth_file_env")
        return value if isinstance(value, str) else None

    @property
    def thinking_level(self) -> str | None:
        """Return the Pi runtime thinking control, with schema-1 compatibility."""
        value = self.execution.get("thinking_level")
        if value is None:
            value = self.configuration.get("thinking_level")
        return value if isinstance(value, str) and value else None

    @property
    def context_tokens(self) -> int:
        return int(self.capabilities["context_tokens"])

    @property
    def max_output_tokens(self) -> int:
        return int(self.capabilities["max_output_tokens"])

    def capped_capabilities(self, case_context_tokens: int) -> dict[str, Any]:
        context = min(self.context_tokens, case_context_tokens)
        return {
            **self.capabilities,
            "context_tokens": context,
            "max_output_tokens": min(self.max_output_tokens, context),
        }

    def resolved_model_args(self, environ: Mapping[str, str]) -> dict[str, Any]:
        if self.execution_mode != "inspect-bridge":
            return {}
        resolved = dict(self.execution["model_args"])
        missing = sorted(
            source
            for source in self.execution["model_args_env"].values()
            if not environ.get(source)
        )
        if missing:
            raise ValueError(
                f"{self.name}: missing required environment variable(s): "
                + ", ".join(missing)
            )
        resolved.update(
            {
                argument: environ[source]
                for argument, source in self.execution["model_args_env"].items()
            }
        )
        return resolved

    def resolved_pi_auth_file(self, environ: Mapping[str, str]) -> Path | None:
        if self.execution_mode != "pi-direct":
            return None
        variable = self.auth_file_env
        assert variable is not None
        value = environ.get(variable)
        if not value:
            raise ValueError(f"{self.name}: missing required environment variable: {variable}")
        return Path(value).expanduser().resolve()

    def create_inspect_model(self, environ: Mapping[str, str]):
        if self.execution_mode != "inspect-bridge":
            raise ValueError(f"{self.name}: Pi-direct resources cannot construct Inspect models")
        from inspect_ai.model import GenerateConfig, get_model

        return get_model(
            self.model,
            config=GenerateConfig(**self.execution["generate_config"]),
            memoize=False,
            **self.resolved_model_args(environ),
        )

    def public_identity(self) -> dict[str, Any]:
        execution = _json_copy(self.execution)
        if self.execution_mode == "inspect-bridge":
            execution["model_args_environment"] = dict(execution.pop("model_args_env"))
        encoded = json.dumps(
            {
                "kind": self.kind,
                "model": self.model,
                "execution": execution,
                "capabilities": self.capabilities,
                "configuration": self.configuration,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return {
            "profile": self.name,
            "kind": self.kind,
            "model": self.model,
            "execution": execution,
            "capabilities": self.capabilities,
            "configuration": self.configuration,
            "configuration_fingerprint": hashlib.sha256(encoded).hexdigest(),
        }

    def direct_provider_configuration_fingerprint(self) -> str:
        if self.execution_mode != "pi-direct":
            raise ValueError("only Pi-direct resources have direct provider configuration")
        encoded = json.dumps(
            {
                "provider": self.direct_provider,
                "auth_file_env": self.auth_file_env,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def readiness_errors(self) -> list[str]:
        errors: list[str] = []
        if "replace-with" in self.model:
            errors.append(f"{self.name}: replace the placeholder model identifier")
        if _contains_placeholder(self.configuration):
            errors.append(f"{self.name}: complete all model configuration identity fields")
        return errors


def load_profiles(path: str | Path) -> dict[str, ModelProfile]:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"{source}: profile document version must be 1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"{source}: profiles must be a non-empty object")
    loaded: dict[str, ModelProfile] = {}
    for name, value in profiles.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise ValueError(f"{source}: every profile must be a named object")
        loaded[name] = ModelProfile.from_dict(name, value)
    return loaded


def load_env_file(path: str | Path, environ: dict[str, str] | None = None) -> None:
    """Load a small KEY=VALUE file without overriding existing environment values."""
    target = os.environ if environ is None else environ
    source = Path(path)
    if not source.exists():
        raise ValueError(f"environment file does not exist: {source}")
    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{source}:{line_number}: expected KEY=VALUE")
        key, item = line.split("=", 1)
        key = key.strip()
        if not ENVIRONMENT_NAME.fullmatch(key):
            raise ValueError(f"{source}:{line_number}: invalid variable name")
        target.setdefault(key, item.strip())


def _validate_execution(name: str, value: dict[str, Any]) -> None:
    mode = value.get("mode")
    if mode == "inspect-bridge":
        required = {"mode", "model_args", "model_args_env", "generate_config"}
        allowed = required | {"thinking_level"}
        if not required.issubset(value) or not set(value).issubset(allowed):
            raise ValueError(
                f"{name}: inspect-bridge execution needs mode, model_args, "
                "model_args_env, and generate_config; thinking_level is optional"
            )
        model_args = value["model_args"]
        model_args_env = value["model_args_env"]
        generate_config = value["generate_config"]
        if not isinstance(model_args, dict):
            raise ValueError(f"{name}: execution.model_args must be an object")
        if not isinstance(model_args_env, dict) or not all(
            isinstance(argument, str)
            and argument
            and isinstance(source, str)
            and ENVIRONMENT_NAME.fullmatch(source)
            for argument, source in model_args_env.items()
        ):
            raise ValueError(
                f"{name}: execution.model_args_env must map constructor arguments "
                "to environment variable names"
            )
        overlap = sorted(set(model_args).intersection(model_args_env))
        if overlap:
            raise ValueError(
                f"{name}: model arguments cannot be both public and environment-backed: "
                + ", ".join(overlap)
            )
        if not isinstance(generate_config, dict):
            raise ValueError(f"{name}: execution.generate_config must be an object")
        _validate_public_json(name, "execution.model_args", model_args)
        _validate_public_json(name, "execution.generate_config", generate_config)
        _validate_thinking_level(name, value)
        return
    if mode == "pi-direct":
        required = {"mode", "provider", "model", "auth_file_env"}
        allowed = required | {"thinking_level"}
        if not required.issubset(value) or not set(value).issubset(allowed):
            raise ValueError(
                f"{name}: pi-direct execution needs mode, provider, model, "
                "and auth_file_env; thinking_level is optional"
            )
        for key in ("provider", "model"):
            item = value[key]
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{name}: execution.{key} must be a non-empty string")
        auth_file_env = value["auth_file_env"]
        if not isinstance(auth_file_env, str) or not ENVIRONMENT_NAME.fullmatch(auth_file_env):
            raise ValueError(
                f"{name}: execution.auth_file_env must name a host environment variable"
            )
        _validate_thinking_level(name, value)
        return
    raise ValueError(f"{name}: execution.mode must be inspect-bridge or pi-direct")


def _validate_thinking_level(name: str, execution: dict[str, Any]) -> None:
    value = execution.get("thinking_level")
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name}: execution.thinking_level must be a non-empty string")


def _validate_capabilities(name: str, value: dict[str, Any]) -> None:
    required = {"context_tokens", "max_output_tokens", "reasoning", "input"}
    if set(value) != required:
        raise ValueError(
            f"{name}: capabilities needs exactly context_tokens, max_output_tokens, "
            "reasoning, and input"
        )
    context = value["context_tokens"]
    output = value["max_output_tokens"]
    if (
        not isinstance(context, int)
        or isinstance(context, bool)
        or context < 1
        or not isinstance(output, int)
        or isinstance(output, bool)
        or output < 1
    ):
        raise ValueError(f"{name}: capability token limits must be positive integers")
    if output > context:
        raise ValueError(f"{name}: max_output_tokens cannot exceed context_tokens")
    if not isinstance(value["reasoning"], bool):
        raise ValueError(f"{name}: capabilities.reasoning must be boolean")
    inputs = value["input"]
    if (
        not isinstance(inputs, list)
        or not inputs
        or not all(isinstance(item, str) and item in {"text", "image"} for item in inputs)
        or len(inputs) != len(set(inputs))
    ):
        raise ValueError(f"{name}: capabilities.input must contain unique text/image values")


def _validate_public_json(name: str, field: str, value: Any) -> None:
    for key, item in _walk_items(value):
        folded = re.sub(r"[^a-z0-9]", "", key.casefold())
        secret_token_key = folded.endswith("token") and not folded.endswith("tokens")
        if secret_token_key or any(
            marker.replace("_", "") in folded for marker in SECRET_MARKERS
        ):
            raise ValueError(
                f"{name}: {field} cannot contain secret-like field {key!r}; "
                "use a named environment variable"
            )
        if not isinstance(item, (dict, list, str, int, float, bool)) and item is not None:
            raise ValueError(f"{name}: {field}.{key} is not JSON-compatible")


def _walk_items(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("public configuration keys must be non-empty strings")
            yield key, item
            yield from _walk_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_items(item)


def _required_string(value: dict[str, Any], key: str, name: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{name}: {key} must be a non-empty string")
    return item.strip()


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return "replace-with" in value
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    return False


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))
