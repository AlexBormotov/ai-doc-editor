---
title: src/ai_doc_editor/preview.py
tags:
  - code-map
  - frontend
---

# `src/ai_doc_editor/preview.py`

Section: [[Frontend]]

## Purpose

Page images for the before/after preview in the UI.

## Functions

- `def render_pages(doc: Path, out_dir: Path, tag: str, max_pages: int=4, dpi: int=80) -> list[Path]` — PNG files of the first pages of a PDF or DOCX (DOCX is rendered by LibreOffice).

## Related

- [[soffice]]
