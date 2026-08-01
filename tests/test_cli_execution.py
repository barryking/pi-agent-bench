from argparse import Namespace
from io import BytesIO

from pi_agent_bench.cli_execution import (
    _benchmark_id,
    _doctor,
    _eval_set_id,
    _local_endpoint_errors,
)
from pi_agent_bench.model_profiles import ModelProfile


class ReadyProfile:
    name = "ready"
    model_resources = ()

    class PiProfile:
        def resolved_runtime_env(self, _environment):
            return {}

    pi_profile = PiProfile()

    def readiness_errors(self):
        return []


class ModelsResponse(BytesIO):
    status = 200


def local_resource(model="openai/nvidia/example-model"):
    return ModelProfile.from_dict(
        "local-resource",
        {
            "kind": "local",
            "model": model,
            "execution": {
                "mode": "inspect-bridge",
                "model_args": {},
                "model_args_env": {},
                "generate_config": {},
            },
            "capabilities": {
                "context_tokens": 32768,
                "max_output_tokens": 8192,
                "reasoning": True,
                "input": ["text"],
            },
            "configuration": {"runtime": "test", "revision": "test"},
        },
    )


def test_eval_set_ids_are_safe_and_profile_specific():
    sol = _eval_set_id("campaign v1", "gpt-5.6-sol")
    luna = _eval_set_id("campaign v1", "gpt-5.6-luna")
    guided = _eval_set_id("campaign v1", "team tools")

    assert sol == "campaign-v1-gpt-5-6-sol"
    assert luna == "campaign-v1-gpt-5-6-luna"
    assert guided == "campaign-v1-team-tools"
    assert sol != luna


def test_benchmark_ids_are_stable_for_resume_and_separate_for_new_campaigns(tmp_path):
    resume = Namespace(
        benchmark_id=None,
        resume=True,
        logs_dir=tmp_path,
        run_name="campaign",
    )
    fresh = Namespace(benchmark_id=None, resume=False)

    assert _benchmark_id(resume) == _benchmark_id(resume)
    assert _benchmark_id(fresh) != _benchmark_id(fresh)


def test_doctor_accepts_an_advertised_local_service_model(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda _request, timeout: ModelsResponse(
            b'{"data":[{"id":"nvidia/example-model"}]}'
        ),
    )

    assert (
        _local_endpoint_errors(
            local_resource(),
            {"base_url": "http://spark.invalid:8000/v1", "api_key": "private"},
        )
        == []
    )


def test_doctor_rejects_a_local_endpoint_without_the_configured_model(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda _request, timeout: ModelsResponse(
            b'{"data":[{"id":"another-model"}]}'
        ),
    )

    errors = _local_endpoint_errors(
        local_resource(),
        {"base_url": "http://spark.invalid:8000/v1", "api_key": "private"},
    )

    assert errors == [
        "local-resource: configured model 'nvidia/example-model' is not advertised by "
        "http://spark.invalid:8000/v1/models; available: another-model"
    ]


def test_doctor_rejects_a_malformed_local_models_response(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda _request, timeout: ModelsResponse(b'{"models":[]}'),
    )

    assert _local_endpoint_errors(
        local_resource("ollama/example"),
        {"base_url": "http://ollama.invalid:11434/v1", "api_key": "ollama"},
    ) == ["local-resource: local endpoint returned an invalid /models response"]


def test_doctor_uses_the_native_ollama_default_endpoint(monkeypatch):
    requested_urls = []

    def open_models(request, timeout):
        requested_urls.append(request.full_url)
        return ModelsResponse(b'{"data":[{"id":"example"}]}')

    monkeypatch.setattr("urllib.request.urlopen", open_models)

    assert _local_endpoint_errors(local_resource("ollama/example"), {}) == []
    assert requested_urls == ["http://localhost:11434/v1/models"]


def test_doctor_requires_an_endpoint_for_other_local_bridge_providers():
    assert _local_endpoint_errors(local_resource(), {}) == [
        "local-resource: local bridged resources require a base_url so the "
        "configured model can be verified"
    ]


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
