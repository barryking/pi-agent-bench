import json
from types import SimpleNamespace

import pytest

from pi_agent_bench.harness_identity import (
    SANDBOX_LABEL,
    build_sandbox,
    sandbox_identity,
    sandbox_source_fingerprint,
)
from pi_agent_bench.versions import FRAMEWORK_VERSION, PI_VERSION, SANDBOX_IMAGE


def write_sandbox_source(root):
    (root / "docker").mkdir()
    (root / "docker" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (root / "docker" / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (root / "verifiers").mkdir()
    (root / "verifiers" / "verify.py").write_text("print('ok')\n", encoding="utf-8")


def test_sandbox_source_fingerprint_changes_with_protected_source(tmp_path):
    write_sandbox_source(tmp_path)
    before = sandbox_source_fingerprint(tmp_path)
    (tmp_path / "verifiers" / "verify.py").write_text("print('changed')\n", encoding="utf-8")

    assert sandbox_source_fingerprint(tmp_path) != before


def test_sandbox_identity_rejects_a_stale_image(tmp_path, monkeypatch):
    write_sandbox_source(tmp_path)
    image = {
        "Id": "sha256:stale",
        "RepoDigests": [],
        "Config": {
            "Labels": {
                SANDBOX_LABEL: "old-source",
                "dev.pi.version": PI_VERSION,
                "org.opencontainers.image.version": FRAMEWORK_VERSION,
            }
        },
    }
    monkeypatch.setattr(
        "pi_agent_bench.harness_identity.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps([image]),
        ),
    )

    with pytest.raises(ValueError, match="does not match this checkout"):
        sandbox_identity(tmp_path)


def test_sandbox_identity_rejects_stale_pi_version(tmp_path, monkeypatch):
    write_sandbox_source(tmp_path)
    image = {
        "Id": "sha256:stale-version",
        "RepoDigests": [],
        "Config": {
            "Labels": {
                SANDBOX_LABEL: sandbox_source_fingerprint(tmp_path),
                "dev.pi.version": "old",
                "org.opencontainers.image.version": FRAMEWORK_VERSION,
            }
        },
    }
    monkeypatch.setattr(
        "pi_agent_bench.harness_identity.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps([image]),
        ),
    )

    with pytest.raises(ValueError, match="stale version labels"):
        sandbox_identity(tmp_path)


def test_build_labels_and_records_the_current_sandbox_source(tmp_path, monkeypatch):
    write_sandbox_source(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            fingerprint = sandbox_source_fingerprint(tmp_path)
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    [
                        {
                            "Id": "sha256:fresh",
                            "RepoDigests": [f"{SANDBOX_IMAGE}@sha256:digest"],
                            "Config": {
                                "Labels": {
                                    SANDBOX_LABEL: fingerprint,
                                    "dev.pi.version": PI_VERSION,
                                    "org.opencontainers.image.version": FRAMEWORK_VERSION,
                                }
                            },
                        }
                    ]
                ),
            )
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("pi_agent_bench.harness_identity.subprocess.run", fake_run)

    build_sandbox(tmp_path)
    identity = sandbox_identity(tmp_path)

    assert commands[0][:2] == ["docker", "build"]
    assert "--provenance=false" in commands[0]
    assert SANDBOX_IMAGE in commands[0]
    assert any(
        item.startswith("BENCHMARK_SOURCE_FINGERPRINT=")
        for item in commands[0]
    )
    assert identity["sandbox_image_id"] == "sha256:fresh"
    assert identity["sandbox_repo_digests"] == [f"{SANDBOX_IMAGE}@sha256:digest"]
