---
title: src/ai_doc_editor/convert.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/convert.py`

Section: [[Backend]]

## Purpose

Format conversion behind a layout gate (spec.md 4.4, AC-8, DR-4, DR-7).

## Classes

### `GateResult` (BaseModel)

Layout gate verdict: passed, target, page counts, failures, note.

Fields: `passed`, `target`, `pages_source`, `pages_candidate`, `failures`, `note`


### `Conversion`

A converted file with its gate result and the render used by the gate.

Fields: `path`, `gate`, `rendered`, `extra`


## Functions

- `def _words(page: pymupdf.Page) -> list[tuple[str, pymupdf.Rect]]` — Words of a page with their rectangles, in reading order.
- `def _content_box(page: pymupdf.Page) -> pymupdf.Rect | None` — Union of all word rectangles on a page (used for margin checks).
- `def layout_gate(source_pdf: Path, candidate_pdf: Path, tol_pt: float, target: str) -> GateResult` — Compare a converted document's rendering with the source (AC-8).
- `def docx_to_pdf(docx: Path, out_dir: Path) -> Conversion` — DOCX -> PDF via LibreOffice; passes the gate by definition (reference renderer, DR-7).
- `def pdf_to_docx(pdf: Path, out_dir: Path, tol_pt: float) -> Conversion` — PDF -> DOCX via pdf2docx, renders the DOCX back with LibreOffice and runs `layout_gate`.

## Related

- [[soffice]]
