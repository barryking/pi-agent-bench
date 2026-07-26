import json
import threading
import urllib.request

from pi_agent_bench.viewer import make_dashboard_server


def test_serves_local_dashboard_and_generated_metrics(tmp_path):
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "run_id": "run-1",
                "case_id": "case-1",
                "dataset_version": "1",
                "started_at": "2026-07-25T12:00:00Z",
                "trial_number": 1,
                "campaign": "default",
                "cache_state": "unspecified",
                "model_configuration": {
                    "profile": "dgx",
                    "kind": "local",
                    "configuration": {},
                    "configuration_fingerprint": "model-dgx",
                },
                "agent_configuration": {
                    "profile": "vanilla",
                    "configuration": {},
                    "configuration_fingerprint": "agent-vanilla",
                },
                "inspect_model": "openai/local-model",
                "harness": {"benchmark_fingerprint": "benchmark-a"},
                "success": True,
                "score": {"value": 1.0, "components": {}},
                "wall_seconds": 10,
                "usage": {},
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
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "<title>Pi Agent Bench — Model comparison</title>" in page
    assert "Primary view: quality versus total task time" in page
    assert "Success versus tokens" in page
    assert "Common cases only" in page
    assert "Case coverage" in page
    assert "Dataset version" in page
    assert '"metric": "quality.score"' in metrics
    assert '"started_at": "2026-07-25T12:00:00Z"' in metrics
    assert "--green" in styles
    assert "renderPareto" in charts
