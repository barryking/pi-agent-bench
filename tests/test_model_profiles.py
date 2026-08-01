import json

import pytest

from pi_agent_bench.model_profiles import ModelProfile, load_env_file, load_profiles


def bridged_value(**overrides):
    value = {
        "kind": "local",
        "model": "openai/example",
        "execution": {
            "mode": "inspect-bridge",
            "model_args": {"timeout": 30},
            "model_args_env": {
                "base_url": "MODEL_BASE_URL",
                "api_key": "MODEL_API_KEY",
            },
            "generate_config": {"temperature": 0},
        },
        "capabilities": {
            "context_tokens": 131072,
            "max_output_tokens": 32768,
            "reasoning": True,
            "input": ["text"],
        },
        "configuration": {"weights": "example@revision", "runtime": "vllm"},
    }
    value.update(overrides)
    return value


def direct_value():
    return {
        "kind": "hosted",
        "model": "openai-codex/example",
        "execution": {
            "mode": "pi-direct",
            "provider": "openai-codex",
            "model": "example",
            "auth_file_env": "PI_AUTH_FILE",
        },
        "capabilities": {
            "context_tokens": 131072,
            "max_output_tokens": 32768,
            "reasoning": True,
            "input": ["text", "image"],
        },
        "configuration": {"billing": "subscription", "model_revision": "snapshot"},
    }


def write_profiles(tmp_path, profiles):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"version": 1, "profiles": profiles}), encoding="utf-8")
    return path


def test_bridged_profile_resolves_constructor_arguments_without_process_mutation(tmp_path):
    profile = load_profiles(write_profiles(tmp_path, {"local": bridged_value()}))["local"]
    environ = {
        "MODEL_BASE_URL": "http://one.invalid/v1",
        "MODEL_API_KEY": "private",
    }

    assert profile.resolved_model_args(environ) == {
        "timeout": 30,
        "base_url": "http://one.invalid/v1",
        "api_key": "private",
    }
    identity = profile.public_identity()
    assert "private" not in json.dumps(identity)
    assert identity["execution"]["model_args_environment"]["api_key"] == "MODEL_API_KEY"


def test_two_bridged_resources_construct_distinct_inspect_models(tmp_path, monkeypatch):
    values = {
        "first": bridged_value(model="openai/first"),
        "second": bridged_value(model="openai/second"),
    }
    profiles = load_profiles(write_profiles(tmp_path, values))
    calls = []

    def fake_get_model(model, **kwargs):
        calls.append((model, kwargs))
        return object()

    monkeypatch.setattr("inspect_ai.model.get_model", fake_get_model)
    profiles["first"].create_inspect_model(
        {"MODEL_BASE_URL": "http://first/v1", "MODEL_API_KEY": "first-key"}
    )
    profiles["second"].create_inspect_model(
        {"MODEL_BASE_URL": "http://second/v1", "MODEL_API_KEY": "second-key"}
    )

    assert calls[0][0] == "openai/first"
    assert calls[0][1]["base_url"] == "http://first/v1"
    assert calls[1][0] == "openai/second"
    assert calls[1][1]["base_url"] == "http://second/v1"
    assert calls[0][1]["api_key"] != calls[1][1]["api_key"]


def test_direct_profile_resolves_only_its_named_authentication_file(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text("{}", encoding="utf-8")
    profile = ModelProfile.from_dict("subscription", direct_value())

    assert profile.resolved_pi_auth_file({"PI_AUTH_FILE": str(auth)}) == auth.resolve()
    assert profile.resolved_model_args({}) == {}


def test_thinking_level_is_execution_identity_with_legacy_compatibility():
    current = direct_value()
    current["execution"]["thinking_level"] = "high"
    profile = ModelProfile.from_dict("subscription", current)
    assert profile.thinking_level == "high"
    assert profile.public_identity()["execution"]["thinking_level"] == "high"

    legacy = direct_value()
    legacy["configuration"]["thinking_level"] = "medium"
    assert ModelProfile.from_dict("legacy", legacy).thinking_level == "medium"


@pytest.mark.parametrize("name", ["bad/name", "bad name", "OpenAI"])
def test_model_resource_names_are_pi_safe(name):
    with pytest.raises(ValueError, match="model profile names"):
        ModelProfile.from_dict(name, bridged_value())


@pytest.mark.parametrize("field", ["api_key", "password", "access_token"])
def test_secret_like_public_model_fields_are_rejected(field):
    value = bridged_value()
    value["configuration"][field] = "not-public"
    with pytest.raises(ValueError, match="cannot contain secret-like"):
        ModelProfile.from_dict("resource", value)


def test_unknown_old_execution_fields_are_rejected():
    value = bridged_value()
    value["runtime_env"] = {}
    with pytest.raises(ValueError, match="invalid model profile fields"):
        ModelProfile.from_dict("resource", value)


def test_case_context_caps_each_catalog_capability():
    profile = ModelProfile.from_dict("resource", bridged_value())
    assert profile.capped_capabilities(65536) == {
        "context_tokens": 65536,
        "max_output_tokens": 32768,
        "reasoning": True,
        "input": ["text"],
    }


def test_env_file_does_not_override_existing_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TOKEN=file\nSECOND=value\n", encoding="utf-8")
    environ = {"TOKEN": "process"}
    load_env_file(env, environ)
    assert environ == {"TOKEN": "process", "SECOND": "value"}
