"""Serve the local RecallTrace reviewer demo."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from db import Db2Error
from extract_notice import draft_notice, load_model_settings, model_configured
from trace_notice import review_notice

ROOT = Path(__file__).resolve().parent
MAX_BODY_BYTES = 128 * 1024


class DemoHandler(BaseHTTPRequestHandler):
    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        if host not in hosts or (origin is not None and origin != f"http://{host}"):
            self.reply(403, {"error": "Open the demo directly on this Mac."})
            return False
        return True

    def reply(self, status, payload):
        content = json.dumps(payload).encode("utf-8")
        self.send_content(status, content, "application/json")

    def send_content(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if not self.local_request():
            return
        if self.path == "/":
            self.send_content(200, (ROOT / "web/index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/sample":
            notice = (ROOT / "fixtures/notice.txt").read_text(encoding="utf-8")
            selection = json.loads((ROOT / "fixtures/selection.json").read_text(encoding="utf-8"))
            self.reply(200, {"notice": notice, "selection": selection})
        elif self.path == "/api/status":
            self.reply(200, {"draft_available": model_configured()})
        else:
            self.reply(404, {"error": "Page not found."})

    def do_POST(self):
        if not self.local_request():
            return
        if self.path not in {"/api/trace", "/api/draft"}:
            self.reply(404, {"error": "Page not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "Send a JSON request."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY_BYTES:
                raise ValueError
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            self.reply(400, {"error": "Send a JSON object within the request size limit."})
            return

        notice = data.get("notice")
        try:
            if self.path == "/api/trace":
                self.reply(200, review_notice(notice, data.get("selection"), lookup=True))
            elif model_configured():
                self.reply(200, {"selection": draft_notice(notice)})
            else:
                self.reply(503, {"error": "The model is not configured. Enter the evidence manually."})
        except ValueError as error:
            self.reply(400, {"error": str(error)})
        except Db2Error:
            self.reply(503, {"error": "Db2 lookup failed. Check that TESTDB is running and the sample data is loaded."})
        except Exception:
            self.reply(502, {"error": "The request could not complete. Try again or enter the evidence manually."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_model_settings()
    with ThreadingHTTPServer(("127.0.0.1", args.port), DemoHandler) as server:
        print(f"RecallTrace demo at http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
