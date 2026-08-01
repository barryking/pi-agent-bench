import json
from types import SimpleNamespace

import pytest

from pi_agent_bench.harness_identity import (
    SANDBOX_LABEL,
    build_sandbox,
    cohort_identity,
    sandbox_identity,
    sandbox_runtime_fingerprint,
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


def test_common_sandbox_runtime_does_not_change_for_an_unrelated_verifier(tmp_path):
    write_sandbox_source(tmp_path)
    before = sandbox_runtime_fingerprint(tmp_path)
    (tmp_path / "verifiers" / "verify.py").write_text(
        "print('changed')\n",
        encoding="utf-8",
    )

    assert sandbox_runtime_fingerprint(tmp_path) == before


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


def test_cohort_fingerprint_tracks_case_evidence_but_not_profile_files(tmp_path):
    repository = tmp_path / "starting"
    repository.mkdir()
    (repository / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    verifier = tmp_path / "verifiers" / "case-one" / "verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("print('{}')\n", encoding="utf-8")
    dataset = tmp_path / "cases.jsonl"
    case = {
        "id": "case-one",
        "instruction": "Implement the requirement.",
        "tags": ["test"],
        "limits": {
            "seconds": 60,
            "turns": 5,
            "context_tokens": 8192,
            "total_tokens": 10000,
        },
        "expected": {
            "verifier_command": [
                "python3",
                "/opt/verifiers/case-one/verify.py",
            ],
            "success_threshold": 1,
            "required_components": ["requirements"],
        },
        "metadata": {
            "dataset_version": "test-1",
            "starting_repository": str(repository),
            "draft": False,
            "score_components": ["requirements"],
            "synthetic": True,
        },
    }
    dataset.write_text(json.dumps(case) + "\n", encoding="utf-8")
    harness = {
        "framework_version": "1",
        "pi_version_expected": "1",
        "inspect_version": "1",
        "execution_protocol_fingerprint": "execution",
        "sandbox_runtime_fingerprint": "runtime",
        "sandbox_image_id": "image",
        "sandbox_source_fingerprint": "sandbox",
    }

    first = cohort_identity(
        dataset,
        cache_state="warm",
        cost_limit=None,
        harness=harness,
        root=tmp_path,
    )
    assert first["cohort_schema_version"] == 2
    assert "dataset_file_sha256" in first["evidence"]
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "agent-profiles.json").write_text("changed")
    same = cohort_identity(
        dataset,
        cache_state="warm",
        cost_limit=None,
        harness=harness,
        root=tmp_path,
    )
    assert same["cohort_fingerprint"] == first["cohort_fingerprint"]

    formatted = json.dumps(case, sort_keys=True, separators=(",", ":"))
    dataset.write_text(formatted + "\n", encoding="utf-8")
    same_content = cohort_identity(
        dataset,
        cache_state="warm",
        cost_limit=None,
        harness=harness,
        root=tmp_path,
    )
    assert same_content["cohort_fingerprint"] == first["cohort_fingerprint"]

    cost_limited = cohort_identity(
        dataset,
        cache_state="warm",
        cost_limit=1.5,
        harness=harness,
        root=tmp_path,
    )
    assert cost_limited["cohort_fingerprint"] != first["cohort_fingerprint"]

    verifier.write_text("print('{\"score\": 1}')\n", encoding="utf-8")
    changed = cohort_identity(
        dataset,
        cache_state="warm",
        cost_limit=None,
        harness=harness,
        root=tmp_path,
    )
    assert changed["cohort_fingerprint"] != first["cohort_fingerprint"]
