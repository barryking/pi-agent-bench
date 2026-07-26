"""Webhook request handling."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def handle_webhook(body: bytes) -> dict[str, Any]:
    """Decode a webhook event."""
    event = json.loads(body)
    if not isinstance(event, dict) or not event.get("event"):
        raise ValueError("webhook body must contain an event")
    return event


def verify_webhook(
    body: bytes,
    *,
    signature: str,
    timestamp: int,
    secret: str,
    now: int,
    tolerance_seconds: int = 300,
) -> dict[str, Any]:
    """Authenticate a timestamped HMAC-SHA256 signature, then decode the body."""
    if abs(now - timestamp) > tolerance_seconds:
        raise ValueError("webhook timestamp is outside the allowed window")
    if not signature.startswith("sha256="):
        raise ValueError("webhook signature must use sha256")
    supplied = signature.removeprefix("sha256=")
    if len(supplied) != 64:
        raise ValueError("webhook signature is malformed")
    signed = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError("webhook signature is invalid")
    return handle_webhook(body)
