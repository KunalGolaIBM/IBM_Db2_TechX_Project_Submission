"""A small fake model server for demos.

It speaks the OpenAI chat completions shape, so the real
gateway transport talks to it without any change. That
makes the whole agent path testable without an API key
and without a network.

The answers are simple on purpose:

- The Diagnostician says the blank value rule.
- The Fixer rewrites a filter on an empty string into a
  filter on the length, which means the same rows on both
  databases.

Run it:

    python scripts/fake_model_server.py --port 8099
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

DIAGNOSIS = (
    "Db2 treats an empty string and a string of blanks as equal, "
    "so the filter matches more rows than it does on Postgres."
)


def answer_for(system: str, user: str) -> str:
    """Return the answer for one request."""
    if "You explain why" in system:
        return DIAGNOSIS
    if "You rewrite a Db2 query" in system:
        current = ""
        if "current Db2 SQL:" in user:
            current = user.split("current Db2 SQL:", 1)[1].strip()
        if "country = ''" in current:
            return current.replace("country = ''", "LENGTH(country) = 0")
        if "= ''" in current:
            return current.replace("= ''", "= ''")
        return current
    if "You translate" in system:
        return user.strip().splitlines()[-1]
    return ""


class Handler(BaseHTTPRequestHandler):
    """Answer one chat completion request."""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        messages = payload.get("messages", [])
        system = ""
        user = ""
        for message in messages:
            if message.get("role") == "system":
                system = message.get("content", "")
            else:
                user = message.get("content", "")
        text = answer_for(system, user)
        body = json.dumps(
            {
                "choices": [{"message": {"content": text}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        """Keep the output quiet."""


def main() -> int:
    """Run the fake model server."""
    parser = argparse.ArgumentParser(prog="fake_model_server")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"fake model server on http://127.0.0.1:{args.port}/v1")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
