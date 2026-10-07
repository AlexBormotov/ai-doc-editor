"""Host-side bridge that lets the Docker app use your logged-in `claude`, `codex` and `agy` CLIs.

Run on the host (not in Docker):

    set CLI_BRIDGE_TOKEN=<random string>        (PowerShell: $env:CLI_BRIDGE_TOKEN="...")
    uv run python scripts/cli_bridge.py --port 8765

and give the container CLI_BRIDGE_URL=http://host.docker.internal:8765 plus the same token.

Security: binds to 127.0.0.1 only, requires the bearer token, accepts only the three CLI names
(never a command line), and runs each CLI with tools disabled or read-only in an empty temp dir.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ai_doc_reader.llm.base import LLMError  # noqa: E402
from ai_doc_reader.llm.cli_provider import CLIS, run_cli  # noqa: E402

MAX_BODY = 2_000_000


class Handler(BaseHTTPRequestHandler):
    token = ""
    timeout_s = 900.0

    def _reply(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth, f"Bearer {self.token}"):
            return self._reply(401, {"error": "bad token"})
        if self.path != "/run":
            return self._reply(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            return self._reply(413, {"error": "request too large"})
        try:
            req = json.loads(self.rfile.read(length))
            cli, model = req["cli"], str(req.get("model", ""))
            system, user = str(req["system"]), str(req["user"])
        except (ValueError, KeyError):
            return self._reply(400, {"error": "expected {cli, model, system, user}"})
        if cli not in CLIS:
            return self._reply(400, {"error": f"cli must be one of {CLIS}"})
        try:
            text = run_cli(cli, model, system, user, self.timeout_s)
        except LLMError as e:
            return self._reply(502, {"error": str(e)})
        return self._reply(200, {"text": text})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"cli-bridge: {fmt % args}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    token = os.environ.get("CLI_BRIDGE_TOKEN", "")
    if len(token) < 16:
        sys.exit("set CLI_BRIDGE_TOKEN to a random string of at least 16 characters")
    Handler.token, Handler.timeout_s = token, args.timeout
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"cli-bridge on http://127.0.0.1:{args.port} (container: host.docker.internal)")
    server.serve_forever()


if __name__ == "__main__":
    main()
