---
title: src/ai_doc_editor/docx/redline.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/docx/redline.py`

Section: [[Backend]]

## Purpose

Tracked-change (redline) elements: `w:ins` and `w:del` (spec.md 4.2).

## Classes

### `Redline`

Creates revision wrappers that share one author and timestamp, with unique IDs.

- `def __init__(self, author: str=AUTHOR, start_id: int=900000)` — Fixes author, timestamp and the starting revision ID.
- `def _wrapper(self, tag: str) -> etree._Element` — New `w:ins`/`w:del` element with ID, author and date.
- `def wrap_insert(self, run: etree._Element) -> etree._Element` — Wraps a new run in `w:ins`.
- `def wrap_delete(self, run: etree._Element) -> None` — Wrap `run` in place with `w:del`; its `w:t` children become `w:delText`.

## Related

- [[docx-reader]]
