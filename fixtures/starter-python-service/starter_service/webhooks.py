"""Webhook request handling."""

from __future__ import annotations

import json
from typing import Any


def handle_webhook(body: bytes) -> dict[str, Any]:
    """Decode a webhook event."""
    event = json.loads(body)
    if not isinstance(event, dict) or not event.get("event"):
        raise ValueError("webhook body must contain an event")
    return event
