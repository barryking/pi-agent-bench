import json
import threading
import urllib.request

import pytest

from pi_agent_bench.viewer import make_dashboard_server


def test_serves_local_dashboard_and_generated_metrics(tmp_path):
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "schema_version": 5,
                "run_id": "run-1",
                "case_id": "case-1",
                "dataset_version": "1",
                "started_at": "2026-07-25T12:00:00Z",
                "trial_number": 1,
                "run_name": "default",
                "cache_state": "unspecified",
                "agent_profile": {
                    "profile": "local-agent",
                    "pi_profile": {
                        "profile": "vanilla",
                        "configuration": {},
                        "configuration_fingerprint": "pi-vanilla",
                    },
                    "model_resources": [
                        {
                            "profile": "dgx",
                            "kind": "local",
                            "model": "openai/local-model",
                            "execution": {"mode": "inspect-bridge"},
                        }
                    ],
                    "default_model_resource": "dgx",
                    "configuration_fingerprint": "agent-local",
                },
                "inspect_model": "openai/local-model",
                "cohort": {"cohort_fingerprint": "cohort-a"},
                "harness": {
                    "harness_source_fingerprint": "harness-a",
                    "sandbox_image_id": "sha256:test-image",
                    "sandbox_source_fingerprint": "sandbox-source-a",
                },
                "success": True,
                "score": {"value": 1.0, "components": {}},
                "wall_seconds": 10,
                "usage": {
                    "bridged": {},
                    "direct": {},
                    "total": {"reported_cost": 0},
                    "cost_coverage": "complete",
                    "observed_models": [],
                },
                "agent": {},
                "verifier": {},
                "artifacts": {},
            }
        ),
        encoding="utf-8",
    )
    server = make_dashboard_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=5) as response:
            page = response.read().decode()
        with urllib.request.urlopen(f"{base_url}/metrics.jsonl", timeout=5) as response:
            metrics = response.read().decode()
        with urllib.request.urlopen(f"{base_url}/styles.css", timeout=5) as response:
            styles = response.read().decode()
        with urllib.request.urlopen(f"{base_url}/charts.js", timeout=5) as response:
            charts = response.read().decode()
        with urllib.request.urlopen(f"{base_url}/statistics.js", timeout=5) as response:
            statistics = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "<title>Pi Agent Bench — Agent profile comparison</title>" in page
    assert "Quality, time, and cost by agent profile" in page
    assert "Metric analysis" in page
    assert "Success versus tokens" in page
    assert "Shared cases only" in page
    assert "Case coverage" in page
    assert "View case-by-profile matrix" in page
    assert "Dataset version" in page
    assert page.index("Metric analysis") < page.index("Success versus tokens")
    profile_table_heading = "<h2>Agent profile comparison</h2>"
    assert page.index("Success versus tokens") < page.index(profile_table_heading)
    assert page.index(profile_table_heading) < page.index("Case coverage")
    assert '"metric": "quality.score"' in metrics
    assert '"started_at": "2026-07-25T12:00:00Z"' in metrics
    assert "--green" in styles
    assert "renderPareto" in charts
    assert "wilsonInterval" in statistics
    assert "caseBootstrapInterval" in statistics


def test_serves_existing_metrics_export_without_run_records(tmp_path):
    metrics = tmp_path / "metrics.jsonl"
    metrics.write_text(
        '{"schema_version":1,"metric":"quality.score","value":1}\n',
        encoding="utf-8",
    )
    server = make_dashboard_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=5) as response:
            page = response.read().decode()
        with urllib.request.urlopen(f"{base_url}/metrics.jsonl", timeout=5) as response:
            served_metrics = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Build validation" not in page
    assert served_metrics == (
        '{"schema_version":1,"metric":"quality.score","value":1}\n'
    )


def test_does_not_hide_invalid_records_behind_an_existing_metrics_export(tmp_path):
    (tmp_path / "broken.json").write_text('{"schema_version": 999}', encoding="utf-8")
    (tmp_path / "metrics.jsonl").write_text(
        '{"schema_version":1,"metric":"quality.score","value":1}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="supported run record schema"):
        make_dashboard_server(tmp_path, port=0)
