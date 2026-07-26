from app import application


def request(path: str) -> tuple[str, dict[str, str], bytes]:
    response: dict[str, object] = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    body = b"".join(application({"PATH_INFO": path}, start_response))
    return str(response["status"]), dict(response["headers"]), body


def test_homepage_is_available():
    status, headers, body = request("/")

    assert status == "200 OK"
    assert headers["Content-Type"].startswith("text/plain")
    assert body == b"synthetic service\n"


def test_unknown_path_is_not_found():
    status, _, _ = request("/missing")

    assert status == "404 Not Found"
