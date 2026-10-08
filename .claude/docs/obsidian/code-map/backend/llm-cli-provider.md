---
title: src/ai_doc_editor/llm/cli_provider.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/cli_provider.py`

Section: [[Backend]]

## Purpose

Subscription CLIs (`claude`, `codex`, `agy`) in headless mode (spec.md 4.5).

## Classes

### `CliProvider` (LLMProvider)

Subscription CLI provider (`cli:claude`, `cli:codex`, `cli:agy`).

- `def __init__(self, cli: str, model: str, timeout: float, bridge_url: str='', bridge_token: str='')` — Remembers CLI name, model, timeout and optional bridge URL/token.
- `def complete_text(self, system: str, user: str, schema: dict) -> str` — Runs the CLI locally, or POSTs to the host bridge when `bridge_url` is set.

## Functions

- `def run_cli(cli: str, model: str, system: str, user: str, timeout: float) -> str` — Run one headless CLI call on this machine and return the reply text.

## Related

- [[llm-base]]
