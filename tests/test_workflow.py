import pytest

from pi_agent_bench.case_proof import assess_case_proof
from pi_agent_bench.dataset import load_cases
from pi_agent_bench.verification import verifier_payload
from pi_agent_bench.workflow import initialize_workspace, scaffold_case
from pi_agent_bench.workspace import prepare_workspace


def test_init_creates_local_files_without_overwriting(tmp_path):
    first = initialize_workspace(tmp_path)
    env = tmp_path / ".env.local"
    profiles = tmp_path / "configs" / "model-baselines.local.json"
    agent_profiles = tmp_path / "configs" / "agent-profiles.local.json"

    assert {status for _, status in first} == {"created"}
    env.write_text("USER_VALUE=kept\n", encoding="utf-8")

    second = initialize_workspace(tmp_path)

    assert {status for _, status in second} == {"kept"}
    assert env.read_text(encoding="utf-8") == "USER_VALUE=kept\n"
    assert profiles.is_file()
    assert agent_profiles.is_file()


@pytest.mark.parametrize("phase", ["planning", "coding"])
def test_new_case_creates_loadable_safe_scaffold(tmp_path, phase):
    case_id = f"{phase}-example-001"
    dataset = tmp_path / f"{phase}.jsonl"

    paths = scaffold_case(
        phase,
        case_id,
        dataset,
        root=tmp_path,
    )
    [case] = load_cases(dataset)

    assert paths[0] == dataset
    assert case.id == case_id
    assert case.metadata["draft"] is True
    if phase == "coding":
        assert (tmp_path / "fixtures" / case_id / "README.md").is_file()
        verifier = tmp_path / "verifiers" / case_id / "verify.py"
        assert "TODO: implement protected verification" in verifier.read_text(
            encoding="utf-8"
        )


def test_new_case_refuses_to_overwrite(tmp_path):
    dataset = tmp_path / "case.jsonl"
    scaffold_case("planning", "plan-example-001", dataset, root=tmp_path)

    with pytest.raises(ValueError, match="refusing to overwrite"):
        scaffold_case("planning", "plan-example-001", dataset, root=tmp_path)


def test_saved_diff_can_reconstruct_disposable_workspace(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "value.txt").write_text("old\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    diff = """\
diff --git a/value.txt b/value.txt
--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-old
+new
"""

    prepare_workspace(fixture, diff, workspace)

    assert (workspace / "value.txt").read_text(encoding="utf-8") == "new\n"
    assert (fixture / "value.txt").read_text(encoding="utf-8") == "old\n"


def test_replay_parser_uses_last_json_object():
    payload = verifier_payload(
        'diagnostic output\n{"score":0.5,"components":{"tests":0.5}}\n'
    )

    assert payload == {"score": 0.5, "components": {"tests": 0.5}}


def test_case_proof_requires_untouched_failure_and_known_good_success():
    proof = assess_case_proof(
        {"score": 0.25, "components": {"old": 1, "new": 0}},
        {"score": 1.0, "components": {"old": 1, "new": 1}},
        success_threshold=0.8,
    )

    assert proof["proved"] is True
    assert proof["before"]["failed_as_expected"] is True
    assert proof["after"]["passed_as_expected"] is True


def test_case_proof_rejects_a_case_that_already_passes():
    proof = assess_case_proof(
        {"score": 1.0},
        {"score": 1.0},
        success_threshold=0.8,
    )

    assert proof["proved"] is False


def test_case_proof_rejects_missing_critical_component():
    proof = assess_case_proof(
        {"score": 0.2, "components": {"core": 0}},
        {"score": 0.9, "components": {"core": 0, "docs": 1}},
        success_threshold=0.8,
        required_components=("core",),
    )

    assert proof["proved"] is False
    assert proof["after"]["passed_as_expected"] is False
