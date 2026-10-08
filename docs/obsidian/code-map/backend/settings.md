---
title: src/ai_doc_editor/settings.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/settings.py`

Section: [[Backend]]

## Purpose

Runtime configuration from environment variables and `.env` (see `.env.example`).

## Classes

### `Settings` (BaseSettings)

Environment / `.env` configuration (providers, limits, runs dir).

Fields: `default_provider`, `default_model`, `ollama_base_url`, `lmstudio_base_url`, `openai_api_key`, `anthropic_api_key`, `google_api_key`, `cli_bridge_url`, `cli_bridge_token`, `max_pages`, `max_upload_mb`, `batch_chars`, `layout_tolerance_pt`, `runs_dir`, `llm_timeout_s`


## Functions

- `def get_settings() -> Settings` — Cached `Settings` instance.
