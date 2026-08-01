import asyncio
import json
from types import SimpleNamespace

import pytest

from pi_agent_bench.agent_profiles import AgentProfile
from pi_agent_bench.inspect_agent import (
    _append_direct_final_message,
    _stage_direct_auth,
    _stage_pi_profile,
)
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


def direct_profile():
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
    return AgentProfile(
        name="test-agent",
        description="Test.",
        pi_profile=vanilla_pi_profile(),
        model_resources=(direct,),
        default_model_resource="reviewer",
    )


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
    profile = direct_profile()
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


def test_rejects_non_object_direct_authentication_document(tmp_path, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text("[]", encoding="utf-8")
    fake = FakeSandbox()
    monkeypatch.setattr("pi_agent_bench.inspect_agent.sandbox", lambda: fake)

    with pytest.raises(RuntimeError, match="could not load openai-codex credentials"):
        asyncio.run(
            _stage_direct_auth(
                direct_profile(),
                {"reviewer": str(auth)},
                "/pi",
            )
        )


def test_direct_final_message_never_reuses_text_from_an_earlier_event():
    state = SimpleNamespace(messages=[])
    events = (
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "openai-codex",
                "model": "reviewer",
                "content": [{"type": "text", "text": "earlier response"}],
            },
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "openai-codex",
                "model": "reviewer",
                "content": [{"type": "toolCall", "name": "read"}],
            },
        },
    )

    _append_direct_final_message(state, events, direct_profile())

    assert state.messages == []
