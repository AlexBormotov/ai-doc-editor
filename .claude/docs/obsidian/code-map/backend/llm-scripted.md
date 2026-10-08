---
title: src/ai_doc_editor/llm/scripted.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/scripted.py`

Section: [[Backend]]

## Purpose

Deterministic provider for tests and the invariant eval: no model, regex rules only.

## Classes

### `ScriptedProvider` (LLMProvider)

Applies `rules` [(pattern, replacement), ...] to every segment and reports the changes.

- `def __init__(self, rules: list[tuple[str, str]] | None=None, raw_reply: str | None=None)` — Compiles regex rules, or keeps a fixed raw reply.
- `def complete_text(self, system: str, user: str, schema: dict) -> str` — Applies rules to each segment and returns changed ones; answers scope requests with `all`.

## Related

- [[llm-base]]
- [[llm-prompts]]
