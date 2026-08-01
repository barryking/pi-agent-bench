import json

import pytest

from pi_agent_bench.agent_profiles import load_agent_profiles
from pi_agent_bench.model_profiles import ModelProfile
from pi_agent_bench.pi_profiles import vanilla_pi_profile


def model(name, *, mode="inspect-bridge", provider="openai-codex", direct_model=None):
    execution = (
        {
            "mode": "inspect-bridge",
            "model_args": {},
            "model_args_env": {},
            "generate_config": {},
        }
        if mode == "inspect-bridge"
        else {
            "mode": "pi-direct",
            "provider": provider,
            "model": direct_model or name,
            "auth_file_env": "PI_AUTH_FILE",
        }
    )
    return ModelProfile.from_dict(
        name,
        {
            "kind": "hosted",
            "model": f"openai/{name}",
            "execution": execution,
            "capabilities": {
                "context_tokens": 32768,
                "max_output_tokens": 8192,
                "reasoning": True,
                "input": ["text"],
            },
            "configuration": {"model_revision": f"{name}-revision"},
        },
    )


def write_profile(tmp_path, value):
    path = tmp_path / "agents.json"
    path.write_text(
        json.dumps({"version": 1, "profiles": {"test-agent": value}}),
        encoding="utf-8",
    )
    return path


def base_value():
    return {
        "description": "A complete test agent.",
        "pi_profile": "vanilla",
        "model_resources": ["local", "reviewer"],
        "default_model_resource": "local",
    }


def load(tmp_path, value=None, models=None):
    return load_agent_profiles(
        write_profile(tmp_path, value or base_value()),
        pi_profiles={"vanilla": vanilla_pi_profile()},
        model_profiles=models or {"local": model("local"), "reviewer": model("reviewer")},
    )


def test_composed_profile_preserves_resource_order_and_fingerprints_bindings(tmp_path):
    profile = load(tmp_path)["test-agent"]
    identity = profile.public_identity()
    assert [resource.name for resource in profile.model_resources] == ["local", "reviewer"]
    assert profile.default_model.name == "local"
    assert [item["profile"] for item in identity["model_resources"]] == [
        "local",
        "reviewer",
    ]

    changed = base_value()
    changed["model_resources"] = ["reviewer", "local"]
    reordered = load(tmp_path, changed)["test-agent"]
    assert (
        reordered.public_identity()["configuration_fingerprint"]
        != identity["configuration_fingerprint"]
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"pi_profile": "missing"}, "unknown Pi profile"),
        ({"model_resources": ["missing"]}, "unknown model resource"),
        ({"model_resources": []}, "non-empty list"),
        ({"model_resources": ["local", "local"]}, "must be unique"),
        ({"default_model_resource": "missing"}, "must appear"),
    ],
)
def test_rejects_invalid_component_bindings(tmp_path, change, message):
    value = base_value()
    value.update(change)
    with pytest.raises(ValueError, match=message):
        load(tmp_path, value)


def test_alias_and_default_changes_affect_composed_fingerprint(tmp_path):
    first = load(tmp_path)["test-agent"].public_identity()["configuration_fingerprint"]
    renamed_models = {"local": model("local"), "review": model("review")}
    value = base_value()
    value["model_resources"] = ["local", "review"]
    value["default_model_resource"] = "review"
    second = load(tmp_path, value, renamed_models)[
        "test-agent"
    ].public_identity()["configuration_fingerprint"]
    assert first != second


def test_rejects_duplicate_direct_pairs_and_conflicting_provider_auth(tmp_path):
    duplicate = {
        "one": model(
            "one", mode="pi-direct", provider="openai-codex", direct_model="same"
        ),
        "two": model(
            "two", mode="pi-direct", provider="openai-codex", direct_model="same"
        ),
    }
    value = base_value()
    value["model_resources"] = ["one", "two"]
    value["default_model_resource"] = "one"
    with pytest.raises(ValueError, match="duplicate direct provider/model pair"):
        load(tmp_path, value, duplicate)

    conflicting_value = duplicate["two"].public_identity()
    assert conflicting_value
    two_payload = {
        "kind": "hosted",
        "model": "openai/two",
        "execution": {
            "mode": "pi-direct",
            "provider": "openai-codex",
            "model": "two",
            "auth_file_env": "OTHER_AUTH_FILE",
        },
        "capabilities": {
            "context_tokens": 32768,
            "max_output_tokens": 8192,
            "reasoning": True,
            "input": ["text"],
        },
        "configuration": {"model_revision": "two"},
    }
    conflicting = {
        "one": duplicate["one"],
        "two": ModelProfile.from_dict("two", two_payload),
    }
    with pytest.raises(ValueError, match=r"sharing provider.*conflict"):
        load(tmp_path, value, conflicting)
