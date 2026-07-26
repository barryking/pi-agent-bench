#!/usr/bin/env python3
"""Protected checks for the owned Node pagination-client starter case."""

from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
from pathlib import Path

WORKSPACE = Path("/workspace")
COMPONENTS = (
    "regression",
    "collects_pages",
    "passes_signal",
    "repeated_cursor",
    "maximum_pages",
    "public_tests",
    "documentation",
)


def run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def main() -> None:
    values = {name: False for name in COMPONENTS}
    values["regression"] = run(["npm", "test"]).returncode == 0
    with tempfile.TemporaryDirectory(prefix="pagination-probe-") as temporary:
        probe = Path(temporary) / "probe.mjs"
        module_url = (WORKSPACE / "src" / "client.js").as_uri()
        probe.write_text(
            textwrap.dedent(
                f"""
                import {{ fetchAllPages }} from {json.dumps(module_url)};

                const signal = new AbortController().signal;
                const calls = [];
                const items = await fetchAllPages(async request => {{
                  calls.push(request);
                  if (request.cursor === null) return {{ items: [1, 2], nextCursor: "b" }};
                  return {{ items: [3], nextCursor: null }};
                }}, {{ signal }});

                async function rejects(callback) {{
                  try {{ await callback(); return false; }}
                  catch {{ return true; }}
                }}

                const repeated = await rejects(() => fetchAllPages(async request => (
                  request.cursor === null
                    ? {{ items: [1], nextCursor: "same" }}
                    : {{ items: [2], nextCursor: "same" }}
                )));
                const maximum = await rejects(() => fetchAllPages(
                  async request => ({{
                    items: [request.cursor],
                    nextCursor: String(Math.random())
                  }}),
                  {{ maxPages: 2 }}
                ));
                console.log(JSON.stringify({{
                  collects_pages: JSON.stringify(items) === JSON.stringify([1, 2, 3]),
                  passes_signal: calls.length === 2 && calls.every(call => call.signal === signal),
                  repeated_cursor: repeated,
                  maximum_pages: maximum
                }}));
                """
            ),
            encoding="utf-8",
        )
        completed = run(["node", str(probe)])
        if completed.returncode == 0:
            try:
                payload = json.loads(completed.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                payload = {}
            for name in ("collects_pages", "passes_signal", "repeated_cursor", "maximum_pages"):
                values[name] = payload.get(name) is True

    changed = _changed_files()
    test_text = "\n".join(
        (WORKSPACE / name).read_text(encoding="utf-8", errors="ignore").casefold()
        for name in changed
        if name.startswith("test/") and name.endswith(".js") and (WORKSPACE / name).is_file()
    )
    values["public_tests"] = all(
        term in test_text for term in ("nextcursor", "signal", "repeated")
    )
    readme = WORKSPACE / "README.md"
    documentation = (
        readme.read_text(encoding="utf-8", errors="ignore").casefold()
        if readme.is_file()
        else ""
    )
    values["documentation"] = all(
        term in documentation for term in ("cursor", "signal", "maxpages")
    )
    _print(values)


def _changed_files() -> list[str]:
    run(
        ["git", "-c", "safe.directory=/workspace", "add", "-N", "."],
        timeout=20,
    )
    return run(
        ["git", "-c", "safe.directory=/workspace", "diff", "--name-only", "HEAD"],
        timeout=20,
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
