---
title: src/ai_doc_editor/docx/reader.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/docx/reader.py`

Section: [[Backend]]

## Purpose

Split a DOCX into paragraph segments (spec.md 4.2).

## Classes

### `DocxDocument`

A parsed DOCX: the python-docx object plus a map from segment ID to `w:p` element.

Fields: `path`, `doc`, `segments`, `paragraphs`

- `def save(self, path: Path) -> None` — Saves the (edited) python-docx document.

## Functions

- `def q(tag: str) -> str` — Expands `prefix:local` into a Clark-notation tag (`{ns}local`).
- `def own_runs(p: etree._Element) -> list[etree._Element]` — Runs whose nearest enclosing paragraph is `p`, in document order.
- `def _nearest_paragraph(el: etree._Element) -> etree._Element | None` — Closest enclosing `w:p` of an element (text boxes nest paragraphs).
- `def run_text(r: etree._Element) -> str` — Visible text of a run: `w:t`, tabs, breaks, non-breaking hyphens.
- `def paragraph_text(p: etree._Element) -> str` — Text of a paragraph's own runs (deleted text excluded).
- `def _skip_reason(p: etree._Element) -> str | None` — Why a paragraph must not be edited: fields, note references, equations, existing revisions, `mc:Fallback` copies; else None.
- `def _story_parts(doc) -> list[tuple[str, etree._Element]]` — Main document, header and footer parts as (name, root) in a stable order.
- `def read_docx(path: Path) -> DocxDocument` — Parses a DOCX into segments: every non-empty `w:p` of every story part, with a stable ID `part/p/N`.

## Related

- [[models]]
