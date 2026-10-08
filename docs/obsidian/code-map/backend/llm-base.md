---
title: src/ai_doc_editor/llm/base.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/base.py`

Section: [[Backend]]

## Purpose

Provider interface and response validation (spec.md 4.1, 4.5).

## Classes

### `LLMError` (RuntimeError)

The backend failed (network, auth, process exit).


### `InvalidResponseError` (LLMError)

The backend answered, but not with valid JSON for the schema, even after a retry.


### `LLMProvider` (ABC)

One LLM backend. Subclasses implement `complete_text`; validation lives here.

Fields: `key`

- `def __init__(self, model: str)` — Stores the model name.
- `def complete_text(self, system: str, user: str, schema: dict) -> str` — Return the raw text reply. `schema` is a hint for backends that can enforce it.
- `def complete_json(self, system: str, user: str, schema: type[T], retries: int=1) -> T` — Call the backend and validate the reply; on failure retry with the error appended.

## Functions

- `def extract_json(text: str) -> str` — The JSON object inside a reply that may carry code fences or stray prose.
- `def strict_schema(model: type[BaseModel]) -> dict` — JSON schema with `$defs` inlined and `additionalProperties: false` (strict-mode safe).
