from pi_agent_bench.cli_execution import _doctor, _eval_set_id


class ReadyProfile:
    name = "ready"
    kind = "hosted"
    pi_direct = None

    def readiness_errors(self):
        return []

    def resolved_runtime_env(self, _environment):
        return {}

    def resolved_pi_auth_file(self, _environment):
        return None


def test_eval_set_ids_are_safe_and_profile_specific():
    sol = _eval_set_id("pilot v1", "gpt-5.6-sol")
    luna = _eval_set_id("pilot v1", "gpt-5.6-luna")
    guided = _eval_set_id("pilot v1", "gpt-5.6-sol", "team tools")

    assert sol == "pilot-v1-gpt-5-6-sol"
    assert luna == "pilot-v1-gpt-5-6-luna"
    assert guided == "pilot-v1-gpt-5-6-sol-team-tools"
    assert sol != luna


def test_doctor_rejects_a_stale_sandbox(monkeypatch):
    monkeypatch.setattr("pi_agent_bench.cli_execution._host_readiness_errors", lambda: [])
    monkeypatch.setattr(
        "pi_agent_bench.cli_execution.sandbox_identity",
        lambda: (_ for _ in ()).throw(ValueError("sandbox is stale")),
    )

    assert _doctor(ReadyProfile()) == ["sandbox is stale"]


def test_doctor_does_not_hide_profile_errors_behind_sandbox_checks(monkeypatch):
    class BrokenProfile(ReadyProfile):
        def readiness_errors(self):
            return ["model profile is incomplete"]

    called = False

    def sandbox():
        nonlocal called
        called = True

    monkeypatch.setattr("pi_agent_bench.cli_execution._host_readiness_errors", lambda: [])
    monkeypatch.setattr("pi_agent_bench.cli_execution.sandbox_identity", sandbox)

    assert _doctor(BrokenProfile()) == ["model profile is incomplete"]
    assert called is False
