# Starter Python service

`create_user` accepts an optional idempotency key containing 1 to 128
characters. The first request is stored durably. An identical replay returns
the original result. Reusing the key with another payload raises an
`IdempotencyConflict`.

Run the public tests with `pytest -q`.
