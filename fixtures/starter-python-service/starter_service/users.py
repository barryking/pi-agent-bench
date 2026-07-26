"""User listing behaviour."""

from __future__ import annotations

from typing import Any


def list_users(
    users: list[dict[str, Any]],
    *,
    search: str = "",
    limit: int = 50,
    page: int = 1,
) -> list[dict[str, Any]]:
    """Return one page of users, optionally filtered by name."""
    matches = [
        user
        for user in users
        if search.casefold() in str(user.get("name", "")).casefold()
    ]
    start = (page - 1) * limit
    return matches[start : start + limit]
