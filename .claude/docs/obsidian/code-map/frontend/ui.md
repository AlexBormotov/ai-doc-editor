---
title: src/ai_doc_editor/ui.py
tags:
  - code-map
  - frontend
---

# `src/ai_doc_editor/ui.py`

Section: [[Frontend]]

## Purpose

Gradio UI: upload, instruction, provider; before/after previews, change table, downloads.

## Functions

- `def _models(provider: str)` — Refreshes the model dropdown when the provider changes.
- `def _report_fragment(html_text: str) -> str` — The report page's body and styles, for embedding in the dark UI.
- `def run(file, preset, instruction, provider, model, track, convert_to, progress=gr.Progress())` — Button handler: copies the upload into a run, calls `edit_document` with progress, renders previews, builds status, downloads and the dark Changes view.
- `def build_ui() -> gr.Blocks` — Gradio Blocks layout: inputs on the left; status, downloads and Preview/Changes/JSON tabs on the right.

## Related

- [[api]]
- [[editor]]
- [[llm-base]]
- [[llm-registry]]
- [[models]]
- [[presets]]
- [[preview]]
- [[settings]]
