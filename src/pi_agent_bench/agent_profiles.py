"""Composed runnable agent profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_profiles import ModelProfile
from .pi_profiles import RESOURCE_NAME, PiProfile


@dataclass(frozen=True)
class AgentProfile:
    """One complete benchmarkable agent system."""

    name: str
    description: str
    pi_profile: PiProfile
    model_resources: tuple[ModelProfile, ...]
    default_model_resource: str

    @property
    def default_model(self) -> ModelProfile:
        return self.resource(self.default_model_resource)

    def resource(self, name: str) -> ModelProfile:
        for resource in self.model_resources:
            if resource.name == name:
                return resource
        raise KeyError(name)

    @property
    def has_direct_resources(self) -> bool:
        return any(resource.execution_mode == "pi-direct" for resource in self.model_resources)

    @property
    def has_bridged_resources(self) -> bool:
        return any(
            resource.execution_mode == "inspect-bridge" for resource in self.model_resources
        )

    def public_identity(self) -> dict[str, Any]:
        pi_identity = self.pi_profile.public_identity()
        resource_identities = [resource.public_identity() for resource in self.model_resources]
        fingerprint_input = {
            "pi_profile_fingerprint": pi_identity["configuration_fingerprint"],
            "model_resources": [
                {
                    "resource": resource.name,
                    "configuration_fingerprint": identity["configuration_fingerprint"],
                }
                for resource, identity in zip(
                    self.model_resources, resource_identities, strict=True
                )
            ],
            "default_model_resource": self.default_model_resource,
        }
        encoded = json.dumps(
            fingerprint_input,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return {
            "profile": self.name,
            "description": self.description,
            "pi_profile": pi_identity,
            "model_resources": resource_identities,
            "default_model_resource": self.default_model_resource,
            "configuration_fingerprint": hashlib.sha256(encoded).hexdigest(),
        }

    def readiness_errors(self) -> list[str]:
        errors = self.pi_profile.readiness_errors()
        for resource in self.model_resources:
            errors.extend(resource.readiness_errors())
        return errors


def load_agent_profiles(
    path: str | Path,
    *,
    pi_profiles: dict[str, PiProfile],
    model_profiles: dict[str, ModelProfile],
) -> dict[str, AgentProfile]:
    """Load composed profiles and resolve every component reference."""
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"{source}: agent profile document version must be 1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"{source}: profiles must be a non-empty object")
    return {
        name: _load_profile(name, value, pi_profiles, model_profiles)
        for name, value in profiles.items()
    }


def _load_profile(
    name: Any,
    value: Any,
    pi_profiles: dict[str, PiProfile],
    model_profiles: dict[str, ModelProfile],
) -> AgentProfile:
    if not isinstance(name, str) or not RESOURCE_NAME.fullmatch(name):
        raise ValueError("agent profile names must use lowercase letters, numbers, ._-")
    if not isinstance(value, dict):
        raise ValueError(f"{name}: agent profile must be an object")
    required = {"description", "pi_profile", "model_resources", "default_model_resource"}
    if set(value) != required:
        missing = sorted(required - set(value))
        unknown = sorted(set(value) - required)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise ValueError(f"{name}: invalid agent profile fields ({'; '.join(details)})")
    description = value["description"]
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{name}: description must be a non-empty string")
    pi_name = value["pi_profile"]
    if not isinstance(pi_name, str) or pi_name not in pi_profiles:
        raise ValueError(f"{name}: unknown Pi profile {pi_name!r}")
    resource_names = value["model_resources"]
    if (
        not isinstance(resource_names, list)
        or not resource_names
        or not all(
            isinstance(resource, str) and RESOURCE_NAME.fullmatch(resource)
            for resource in resource_names
        )
    ):
        raise ValueError(
            f"{name}: model_resources must be a non-empty list of Pi-safe resource names"
        )
    if len(resource_names) != len(set(resource_names)):
        raise ValueError(f"{name}: model_resources must be unique")
    unknown_resources = [resource for resource in resource_names if resource not in model_profiles]
    if unknown_resources:
        raise ValueError(
            f"{name}: unknown model resource(s): " + ", ".join(unknown_resources)
        )
    default = value["default_model_resource"]
    if not isinstance(default, str) or default not in resource_names:
        raise ValueError(f"{name}: default_model_resource must appear in model_resources")
    resources = tuple(model_profiles[resource] for resource in resource_names)
    _validate_direct_resources(name, resources)
    return AgentProfile(
        name=name,
        description=description.strip(),
        pi_profile=pi_profiles[pi_name],
        model_resources=resources,
        default_model_resource=default,
    )


def _validate_direct_resources(name: str, resources: tuple[ModelProfile, ...]) -> None:
    provider_definitions: dict[str, tuple[str, str]] = {}
    direct_pairs: set[tuple[str, str]] = set()
    for resource in resources:
        if resource.execution_mode != "pi-direct":
            continue
        provider = resource.direct_provider
        model = resource.direct_model
        auth_file_env = resource.auth_file_env
        assert provider is not None and model is not None and auth_file_env is not None
        pair = (provider, model)
        if pair in direct_pairs:
            raise ValueError(
                f"{name}: duplicate direct provider/model pair {provider}/{model}"
            )
        direct_pairs.add(pair)
        definition = (auth_file_env, resource.direct_provider_configuration_fingerprint())
        previous = provider_definitions.setdefault(provider, definition)
        if previous != definition:
            raise ValueError(
                f"{name}: direct resources sharing provider {provider!r} conflict"
            )
