"""SQLite-backed durable and idempotent user creation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class IdempotencyConflict(Exception):
    """A key was reused with a different payload."""


class UserRepository:
    """Store users and idempotency outcomes in SQLite."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users "
                "(id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS idempotency_requests ("
                "key TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                "status INTEGER NOT NULL, response TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def create_user(
        self,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Create once, or replay the stored result for the same key and body."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if idempotency_key is None:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO users (id, payload) VALUES (?, ?)",
                    (str(payload["id"]), canonical),
                )
            return 201, dict(payload)
        if not 1 <= len(idempotency_key) <= 128:
            raise ValueError("idempotency key must contain 1 to 128 characters")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = connection.execute(
                "SELECT payload, status, response FROM idempotency_requests "
                "WHERE key = ?",
                (idempotency_key,),
            ).fetchone()
            if stored is not None:
                if stored[0] != canonical:
                    raise IdempotencyConflict(idempotency_key)
                connection.commit()
                return int(stored[1]), json.loads(stored[2])
            response = dict(payload)
            response_json = json.dumps(response, sort_keys=True, separators=(",", ":"))
            connection.execute(
                "INSERT INTO users (id, payload) VALUES (?, ?)",
                (str(payload["id"]), canonical),
            )
            connection.execute(
                "INSERT INTO idempotency_requests "
                "(key, payload, status, response) VALUES (?, ?, ?, ?)",
                (idempotency_key, canonical, 201, response_json),
            )
            connection.commit()
            return 201, response
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def count_users(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0])
