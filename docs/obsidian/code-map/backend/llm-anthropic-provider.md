---
title: src/ai_doc_editor/llm/anthropic_provider.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/anthropic_provider.py`

Section: [[Backend]]

## Purpose

Anthropic API through the official SDK, with structured output.

## Classes

### `AnthropicProvider` (LLMProvider)

Anthropic API through the official SDK, structured output.

- `def __init__(self, model: str, api_key: str, timeout: float)` — Creates the Anthropic SDK client with the key and timeout.
- `def complete_text(self, system: str, user: str, schema: dict) -> str` — `messages.create` with `output_config.format` = JSON schema; raises on API error or refusal.
- `def list_models(self) -> list[str]` — Model IDs from the Models API, or an empty list.

## Related

- [[llm-base]]
