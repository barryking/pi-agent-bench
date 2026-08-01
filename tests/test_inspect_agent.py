import asyncio
import json
from types import SimpleNamespace

from pi_agent_bench.agent_profiles import AgentProfile
from pi_agent_bench.inspect_agent import _stage_direct_auth, _stage_pi_profile
from pi_agent_bench.model_profiles import ModelProfile
from pi_agent_bench.pi_profiles import load_pi_profiles, vanilla_pi_profile


class FakeSandbox:
    def __init__(self):
        self.files = {}
        self.commands = []

    async def write_file(self, path, content):
        self.files[path] = content

    async def exec(self, command):
        self.commands.append(command)
        return SimpleNamespace(success=True, stderr="")


def test_stages_renamed_pi_profile_resources(tmp_path, monkeypatch):
    context = tmp_path / "AGENTS.md"
    context.write_text("Use the repository contract.\n", encoding="utf-8")
    source = tmp_path / "pi.json"
    source.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "test-pi": {
                        "description": "Test Pi.",
                        "tools": ["read"],
                        "runtime_env": {},
                        "settings": {"compaction": {"reserveTokens": 1000}},
                        "context_files": [{"name": "rules", "path": "AGENTS.md"}],
                        "system_prompt": None,
                        "append_system_prompts": [],
                        "skills": [],
                        "extensions": [],
                        "prompt_templates": [],
                        "mcp_servers": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    fake = FakeSandbox()
    monkeypatch.setattr("pi_agent_bench.inspect_agent.sandbox", lambda: fake)

    asyncio.run(_stage_pi_profile(load_pi_profiles(source)["test-pi"], "/pi"))

    assert json.loads(fake.files["/pi/settings.json"])["compaction"] == {
        "reserveTokens": 1000
    }
    assert "Use the repository contract." in fake.files["/pi/AGENTS.md"]


def test_stages_authentication_only_for_selected_direct_resource(tmp_path, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text(
        json.dumps(
            {
                "openai-codex": {"access": "selected-secret"},
                "unselected-provider": {"access": "must-not-be-staged"},
            }
        ),
        encoding="utf-8",
    )
    direct = ModelProfile.from_dict(
        "reviewer",
        {
            "kind": "hosted",
            "model": "openai-codex/reviewer",
            "execution": {
                "mode": "pi-direct",
                "provider": "openai-codex",
                "model": "reviewer",
                "auth_file_env": "PI_AUTH_FILE",
            },
            "capabilities": {
                "context_tokens": 32768,
                "max_output_tokens": 8192,
                "reasoning": True,
                "input": ["text"],
            },
            "configuration": {"revision": "test"},
        },
    )
    profile = AgentProfile(
        name="test-agent",
        description="Test.",
        pi_profile=vanilla_pi_profile(),
        model_resources=(direct,),
        default_model_resource="reviewer",
    )
    fake = FakeSandbox()
    monkeypatch.setattr("pi_agent_bench.inspect_agent.sandbox", lambda: fake)

    asyncio.run(
        _stage_direct_auth(
            profile,
            {"reviewer": str(auth)},
            "/pi",
        )
    )

    staged = json.loads(fake.files["/pi/auth.json"])
    assert staged == {"openai-codex": {"access": "selected-secret"}}
    assert fake.commands == [["chmod", "600", "/pi/auth.json"]]
