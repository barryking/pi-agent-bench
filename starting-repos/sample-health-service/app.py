"""A deliberately small synthetic WSGI service."""

from __future__ import annotations

from wsgiref.simple_server import make_server


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/":
        body = b"synthetic service\n"
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    body = b"not found\n"
    start_response(
        "404 Not Found",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def main() -> None:
    with make_server("0.0.0.0", 8080, application) as server:
        print("serving on http://0.0.0.0:8080", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
