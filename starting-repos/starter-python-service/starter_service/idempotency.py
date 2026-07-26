"""SQLite-backed user creation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class UserRepository:
    """Store users in a small SQLite database."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users "
                "(id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def create_user(
        self,
        payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        """Create one user and return its HTTP-like status and response."""
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO users (id, payload) VALUES (?, ?)",
                (str(payload["id"]), body),
            )
        return 201, dict(payload)

    def count_users(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0])
