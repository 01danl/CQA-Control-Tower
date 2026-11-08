#!/usr/bin/env python3
"""Local-only benchmark dashboard server (127.0.0.1 by default).

Serves the static vanilla-JS viewer from tools/benchmark_dashboard and a
read-only JSON endpoint built from experiment workspaces. It never serves
credentials, audio URLs or anything outside the workspace payload: the collect
step already strips signed URLs and the payload contains only experiment and
provenance-verified baseline data.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "tools" / "benchmark_dashboard"
WORKSPACE = REPO / "backend" / ".experiments-private"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def list_experiments() -> list[dict]:
    items = []
    if WORKSPACE.exists():
        for path in sorted(WORKSPACE.glob("*/dashboard_data.json")):
            try:
                payload = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            models = payload.get("models", [])
            records = payload.get("experiments", [])
            items.append(
                {
                    "experiment_id": payload.get("experiment_id", path.parent.name),
                    "models": models,
                    "completed": sum(1 for r in records if r.get("status") == "completed"),
                    "total": len(records),
                }
            )
    return items


def experiment_payload(experiment_id: str) -> dict | None:
    path = (WORKSPACE / experiment_id / "dashboard_data.json").resolve()
    if WORKSPACE.resolve() not in path.parents or not path.exists():
        return None
    return json.loads(path.read_text())


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        route = urlparse(self.path).path
        if route == "/api/experiments":
            body = json.dumps({"experiments": list_experiments()}).encode()
            self._send(200, body, "application/json")
            return
        if route.startswith("/api/data/"):
            payload = experiment_payload(route.removeprefix("/api/data/"))
            if payload is None:
                self._send(404, b'{"error": "unknown experiment"}', "application/json")
                return
            self._send(200, json.dumps(payload).encode(), "application/json")
            return
        target = STATIC / (route.lstrip("/") or "index.html")
        if not target.is_file() or STATIC.resolve() not in target.resolve().parents:
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, target.read_bytes(), MIME.get(target.suffix, "application/octet-stream"))

    def log_message(self, *args) -> None:  # keep console quiet
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Benchmark dashboard: http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
