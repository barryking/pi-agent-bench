#!/usr/bin/env python3
"""Protected checks for the user-list filter pilot."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

WORKSPACE = Path("/workspace")
WEIGHTS = {
    "regression": 0.15,
    "default_list": 0.15,
    "activated_true": 0.15,
    "activated_false": 0.15,
    "pagination_validation": 0.15,
    "public_tests": 0.10,
    "documentation": 0.15,
}


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env={
            **os.environ,
            "PYTHONPATH": str(WORKSPACE),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def hidden_probe(temporary: Path) -> dict[str, bool]:
    probe = temporary / "probe.py"
    probe.write_text(
        textwrap.dedent(
            """
            import json
            import uuid

            from fastapi.testclient import TestClient

            from app.main import app


            prefix = "filter-" + uuid.uuid4().hex


            def payload(name, active):
                return {
                    "id": str(uuid.uuid4()),
                    "first_name": prefix + "-" + name,
                    "last_name": "Pilot",
                    "address": "Test Street",
                    "activated": active,
                }


            with TestClient(app) as client:
                active = payload("active", True)
                inactive = payload("inactive", False)
                created = [
                    client.post("/api/users/", json=active),
                    client.post("/api/users/", json=inactive),
                ]
                default = client.get(
                    "/api/users/",
                    params={"search": prefix, "limit": 100, "page": 1},
                )
                only_active = client.get(
                    "/api/users/",
                    params={
                        "search": prefix,
                        "activated": "true",
                        "limit": 100,
                        "page": 1,
                    },
                )
                only_inactive = client.get(
                    "/api/users/",
                    params={
                        "search": prefix,
                        "activated": "false",
                        "limit": 100,
                        "page": 1,
                    },
                )
                invalid = [
                    client.get("/api/users/", params={"limit": 0}),
                    client.get("/api/users/", params={"limit": 101}),
                    client.get("/api/users/", params={"page": 0}),
                ]


            def users(response):
                return response.json().get("users", []) if response.status_code == 200 else []


            active_users = users(only_active)
            inactive_users = users(only_inactive)
            default_ids = {user["id"] for user in users(default)}
            print(json.dumps({
                "default_list": (
                    all(response.status_code == 201 for response in created)
                    and {active["id"], inactive["id"]}.issubset(default_ids)
                ),
                "activated_true": (
                    only_active.status_code == 200
                    and [user["id"] for user in active_users] == [active["id"]]
                    and all(user["activated"] is True for user in active_users)
                ),
                "activated_false": (
                    only_inactive.status_code == 200
                    and [user["id"] for user in inactive_users] == [inactive["id"]]
                    and all(user["activated"] is False for user in inactive_users)
                ),
                "pagination_validation": all(response.status_code == 422 for response in invalid),
            }, sort_keys=True))
            """
        ),
        encoding="utf-8",
    )
    completed = run(["python3", str(probe)], cwd=temporary)
    if completed.returncode:
        return {
            "default_list": False,
            "activated_true": False,
            "activated_false": False,
            "pagination_validation": False,
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload = {}
    return {
        name: payload.get(name) is True
        for name in (
            "default_list",
            "activated_true",
            "activated_false",
            "pagination_validation",
        )
    }


def changed_evidence() -> tuple[bool, bool]:
    changed = run(
        ["git", "-c", "safe.directory=/workspace", "diff", "--name-only", "HEAD"],
        cwd=WORKSPACE,
        timeout=20,
    ).stdout.splitlines()
    tests = [
        WORKSPACE / name
        for name in changed
        if name.startswith("tests/") and name.endswith(".py")
    ]
    public_tests = any(
        all(term in path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in ("activated", "limit", "page"))
        for path in tests
        if path.is_file()
    )
    readme = WORKSPACE / "README.md"
    documentation = readme.is_file() and all(
        term in readme.read_text(encoding="utf-8", errors="ignore").lower()
        for term in ("activated", "limit", "page")
    )
    return public_tests, documentation


def main() -> None:
    components = {name: False for name in WEIGHTS}
    regression = run(["python3", "-m", "pytest", "-q"], cwd=WORKSPACE)
    components["regression"] = regression.returncode == 0
    with tempfile.TemporaryDirectory(prefix="user-list-filter-") as temporary:
        components.update(hidden_probe(Path(temporary)))
    components["public_tests"], components["documentation"] = changed_evidence()
    score = sum(WEIGHTS[name] for name, passed in components.items() if passed)
    failed = [name for name, passed in components.items() if not passed]
    print(
        json.dumps(
            {
                "score": round(score, 6),
                "components": {
                    name: 1.0 if passed else 0.0
                    for name, passed in components.items()
                },
                "explanation": (
                    "All user-list filter checks passed."
                    if not failed
                    else "Failed components: " + ", ".join(failed)
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
