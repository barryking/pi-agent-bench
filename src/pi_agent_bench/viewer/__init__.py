"""Local-only server for the Pi Agent Bench dashboard."""

from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from socketserver import TCPServer
from typing import Any
from urllib.parse import urlparse

from ..reporting import build_report, write_report, write_visualizer_exports
from ..result_records import load_records


class LocalDashboardServer(ThreadingHTTPServer):
    """HTTP server that avoids a potentially slow reverse-DNS lookup on startup."""

    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        self.server_name = str(self.server_address[0])
        self.server_port = int(self.server_address[1])


def prepare_dashboard(results_dir: str | Path) -> Path:
    """Refresh all derived reports and return the dashboard HTML asset."""
    destination = Path(results_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    metrics_path = destination / "metrics.jsonl"
    has_existing_metrics = metrics_path.is_file() and metrics_path.stat().st_size > 0
    record_paths = [
        path for path in destination.glob("*.json") if path.name != "summary.json"
    ]
    records = load_records(destination) if record_paths else []
    if records:
        write_report(build_report(destination), destination / "summary.md")
        write_visualizer_exports(destination)
    elif not has_existing_metrics:
        raise ValueError(f"{destination}: no run record JSON files found")
    return Path(str(files(__package__).joinpath("index.html")))


def make_dashboard_server(
    results_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> LocalDashboardServer:
    destination = Path(results_dir).resolve()
    dashboard_path = prepare_dashboard(destination)

    routes = {
        "/": (dashboard_path, "text/html; charset=utf-8"),
        "/index.html": (dashboard_path, "text/html; charset=utf-8"),
        "/styles.css": (
            Path(str(files(__package__).joinpath("styles.css"))),
            "text/css; charset=utf-8",
        ),
        "/core.js": (
            Path(str(files(__package__).joinpath("core.js"))),
            "text/javascript; charset=utf-8",
        ),
        "/statistics.js": (
            Path(str(files(__package__).joinpath("statistics.js"))),
            "text/javascript; charset=utf-8",
        ),
        "/charts.js": (
            Path(str(files(__package__).joinpath("charts.js"))),
            "text/javascript; charset=utf-8",
        ),
        "/app.js": (
            Path(str(files(__package__).joinpath("app.js"))),
            "text/javascript; charset=utf-8",
        ),
        "/metrics.jsonl": (destination / "metrics.jsonl", "application/x-ndjson"),
        "/runs.csv": (destination / "runs.csv", "text/csv; charset=utf-8"),
        "/summary.json": (destination / "summary.json", "application/json"),
    }

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            target = routes.get(route)
            if target is None:
                self.send_error(404)
                return
            path, content_type = target
            try:
                payload = path.read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return LocalDashboardServer((host, port), DashboardHandler)


def serve_dashboard(
    results_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    open_browser: bool = True,
) -> None:
    """Generate reports and serve the dashboard until interrupted."""
    server = make_dashboard_server(results_dir, host, port)
    actual_host, actual_port = server.server_address[:2]
    display_host = "127.0.0.1" if actual_host in {"0.0.0.0", "::"} else actual_host
    url = f"http://{display_host}:{actual_port}/"
    print(f"dashboard: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.1, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
