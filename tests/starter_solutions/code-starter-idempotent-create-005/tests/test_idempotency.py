import pytest
from starter_service.idempotency import IdempotencyConflict, UserRepository


def test_idempotency_replay_and_conflict(tmp_path):
    repository = UserRepository(tmp_path / "users.sqlite")
    payload = {"id": "1", "name": "Ada"}

    first = repository.create_user(payload, idempotency_key="request-1")
    replay = repository.create_user(payload, idempotency_key="request-1")

    assert replay == first
    assert repository.count_users() == 1
    with pytest.raises(IdempotencyConflict):
        repository.create_user(
            {"id": "2", "name": "Grace"},
            idempotency_key="request-1",
        )


@pytest.mark.parametrize("key", ["", "x" * 129])
def test_idempotency_key_limit(key, tmp_path):
    repository = UserRepository(tmp_path / "users.sqlite")
    with pytest.raises(ValueError):
        repository.create_user({"id": "1"}, idempotency_key=key)
