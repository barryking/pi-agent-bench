"""User listing behaviour."""

from __future__ import annotations

from typing import Any


def list_users(
    users: list[dict[str, Any]],
    *,
    search: str = "",
    activated: bool | None = None,
    limit: int = 50,
    page: int = 1,
) -> list[dict[str, Any]]:
    """Return one validated page, optionally filtered by name and activation."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be from 1 to 100")
    if page < 1:
        raise ValueError("page must be at least 1")
    matches = [
        user
        for user in users
        if search.casefold() in str(user.get("name", "")).casefold()
        and (activated is None or user.get("activated") is activated)
    ]
    start = (page - 1) * limit
    return matches[start : start + limit]
