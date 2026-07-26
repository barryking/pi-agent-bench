#!/usr/bin/env python3
"""Protected checks for the owned user-filter starter case."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/workspace")
sys.path.insert(0, str(WORKSPACE))
WEIGHTS = {
    "regression": 0.15,
    "default_list": 0.10,
    "activated_true": 0.15,
    "activated_false": 0.15,
    "pagination_validation": 0.15,
    "public_tests": 0.15,
    "documentation": 0.15,
}


def changed_files() -> list[str]:
    subprocess.run(
        ["git", "-c", "safe.directory=/workspace", "add", "-N", "."],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    completed = subprocess.run(
        ["git", "-c", "safe.directory=/workspace", "diff", "--name-only", "HEAD"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.splitlines()


def main() -> None:
    components = {name: False for name in WEIGHTS}
    regression = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    components["regression"] = regression.returncode == 0
    try:
        from starter_service.users import list_users

        users = [
            {"id": "1", "name": "Ada", "activated": True},
            {"id": "2", "name": "Grace", "activated": False},
            {"id": "3", "name": "Adam", "activated": True},
        ]
        components["default_list"] = [
            item["id"] for item in list_users(users, search="a", limit=10, page=1)
        ] == ["1", "2", "3"]
        components["activated_true"] = [
            item["id"]
            for item in list_users(
                users,
                search="a",
                activated=True,
                limit=10,
                page=1,
            )
        ] == ["1", "3"]
        components["activated_false"] = [
            item["id"]
            for item in list_users(
                users,
                activated=False,
                limit=10,
                page=1,
            )
        ] == ["2"]
        invalid_values = (
            {"limit": 0, "page": 1},
            {"limit": 101, "page": 1},
            {"limit": 10, "page": 0},
        )
        rejected = 0
        for values in invalid_values:
            try:
                list_users(users, **values)
            except ValueError:
                rejected += 1
        components["pagination_validation"] = rejected == len(invalid_values)
    except Exception:
        pass

    changed = changed_files()
    tests = [
        WORKSPACE / name
        for name in changed
        if name.startswith("tests/") and name.endswith(".py")
    ]
    components["public_tests"] = any(
        all(
            term in path.read_text(encoding="utf-8", errors="ignore").casefold()
            for term in ("activated", "limit", "page")
        )
        for path in tests
        if path.is_file()
    )
    readme = WORKSPACE / "README.md"
    components["documentation"] = readme.is_file() and all(
        term in readme.read_text(encoding="utf-8", errors="ignore").casefold()
        for term in ("activated", "limit", "page")
    )
    _print_result(components)


def _print_result(components: dict[str, bool]) -> None:
    score = sum(WEIGHTS[name] for name, passed in components.items() if passed)
    failed = [name for name, passed in components.items() if not passed]
    print(
        json.dumps(
            {
                "score": round(score, 6),
                "components": {name: float(passed) for name, passed in components.items()},
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
