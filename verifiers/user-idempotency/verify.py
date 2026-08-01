#!/usr/bin/env python3
"""Protected behavioural verifier for the external FastAPI idempotency candidate."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
from contextlib import suppress
from pathlib import Path

WORKSPACE = Path("/workspace")
WEIGHTS = {
    "regression": 0.10,
    "normal_create": 0.10,
    "identical_replay": 0.20,
    "payload_conflict": 0.15,
    "restart_persistence": 0.15,
    "concurrent_duplicate": 0.15,
    "public_tests": 0.075,
    "documentation": 0.075,
}


def run(command: list[str], *, cwd: Path, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(WORKSPACE),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def hidden_probe(temp: Path) -> dict[str, bool]:
    probe = temp / "probe.py"
    probe.write_text(
        textwrap.dedent(
            """
            import json
            import sys
            import uuid
            from concurrent.futures import ThreadPoolExecutor

            from fastapi.testclient import TestClient

            from app.database import SessionLocal
            from app.main import app
            from app.models import User


            def payload(user_id, first_name="Ada"):
                return {
                    "id": user_id,
                    "first_name": first_name,
                    "last_name": "Lovelace",
                    "address": "1 Analytical Engine Way",
                    "activated": True,
                }


            def count_user(user_id):
                with SessionLocal() as session:
                    return session.query(User).filter(User.id == user_id).count()


            mode = sys.argv[1]
            if mode == "basic":
                with TestClient(app) as client:
                    plain_id = str(uuid.uuid4())
                    plain = client.post("/api/users/", json=payload(plain_id))

                    replay_id = str(uuid.uuid4())
                    key = "basic-" + str(uuid.uuid4())
                    first = client.post(
                        "/api/users/",
                        json=payload(replay_id),
                        headers={"Idempotency-Key": key},
                    )
                    second = client.post(
                        "/api/users/",
                        json=payload(replay_id),
                        headers={"Idempotency-Key": key},
                    )
                    conflict = client.post(
                        "/api/users/",
                        json=payload(str(uuid.uuid4()), first_name="Grace"),
                        headers={"Idempotency-Key": key},
                    )
                print(json.dumps({
                    "normal_create": plain.status_code == 201,
                    "identical_replay": (
                        first.status_code == 201
                        and second.status_code == first.status_code
                        and second.json() == first.json()
                        and count_user(replay_id) == 1
                    ),
                    "payload_conflict": conflict.status_code == 409,
                }))
            elif mode == "once":
                user_id, key = sys.argv[2], sys.argv[3]
                with TestClient(app) as client:
                    response = client.post(
                        "/api/users/",
                        json=payload(user_id),
                        headers={"Idempotency-Key": key},
                    )
                print(json.dumps({
                    "status": response.status_code,
                    "body": response.json(),
                    "count": count_user(user_id),
                }, sort_keys=True))
            elif mode == "concurrent":
                user_id = str(uuid.uuid4())
                key = "concurrent-" + str(uuid.uuid4())

                def request():
                    with TestClient(app) as client:
                        response = client.post(
                            "/api/users/",
                            json=payload(user_id),
                            headers={"Idempotency-Key": key},
                        )
                        return response.status_code, response.json()

                with ThreadPoolExecutor(max_workers=6) as pool:
                    responses = list(pool.map(lambda _: request(), range(6)))
                statuses = [item[0] for item in responses]
                bodies = [item[1] for item in responses]
                print(json.dumps({
                    "ok": (
                        statuses == [201] * 6
                        and all(body == bodies[0] for body in bodies)
                        and count_user(user_id) == 1
                    )
                }))
            """
        ),
        encoding="utf-8",
    )

    components = {
        "normal_create": False,
        "identical_replay": False,
        "payload_conflict": False,
        "restart_persistence": False,
        "concurrent_duplicate": False,
    }
    basic = run(["python3", str(probe), "basic"], cwd=temp)
    if basic.returncode == 0:
        with suppress(IndexError, json.JSONDecodeError):
            values = json.loads(basic.stdout.strip().splitlines()[-1])
            for name in ("normal_create", "identical_replay", "payload_conflict"):
                components[name] = values.get(name) is True

    user_id = "00000000-0000-4000-8000-000000000001"
    key = "restart-persistence-key"
    first = run(["python3", str(probe), "once", user_id, key], cwd=temp)
    second = run(["python3", str(probe), "once", user_id, key], cwd=temp)
    if first.returncode == 0 and second.returncode == 0:
        with suppress(IndexError, KeyError, json.JSONDecodeError):
            first_value = json.loads(first.stdout.strip().splitlines()[-1])
            second_value = json.loads(second.stdout.strip().splitlines()[-1])
            components["restart_persistence"] = (
                first_value["status"] == 201
                and second_value == first_value
                and second_value["count"] == 1
            )

    concurrent = run(["python3", str(probe), "concurrent"], cwd=temp)
    if concurrent.returncode == 0:
        with suppress(IndexError, json.JSONDecodeError):
            components["concurrent_duplicate"] = (
                json.loads(concurrent.stdout.strip().splitlines()[-1]).get("ok") is True
            )
    return components


def changed_evidence() -> tuple[bool, bool]:
    run(
        ["git", "-c", "safe.directory=/workspace", "add", "-N", "."],
        cwd=WORKSPACE,
        timeout=20,
    )
    names = run(
        ["git", "-c", "safe.directory=/workspace", "diff", "--name-only", "HEAD"],
        cwd=WORKSPACE,
        timeout=20,
    ).stdout.splitlines()
    test_files = [
        WORKSPACE / name
        for name in names
        if name.startswith("tests/") and name.endswith(".py")
    ]
    public_tests = any(
        "idempotency" in path.read_text(encoding="utf-8", errors="ignore").lower()
        for path in test_files
        if path.is_file()
    )
    readme = WORKSPACE / "README.md"
    documentation = readme.is_file() and all(
        term in readme.read_text(encoding="utf-8", errors="ignore").lower()
        for term in ("idempotency-key", "409")
    )
    return public_tests, documentation


def main() -> None:
    components: dict[str, bool] = {name: False for name in WEIGHTS}
    regression = run(["python3", "-m", "pytest", "-q"], cwd=WORKSPACE, timeout=120)
    components["regression"] = regression.returncode == 0
    with tempfile.TemporaryDirectory(prefix="idempotency-verifier-") as directory:
        components.update(hidden_probe(Path(directory)))
    components["public_tests"], components["documentation"] = changed_evidence()
    score = sum(WEIGHTS[name] for name, passed in components.items() if passed)
    failed = [name for name, passed in components.items() if not passed]
    print(
        json.dumps(
            {
                "score": round(score, 6),
                "components": {
                    name: 1.0 if passed else 0.0 for name, passed in components.items()
                },
                "explanation": (
                    "All idempotency checks passed."
                    if not failed
                    else "Failed components: " + ", ".join(failed)
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
