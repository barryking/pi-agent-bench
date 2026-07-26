#!/usr/bin/env python3
"""Protected checks for the owned configuration-precedence starter case."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/workspace")
sys.path.insert(0, str(WORKSPACE))
COMPONENTS = (
    "regression",
    "command_line_false",
    "environment_zero",
    "file_empty_string",
    "fallback_order",
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
        from starter_service.config import load_config

        values["command_line_false"] = load_config(
            {"enabled": True},
            {"enabled": True},
            {"ENABLED": True},
            {"enabled": False},
        )["enabled"] is False
        values["environment_zero"] = load_config(
            {"workers": 4},
            {"workers": 3},
            {"WORKERS": 0},
            {},
        )["workers"] == 0
        values["file_empty_string"] = load_config(
            {"label": "default"},
            {"label": ""},
            {},
            {},
        )["label"] == ""
        values["fallback_order"] = load_config(
            {"a": 1, "b": 2, "c": 3, "d": 4},
            {"b": 20, "c": 30, "d": 40},
            {"C": 300, "D": 400},
            {"d": 4000},
        ) == {"a": 1, "b": 20, "c": 300, "d": 4000}
    except Exception:
        pass

    changed = _changed_files()
    test_text = "\n".join(
        (WORKSPACE / name).read_text(encoding="utf-8", errors="ignore").casefold()
        for name in changed
        if name.startswith("tests/") and name.endswith(".py") and (WORKSPACE / name).is_file()
    )
    values["public_tests"] = all(term in test_text for term in ("false", "0", "empty"))
    readme = WORKSPACE / "README.md"
    documentation = (
        readme.read_text(encoding="utf-8", errors="ignore").casefold()
        if readme.is_file()
        else ""
    )
    values["documentation"] = all(
        term in documentation for term in ("command line", "environment", "file", "default")
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
