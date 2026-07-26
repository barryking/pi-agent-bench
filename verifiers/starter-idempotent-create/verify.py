#!/usr/bin/env python3
"""Protected checks for the owned durable-idempotency starter case."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORKSPACE = Path("/workspace")
sys.path.insert(0, str(WORKSPACE))
COMPONENTS = (
    "regression",
    "normal_create",
    "identical_replay",
    "payload_conflict",
    "restart_persistence",
    "concurrent_duplicate",
    "key_validation",
    "public_tests",
    "documentation",
)


def main() -> None:
    values = {name: False for name in COMPONENTS}
    regression = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    values["regression"] = regression.returncode == 0
    try:
        from starter_service.idempotency import IdempotencyConflict, UserRepository

        with tempfile.TemporaryDirectory(prefix="starter-idempotency-") as temporary:
            database = Path(temporary) / "users.sqlite"
            repository = UserRepository(database)
            values["normal_create"] = (
                repository.create_user({"id": "plain", "name": "Ada"})
                == (201, {"id": "plain", "name": "Ada"})
            )
            payload = {"id": "keyed", "name": "Grace"}
            first = repository.create_user(payload, idempotency_key="key-1")
            second = repository.create_user(payload, idempotency_key="key-1")
            values["identical_replay"] = (
                first == second == (201, payload) and repository.count_users() == 2
            )
            try:
                repository.create_user(
                    {"id": "other", "name": "Different"},
                    idempotency_key="key-1",
                )
            except IdempotencyConflict:
                values["payload_conflict"] = True

            reopened = UserRepository(database)
            values["restart_persistence"] = (
                reopened.create_user(payload, idempotency_key="key-1") == first
                and reopened.count_users() == 2
            )

            concurrent_payload = {"id": "concurrent", "name": "Lin"}

            def create():
                return UserRepository(database).create_user(
                    concurrent_payload,
                    idempotency_key="key-concurrent",
                )

            with ThreadPoolExecutor(max_workers=6) as pool:
                outcomes = list(pool.map(lambda _: create(), range(6)))
            values["concurrent_duplicate"] = (
                outcomes == [(201, concurrent_payload)] * 6
                and reopened.count_users() == 3
            )
            invalid = 0
            for key in ("", "x" * 129):
                try:
                    reopened.create_user(
                        {"id": "invalid-" + str(len(key)), "name": "No"},
                        idempotency_key=key,
                    )
                except ValueError:
                    invalid += 1
            values["key_validation"] = invalid == 2
    except Exception:
        pass

    changed = _changed_files()
    test_text = "\n".join(
        (WORKSPACE / name).read_text(encoding="utf-8", errors="ignore").casefold()
        for name in changed
        if name.startswith("tests/") and name.endswith(".py") and (WORKSPACE / name).is_file()
    )
    values["public_tests"] = all(
        term in test_text for term in ("idempotency", "replay", "conflict")
    )
    readme = WORKSPACE / "README.md"
    documentation = (
        readme.read_text(encoding="utf-8", errors="ignore").casefold()
        if readme.is_file()
        else ""
    )
    values["documentation"] = all(
        term in documentation for term in ("idempotency", "conflict", "128")
    )
    _print(values)


def _changed_files() -> list[str]:
    subprocess.run(
        ["git", "-c", "safe.directory=/workspace", "add", "-N", "."],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    return subprocess.run(
        ["git", "-c", "safe.directory=/workspace", "diff", "--name-only", "HEAD"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()


def _print(values: dict[str, bool]) -> None:
    score = sum(values.values()) / len(values)
    failed = [name for name, passed in values.items() if not passed]
    print(
        json.dumps(
            {
                "score": round(score, 6),
                "components": {name: float(passed) for name, passed in values.items()},
                "explanation": (
                    "All checks passed."
                    if not failed
                    else "Failed: " + ", ".join(failed)
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
