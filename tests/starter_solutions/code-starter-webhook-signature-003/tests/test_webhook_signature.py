import hashlib
import hmac

import pytest
from starter_service.webhooks import verify_webhook


def signature(body, timestamp, secret):
    value = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return "sha256=" + value


def test_valid_signature_and_invalid_signature():
    body = b'{"event":"created"}'
    assert verify_webhook(
        body,
        signature=signature(body, 1000, "secret"),
        timestamp=1000,
        secret="secret",
        now=1001,
    )["event"] == "created"
    with pytest.raises(ValueError):
        verify_webhook(
            body,
            signature="sha256=" + ("0" * 64),
            timestamp=1000,
            secret="secret",
            now=1001,
        )


def test_stale_timestamp_is_invalid():
    body = b'{"event":"created"}'
    with pytest.raises(ValueError):
        verify_webhook(
            body,
            signature=signature(body, 1000, "secret"),
            timestamp=1000,
            secret="secret",
            now=1301,
        )
