from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .constants import BROWSER_BRIDGE_HOST, BROWSER_BRIDGE_PORT
from .time_limiter import TimeLimitEngine


def _allowed_origin(origin: str) -> bool:
    # Chromium extension service-worker requests with host permission may omit
    # Origin entirely. Normal web pages send their http(s) origin and remain rejected.
    return not origin or origin.startswith("chrome-extension://") or origin.startswith("moz-extension://")


class BrowserBridge:
    def __init__(
        self,
        engine: TimeLimitEngine,
        host: str = BROWSER_BRIDGE_HOST,
        port: int = BROWSER_BRIDGE_PORT,
    ):
        self.engine = engine
        self.host = host
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.error = ""

    @property
    def running(self) -> bool:
        return bool(self.server and self.thread and self.thread.is_alive())

    def start(self) -> bool:
        if self.running:
            return True
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "LumaGuardBridge/1"

            def _origin(self) -> str:
                return self.headers.get("Origin", "")

            def _headers(self, status: int = 200) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                origin = self._origin()
                if _allowed_origin(origin):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-LumaGuard-Companion")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()

            def _json(self, payload: dict[str, Any], status: int = 200) -> None:
                self._headers(status)
                self.wfile.write(json.dumps(payload).encode("utf-8"))

            def do_OPTIONS(self):  # noqa: N802
                if not _allowed_origin(self._origin()):
                    self._json({"ok": False}, 403)
                    return
                self._headers(204)

            def do_GET(self):  # noqa: N802
                if self.path != "/status" or not _allowed_origin(self._origin()):
                    self._json({"ok": False}, 404)
                    return
                self._json(
                    {"ok": True, "service": "LumaGuard", "version": 1, **bridge.engine.companion_appearance()}
                )

            def do_POST(self):  # noqa: N802
                if (
                    self.path not in ("/heartbeat", "/presence", "/decision")
                    or not _allowed_origin(self._origin())
                    or self.headers.get("X-LumaGuard-Companion") != "1"
                ):
                    self._json({"ok": False}, 403)
                    return
                try:
                    length = min(4096, int(self.headers.get("Content-Length", "0")))
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    browser = str(payload.get("browser", "browser"))
                    if self.path == "/presence":
                        bridge.engine.record_companion_presence(browser)
                        self._json(
                            {
                                "ok": True,
                                "connected": True,
                                "service": "LumaGuard",
                                **bridge.engine.companion_appearance(),
                            }
                        )
                        return
                    if self.path == "/decision":
                        if str(payload.get("action", "")) != "block_today":
                            self._json({"ok": False, "blocked": False, "error": "invalid_action"}, 400)
                            return
                        result = bridge.engine.block_site_today(str(payload.get("domain", "")))
                        result.update(bridge.engine.companion_appearance())
                        self._json(result, 200 if result.get("ok") else 400)
                        return
                    result = bridge.engine.record_web_heartbeat(
                        browser,
                        str(payload.get("domain", "")),
                        active=bool(payload.get("active", True)),
                    )
                    result.update(bridge.engine.companion_appearance())
                    self._json(result, 200 if result.get("ok") else 400)
                except (ValueError, TypeError, json.JSONDecodeError):
                    self._json({"ok": False, "blocked": False, "error": "invalid_request"}, 400)

            def log_message(self, _format: str, *_args) -> None:
                return

        try:
            self.server = ThreadingHTTPServer((self.host, self.port), Handler)
            self.server.daemon_threads = True
            self.thread = threading.Thread(target=self.server.serve_forever, name="LumaGuardBrowserBridge", daemon=True)
            self.thread.start()
            self.error = ""
            return True
        except OSError as exc:
            self.error = str(exc)
            self.server = None
            self.thread = None
            return False

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.server = None
        self.thread = None
