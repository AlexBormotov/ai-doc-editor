---
title: src/ai_doc_editor/invariants.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/invariants.py`

Section: [[Backend]]

## Purpose

Structure invariants: the oracle that decides whether an edit preserved the layout.

## Functions

- `def _c14n(el: etree._Element | None) -> bytes` — Canonical XML bytes of an element (empty for None).
- `def _in_ins(run: etree._Element, p: etree._Element) -> bool` — True when a run sits inside a `w:ins` within the paragraph.
- `def rejected_text(p: etree._Element) -> str` — Paragraph text with every tracked change rejected (insertions dropped, deletions kept).
- `def unchanged_regions(old: str, new: str) -> list[tuple[int, int, int]]` — (old_start, new_start, length) of the text a word-level edit leaves untouched.
- `def char_formats(p: etree._Element) -> list[tuple[str, bytes]]` — (character, canonical rPr) for each visible character of the paragraph.
- `def _table_shape(tbl: etree._Element) -> list[list[tuple[str, str]]]` — Rows x cells of a table with `gridSpan` and `vMerge` per cell.
- `def _entries(root: etree._Element, names: set[str]) -> list[tuple]` — What a package index means, independent of how it is written.
- `def _non_story_parts_equal(a: Path, b: Path, story_names: set[str]) -> list[str]` — Compares every package part other than the story parts (XML canonically, indexes by meaning).
- `def check_docx(original: Path, edited: Path, expected: dict[str, str], tracked: bool) -> list[str]` — Violations of AC-1 (and AC-2 when `tracked`) between `original` and `edited`.
- `def _spans(page) -> list[dict]` — Non-empty text spans of a PDF page.
- `def _core(bbox)` — A span's box without the top and bottom 20%: line boxes of adjacent lines touch.
- `def _close(a, b, tol: float) -> bool` — Element-wise comparison of two coordinate tuples within a tolerance.
- `def check_pdf(original: Path, edited: Path, expected: dict[str, str], moved: list[tuple[int, Any, float]] | None=None, boxes: dict[str, Any] | None=None) -> list[str]` — Violations of AC-4 between `original` and `edited`.

## Related

- [[docx-reader]]
- [[docx-writer]]
- [[pdf-reader]]
- [[pdf-writer]]
