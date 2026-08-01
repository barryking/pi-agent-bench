import json
from pathlib import Path

import pytest

from pi_agent_bench.pi_profiles import load_pi_profiles

ROOT = Path(__file__).resolve().parents[1]


def write_profiles(path, profile):
    path.write_text(
        json.dumps({"version": 1, "profiles": {"test-agent": profile}}),
        encoding="utf-8",
    )


def base_profile():
    return {
        "description": "A test agent.",
        "tools": ["read", "bash", "edit"],
        "runtime_env": {},
        "settings": {},
        "context_files": [],
        "system_prompt": None,
        "append_system_prompts": [],
        "skills": [],
        "extensions": [],
        "prompt_templates": [],
        "mcp_servers": [],
    }


def test_loads_and_fingerprints_selected_resources(tmp_path):
    context = tmp_path / "AGENTS.md"
    context.write_text("Write a test before changing code.\n", encoding="utf-8")
    profile = base_profile()
    profile["context_files"] = [{"name": "test-first", "path": "AGENTS.md"}]
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)

    loaded = load_pi_profiles(config)["test-agent"]
    identity = loaded.public_identity()

    assert loaded.tools == ("read", "bash", "edit")
    assert identity["profile"] == "test-agent"
    assert identity["configuration"]["resources"]["context_files"][0]["files"] == 1
    assert str(tmp_path) not in json.dumps(identity)


def test_resource_change_changes_profile_fingerprint(tmp_path):
    context = tmp_path / "AGENTS.md"
    context.write_text("First version.\n", encoding="utf-8")
    profile = base_profile()
    profile["context_files"] = [{"name": "rules", "path": "AGENTS.md"}]
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)
    first = load_pi_profiles(config)["test-agent"].public_identity()

    context.write_text("Second version.\n", encoding="utf-8")
    second = load_pi_profiles(config)["test-agent"].public_identity()

    assert first["configuration_fingerprint"] != second["configuration_fingerprint"]


def test_rejects_symbolic_link_resources(tmp_path):
    real = tmp_path / "real.md"
    real.write_text("Hidden behind a link.\n", encoding="utf-8")
    linked = tmp_path / "linked.md"
    linked.symlink_to(real)
    profile = base_profile()
    profile["context_files"] = [{"name": "linked", "path": "linked.md"}]
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)

    loaded = load_pi_profiles(config)["test-agent"]

    assert loaded.readiness_errors() == ["linked: resource paths cannot be symbolic links"]


def test_runtime_environment_records_names_but_not_secret_values(tmp_path):
    profile = base_profile()
    profile["runtime_env"] = {"MY_TOOL_TOKEN": "PRIVATE_AGENT_TOKEN"}
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)
    loaded = load_pi_profiles(config)["test-agent"]

    assert loaded.resolved_runtime_env({"PRIVATE_AGENT_TOKEN": "do-not-record-this"}) == {
        "MY_TOOL_TOKEN": "do-not-record-this"
    }
    assert "do-not-record-this" not in json.dumps(loaded.public_identity())
    with pytest.raises(ValueError, match="PRIVATE_AGENT_TOKEN"):
        loaded.resolved_runtime_env({})


def test_runtime_environment_cannot_replace_the_isolated_pi_home(tmp_path):
    profile = base_profile()
    profile["runtime_env"] = {"HOME": "PRIVATE_HOME"}
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)

    with pytest.raises(ValueError, match="protected variable"):
        load_pi_profiles(config)


def test_rejects_mcp_server_without_its_extension(tmp_path):
    profile = base_profile()
    profile["mcp_servers"] = [
        {
            "name": "issues",
            "extension": "mcp-client",
            "transport": "http",
            "server": "company-issues",
            "tools": ["issue_search"],
        }
    ]
    profile["tools"].append("issue_search")
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)

    loaded = load_pi_profiles(config)["test-agent"]

    assert loaded.readiness_errors() == [
        "test-agent: MCP server 'issues' names missing extension 'mcp-client'"
    ]


def test_rejects_mcp_tools_that_pi_cannot_use(tmp_path):
    extension = tmp_path / "mcp-client.ts"
    extension.write_text("export default function () {}\n", encoding="utf-8")
    profile = base_profile()
    profile["extensions"] = [{"name": "mcp-client", "path": "mcp-client.ts"}]
    profile["mcp_servers"] = [
        {
            "name": "issues",
            "extension": "mcp-client",
            "transport": "http",
            "server": "company-issues",
            "tools": ["issue_search"],
        }
    ]
    config = tmp_path / "profiles.json"
    write_profiles(config, profile)

    loaded = load_pi_profiles(config)["test-agent"]

    assert loaded.readiness_errors() == [
        "test-agent: MCP server 'issues' has tools that are not enabled for "
        "this outcome: issue_search"
    ]


def test_rejects_model_choices_and_secrets_in_agent_settings(tmp_path):
    config = tmp_path / "profiles.json"
    profile = base_profile()
    profile["settings"] = {"defaultModel": "gpt-example"}
    write_profiles(config, profile)
    with pytest.raises(ValueError, match="belongs in the model"):
        load_pi_profiles(config)

    profile["settings"] = {"toolToken": "never-put-secrets-here"}
    write_profiles(config, profile)
    with pytest.raises(ValueError, match="cannot contain secrets"):
        load_pi_profiles(config)


def test_allows_non_secret_token_budget_settings(tmp_path):
    config = tmp_path / "profiles.json"
    profile = base_profile()
    profile["settings"] = {"compaction": {"reserveTokens": 12000}}
    write_profiles(config, profile)

    loaded = load_pi_profiles(config)["test-agent"]

    assert loaded.settings["compaction"]["reserveTokens"] == 12000


def test_owned_pi_profile_examples_are_complete_and_ready():
    profiles = load_pi_profiles(
        ROOT / "examples" / "agent-profiles" / "pi-profiles.example.json"
    )

    assert set(profiles) == {
        "example-guidance",
        "example-skill",
        "example-extension",
        "example-prompt-template",
        "example-mcp",
        "example-everything",
    }
    assert all(profile.readiness_errors() == [] for profile in profiles.values())
    everything = profiles["example-everything"]
    assert everything.tools[-2:] == (
        "repository_info",
        "example_catalog_lookup",
    )
    assert everything.mcp_servers[0]["extension"] == "mcp-client"
