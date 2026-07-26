#!/usr/bin/env python3
"""Protected checks for the owned webhook-signature starter case."""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/workspace")
sys.path.insert(0, str(WORKSPACE))
COMPONENTS = (
    "regression",
    "valid_signature",
    "invalid_signature",
    "timestamp_window",
    "constant_time_check",
    "public_tests",
    "documentation",
)


def rejected(call) -> bool:
    try:
        call()
    except ValueError:
        return True
    return False


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
        from starter_service.webhooks import verify_webhook

        body = b'{"event":"user.created","id":"42"}'
        secret = "starter-secret"
        now = 1_800_000_000
        timestamp = now - 10

        def sign(value: int) -> str:
            signed = f"{value}.".encode() + body
            digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
            return f"sha256={digest}"

        signature = sign(timestamp)
        values["valid_signature"] = verify_webhook(
            body,
            signature=signature,
            timestamp=timestamp,
            secret=secret,
            now=now,
        ) == {"event": "user.created", "id": "42"}
        values["invalid_signature"] = all(
            (
                rejected(
                    lambda: verify_webhook(
                        body,
                        signature="sha256=" + ("0" * 64),
                        timestamp=timestamp,
                        secret=secret,
                        now=now,
                    )
                ),
                rejected(
                    lambda: verify_webhook(
                        body,
                        signature="",
                        timestamp=timestamp,
                        secret=secret,
                        now=now,
                    )
                ),
            )
        )
        values["timestamp_window"] = all(
            (
                rejected(
                    lambda: verify_webhook(
                        body,
                        signature=sign(now - 301),
                        timestamp=now - 301,
                        secret=secret,
                        now=now,
                    )
                ),
                rejected(
                    lambda: verify_webhook(
                        body,
                        signature=sign(now + 301),
                        timestamp=now + 301,
                        secret=secret,
                        now=now,
                    )
                ),
            )
        )
    except Exception:
        pass

    source = WORKSPACE / "starter_service" / "webhooks.py"
    source_text = source.read_text(encoding="utf-8", errors="ignore") if source.is_file() else ""
    values["constant_time_check"] = "compare_digest" in source_text
    changed = _changed_files()
    test_text = "\n".join(
        (WORKSPACE / name).read_text(encoding="utf-8", errors="ignore").casefold()
        for name in changed
        if name.startswith("tests/") and name.endswith(".py") and (WORKSPACE / name).is_file()
    )
    values["public_tests"] = all(
        term in test_text for term in ("signature", "timestamp", "invalid")
    )
    readme = WORKSPACE / "README.md"
    documentation = (
        readme.read_text(encoding="utf-8", errors="ignore").casefold()
        if readme.is_file()
        else ""
    )
    values["documentation"] = all(
        term in documentation for term in ("signature", "sha256", "timestamp")
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
