# Starter Python service

Webhooks use a `sha256=` signature over the timestamp, a dot, and the exact
body. The timestamp must be within 300 seconds. Invalid signatures are
rejected before JSON is handled.

Run the public tests with `pytest -q`.
