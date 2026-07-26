import json

import pytest

from pi_agent_bench.model_profiles import (
    load_env_file,
    load_profiles,
    profile_environment,
)


def write_profiles(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "dgx": {
                        "kind": "local",
                        "model": "openai/test-model",
                        "runtime_env": {
                            "OPENAI_BASE_URL": "DGX_BASE_URL",
                            "OPENAI_API_KEY": "DGX_API_KEY",
                        },
                        "configuration": {"runtime": "vllm"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_profile_resolves_secrets_only_at_runtime(tmp_path):
    profile = load_profiles(write_profiles(tmp_path))["dgx"]
    environ = {
        "DGX_BASE_URL": "http://dgx:8000/v1",
        "DGX_API_KEY": "secret",
    }

    assert "secret" not in json.dumps(profile.public_identity())
    with profile_environment(profile, environ):
        assert environ["OPENAI_BASE_URL"] == "http://dgx:8000/v1"
        assert environ["OPENAI_API_KEY"] == "secret"
    assert "OPENAI_BASE_URL" not in environ
    assert "OPENAI_API_KEY" not in environ


def test_profile_reports_missing_environment(tmp_path):
    profile = load_profiles(write_profiles(tmp_path))["dgx"]

    with pytest.raises(ValueError, match="DGX_API_KEY"):
        profile.resolved_runtime_env({"DGX_BASE_URL": "http://dgx:8000/v1"})


def test_profile_fingerprint_includes_the_exact_model(tmp_path):
    first = load_profiles(write_profiles(tmp_path))["dgx"]
    second = type(first)(
        name=first.name,
        kind=first.kind,
        model="openai/a-different-model",
        runtime_env=first.runtime_env,
        configuration=first.configuration,
    )

    assert (
        first.public_identity()["configuration_fingerprint"]
        != second.public_identity()["configuration_fingerprint"]
    )


def test_env_file_does_not_override_existing_values(tmp_path):
    path = tmp_path / ".env.local"
    path.write_text("TOKEN=file-value\nENDPOINT=http://dgx/v1\n", encoding="utf-8")
    environ = {"TOKEN": "shell-value"}

    load_env_file(path, environ)

    assert environ == {"TOKEN": "shell-value", "ENDPOINT": "http://dgx/v1"}


def test_profile_rejects_placeholder_identity():
    from pi_agent_bench.model_profiles import ModelProfile

    profile = ModelProfile(
        name="hosted-quality",
        kind="hosted",
        model="openai/replace-with-model",
        runtime_env={},
        configuration={"model_revision": "replace-with-revision"},
    )

    assert len(profile.readiness_errors()) == 2


def test_profile_resolves_pi_direct_auth_without_exposing_credentials(tmp_path):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"openai-codex":{"type":"oauth","access":"secret"}}')
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "subscription": {
                        "kind": "hosted",
                        "model": "openai-codex/gpt-5.6-sol",
                        "runtime_env": {},
                        "pi_direct": {
                            "provider": "openai-codex",
                            "model": "gpt-5.6-sol",
                            "auth_file_env": "PI_AUTH_FILE",
                        },
                        "configuration": {"provider": "openai-codex"},
                    }
                },
            }
        )
    )

    profile = load_profiles(profiles)["subscription"]

    assert profile.resolved_pi_auth_file({"PI_AUTH_FILE": str(auth_file)}) == auth_file
    assert "secret" not in json.dumps(profile.public_identity())
    assert profile.public_identity()["execution"]["mode"] == "pi-direct"
