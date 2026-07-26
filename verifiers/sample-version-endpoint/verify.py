"""Model-hidden deterministic verifier for the synthetic version endpoint case."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/workspace")
sys.path.insert(0, str(WORKSPACE))


def request(application, path: str) -> tuple[str, dict[str, str], bytes]:
    response: dict[str, object] = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    body = b"".join(application({"PATH_INFO": path}, start_response))
    return str(response["status"]), dict(response["headers"]), body


def main() -> int:
    components: dict[str, bool] = {}
    explanations: list[str] = []
    try:
        from app import application

        ping_status, _, ping_body = request(application, "/ping")
        components["existing_behaviour"] = (
            ping_status == "200 OK" and ping_body == b"pong\n"
        )

        version_status, version_headers, version_body = request(
            application,
            "/version",
        )
        components["version_status"] = version_status == "200 OK"
        components["version_content_type"] = version_headers.get(
            "Content-Type",
            "",
        ).startswith("application/json")
        try:
            version_payload = json.loads(version_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            version_payload = None
        components["version_payload"] = version_payload == {"version": "1.0.0"}
    except Exception as exc:
        explanations.append(f"service import or request failed: {exc}")
        components.update(
            {
                "existing_behaviour": False,
                "version_status": False,
                "version_content_type": False,
                "version_payload": False,
            }
        )

    readme = (WORKSPACE / "README.md").read_text(encoding="utf-8").casefold()
    components["documentation"] = "/version" in readme and "json" in readme

    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    components["public_tests"] = tests.returncode == 0
    if tests.returncode:
        explanations.append(tests.stdout + tests.stderr)

    passed = sum(components.values())
    total = len(components)
    payload = {
        "score": passed / total,
        "components": components,
        "explanation": "; ".join(explanations) or f"{passed}/{total} checks passed",
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
