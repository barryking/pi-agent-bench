import pytest
from starter_service.users import list_users

USERS = [
    {"id": "1", "name": "Ada", "activated": True},
    {"id": "2", "name": "Grace", "activated": False},
]


def test_activated_filter_and_default():
    assert len(list_users(USERS)) == 2
    assert [user["id"] for user in list_users(USERS, activated=True)] == ["1"]
    assert [user["id"] for user in list_users(USERS, activated=False)] == ["2"]


@pytest.mark.parametrize("values", [{"limit": 0}, {"limit": 101}, {"page": 0}])
def test_limit_and_page_boundaries(values):
    with pytest.raises(ValueError):
        list_users(USERS, **values)
