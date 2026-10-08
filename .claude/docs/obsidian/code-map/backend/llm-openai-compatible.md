---
title: src/ai_doc_editor/llm/openai_compatible.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/openai_compatible.py`

Section: [[Backend]]

## Purpose

Ollama, LM Studio, OpenAI and Google Gemini through one OpenAI-compatible client.

## Classes

### `OpenAICompatibleProvider` (LLMProvider)

One adapter for every OpenAI-compatible endpoint.

- `def __init__(self, key: str, model: str, base_url: str | None, api_key: str, timeout: float)` — OpenAI SDK client for a base URL (Ollama, LM Studio, OpenAI, Gemini).
- `def complete_text(self, system: str, user: str, schema: dict) -> str` — Chat completion with `json_schema` response format (falls back without it on 400); Ollama gets `reasoning_effort: none`.
- `def list_models(self) -> list[str]` — Model IDs from `/models`, or an empty list.

## Related

- [[llm-base]]
