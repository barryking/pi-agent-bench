"""Public-safe model profiles for Pi Agent Bench."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelProfile:
    name: str
    kind: str
    model: str
    runtime_env: dict[str, str]
    configuration: dict[str, Any]
    pi_direct: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, name: str, value: dict[str, Any]) -> ModelProfile:
        kind = _required_string(value, "kind")
        if kind not in {"local", "hosted"}:
            raise ValueError(f"{name}: kind must be local or hosted")
        model = _required_string(value, "model")
        runtime_env = value.get("runtime_env", {})
        configuration = value.get("configuration", {})
        pi_direct = value.get("pi_direct")
        if not isinstance(runtime_env, dict) or not all(
            isinstance(key, str)
            and key
            and isinstance(source, str)
            and source
            for key, source in runtime_env.items()
        ):
            raise ValueError(f"{name}: runtime_env must map variable names to variable names")
        if not isinstance(configuration, dict):
            raise ValueError(f"{name}: configuration must be an object")
        if pi_direct is not None:
            if not isinstance(pi_direct, dict):
                raise ValueError(f"{name}: pi_direct must be an object")
            required = {"provider", "model", "auth_file_env"}
            if set(pi_direct) != required or not all(
                isinstance(pi_direct[key], str) and pi_direct[key].strip()
                for key in required
            ):
                raise ValueError(
                    f"{name}: pi_direct must contain non-empty provider, model, "
                    "and auth_file_env strings"
                )
        return cls(
            name=name,
            kind=kind,
            model=model,
            runtime_env=dict(runtime_env),
            configuration=dict(configuration),
            pi_direct=dict(pi_direct) if pi_direct is not None else None,
        )

    def resolved_runtime_env(self, environ: Mapping[str, str]) -> dict[str, str]:
        missing = sorted(source for source in self.runtime_env.values() if not environ.get(source))
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"{self.name}: missing required environment variable(s): {names}")
        return {target: environ[source] for target, source in self.runtime_env.items()}

    def public_identity(self) -> dict[str, Any]:
        execution = (
            {
                "mode": "pi-direct",
                "provider": self.pi_direct["provider"],
                "model": self.pi_direct["model"],
                "auth_file_env": self.pi_direct["auth_file_env"],
            }
            if self.pi_direct
            else {"mode": "inspect-bridge"}
        )
        fingerprint_input = json.dumps(
            {
                "kind": self.kind,
                "model": self.model,
                "configuration": self.configuration,
                "execution": execution,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return {
            "profile": self.name,
            "kind": self.kind,
            "model": self.model,
            "configuration": self.configuration,
            "configuration_fingerprint": hashlib.sha256(
                fingerprint_input.encode()
            ).hexdigest(),
            "runtime_environment": sorted(self.runtime_env),
            "execution": execution,
        }

    def readiness_errors(self) -> list[str]:
        errors: list[str] = []
        if "replace-with" in self.model:
            errors.append(f"{self.name}: replace the placeholder model identifier")
        if _contains_placeholder(self.configuration):
            errors.append(f"{self.name}: complete all model configuration identity fields")
        return errors

    def resolved_pi_auth_file(self, environ: Mapping[str, str]) -> Path | None:
        if self.pi_direct is None:
            return None
        variable = self.pi_direct["auth_file_env"]
        value = environ.get(variable)
        if not value:
            raise ValueError(
                f"{self.name}: missing required environment variable: {variable}"
            )
        return Path(value).expanduser().resolve()


def load_profiles(path: str | Path) -> dict[str, ModelProfile]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"{source}: profile document version must be 1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"{source}: profiles must be a non-empty object")
    loaded: dict[str, ModelProfile] = {}
    for name, value in profiles.items():
        if not isinstance(name, str) or not name or not isinstance(value, dict):
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
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            raise ValueError(f"{source}:{line_number}: invalid variable name")
        target.setdefault(key, value.strip())


@contextmanager
def profile_environment(
    profile: ModelProfile, environ: dict[str, str] | None = None
) -> Iterator[None]:
    """Temporarily expose a profile using provider-standard environment names."""
    target = os.environ if environ is None else environ
    resolved = profile.resolved_runtime_env(target)
    previous = {key: target.get(key) for key in resolved}
    target.update(resolved)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                target.pop(key, None)
            else:
                target[key] = value


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item.strip()


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return "replace-with" in value
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    return False
