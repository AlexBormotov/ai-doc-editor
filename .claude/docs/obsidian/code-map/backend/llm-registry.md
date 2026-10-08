---
title: src/ai_doc_editor/llm/registry.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/registry.py`

Section: [[Backend]]

## Purpose

Provider keys -> configured provider instances (spec.md 4.5).

## Functions

- `def get_provider(key: str, model: str, settings: Settings | None=None) -> LLMProvider` — Provider instance for a key (`ollama`, `lmstudio`, `openai`, `google`, `anthropic`, `cli:*`) from settings.
- `def list_models(key: str, settings: Settings | None=None) -> list[str]` — Models the backend reports (live for local servers and APIs), else a fallback list.

## Related

- [[llm-anthropic-provider]]
- [[llm-base]]
- [[llm-cli-provider]]
- [[llm-openai-compatible]]
- [[settings]]
