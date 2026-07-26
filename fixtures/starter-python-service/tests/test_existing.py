from starter_service.config import load_config
from starter_service.idempotency import UserRepository
from starter_service.users import list_users
from starter_service.webhooks import handle_webhook


def test_user_search_and_paging():
    users = [
        {"id": "1", "name": "Ada", "activated": True},
        {"id": "2", "name": "Grace", "activated": False},
        {"id": "3", "name": "Adam", "activated": True},
    ]

    assert [user["id"] for user in list_users(users, search="ad", limit=1)] == ["1"]


def test_configuration_uses_highest_non_empty_value():
    result = load_config(
        {"port": 8000},
        {"port": 8001},
        {"PORT": 8002},
        {"port": 8003},
    )

    assert result["port"] == 8003


def test_webhook_decoding():
    assert handle_webhook(b'{"event":"user.created","id":"1"}')["id"] == "1"


def test_plain_user_creation(tmp_path):
    repository = UserRepository(tmp_path / "users.sqlite")

    status, response = repository.create_user({"id": "1", "name": "Ada"})

    assert status == 201
    assert response == {"id": "1", "name": "Ada"}
    assert repository.count_users() == 1
