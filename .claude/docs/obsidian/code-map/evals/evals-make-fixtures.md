---
title: evals/make_fixtures.py
tags:
  - code-map
  - evals
---

# `evals/make_fixtures.py`

Section: [[Evals]]

## Purpose

Generate the test documents under evals/fixtures/.

## Functions

- `def _add_hyperlink(paragraph, url: str, text: str) -> None` — Appends an external hyperlink run to a paragraph.
- `def _add_page_field(paragraph) -> None` — Appends a `PAGE` field (`w:fldSimple`).
- `def _add_text_box(paragraph, text: str) -> None` — Inline DrawingML text box (wps:wsp) holding one paragraph.
- `def _set_columns(section, num: int) -> None` — Sets the number of text columns of a section.
- `def make_report_en(path: Path) -> None` — English report DOCX: styles, mixed runs, hyperlink, lists, merged table, text box, landscape 2-column section, header/footer.
- `def make_contract_ru(path: Path) -> None` — Russian contract DOCX with names, phones, e-mails and a typo (anonymise/proofread tasks).
- `def make_layout_pdf(path: Path) -> None` — A4 page with text blocks at exact positions, an image and vector graphics.
- `def make_sections_pdf(path: Path) -> None` — Two sections, every line its own text object (as browsers print), with room to reflow.
- `def main() -> None` — Writes all fixtures; renders PDF and DOC copies when LibreOffice is available.

## Related

- [[soffice]]
