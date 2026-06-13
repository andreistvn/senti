"""
SentiNet Tray — loopback HTTP API.

A tiny stdlib JSON server (no Flask/FastAPI) the web dashboard polls for live
state. Bound to 127.0.0.1 so it is never exposed off the machine. CORS is fully
permissive because the dashboard is served from a different origin (Vite dev
server) and we want it to "just work" after export.

Endpoints:
    GET  /api/status   current protection state
    POST /api/toggle   flip protection, return new status
    GET  /api/stats    counters + telemetry + bayanihan + last threat
    GET  /api/events   recent detection-log rows
    GET  /api/health   daemon services list
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import API_HOST, API_PORT


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        # silence the default per-request stderr logging
        def log_message(self, *args):
            pass

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _send_json(self, payload, code=200):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            # CORS preflight for POST /api/toggle
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/api/status":
                self._send_json(state.status_dict())
            elif path == "/api/stats":
                self._send_json(state.stats_dict())
            elif path == "/api/events":
                self._send_json({"events": state.events_list()})
            elif path == "/api/health":
                self._send_json({"services": state.health_list()})
            elif path in ("", "/api"):
                self._send_json({"name": "SentiNet Tray API", "ok": True})
            else:
                self._send_json({"error": "not found"}, code=404)

        def do_POST(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            # drain any request body so the socket stays clean
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            if path == "/api/toggle":
                state.toggle()
                self._send_json(state.status_dict())
            else:
                self._send_json({"error": "not found"}, code=404)

    return Handler


class ApiServer:
    def __init__(self, state):
        self._server = ThreadingHTTPServer((API_HOST, API_PORT), make_handler(state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
