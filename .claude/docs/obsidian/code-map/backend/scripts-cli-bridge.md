---
title: scripts/cli_bridge.py
tags:
  - code-map
  - backend
---

# `scripts/cli_bridge.py`

Section: [[Backend]]

## Purpose

Host-side bridge that lets the Docker app use your logged-in `claude`, `codex` and `agy` CLIs.

## Classes

### `Handler` (BaseHTTPRequestHandler)

HTTP handler of the bridge; `token` and `timeout_s` are set at start-up.

- `def _reply(self, status: int, body: dict) -> None` — Sends a JSON response with status code.
- `def do_POST(self) -> None` — `POST /run`: checks bearer token, size and CLI name, runs the CLI, returns `{text}`.
- `def log_message(self, fmt: str, *args) -> None` — Logs requests to stderr with a `cli-bridge:` prefix.

## Functions

- `def main() -> None` — Requires `CLI_BRIDGE_TOKEN`, binds `127.0.0.1:<port>` and serves forever.

## Related

- [[llm-base]]
- [[llm-cli-provider]]
