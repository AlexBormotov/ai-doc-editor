---
title: src/ai_doc_editor/docx/writer.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/docx/writer.py`

Section: [[Backend]]

## Purpose

Apply edits to DOCX paragraphs in place (spec.md 4.2, DR-2).

## Classes

### `_Atom`

A run holding exactly one content child, with its character span in the paragraph.

Fields: `run`, `start`, `end`

- `def is_text(self) -> bool` — True when the atom carries characters (non-empty span).

## Functions

- `def _content_len(child: etree._Element) -> int` — Character length a run child contributes (`w:t` text, 1 for tab/break).
- `def _split_run_children(run: etree._Element) -> list[etree._Element]` — Split a run into runs that each hold one content child; returns the new runs in order.
- `def _atoms(p: etree._Element) -> list[_Atom]` — Splits a paragraph's runs into single-child atoms with character offsets.
- `def _split_atom(atoms: list[_Atom], pos: int) -> None` — Ensure no text atom spans `pos` strictly inside it (only `w:t` atoms can be split).
- `def _new_run(text: str, fmt_run: etree._Element | None) -> etree._Element` — New run with the formatting of a neighbour run; tabs and breaks become `w:tab`/`w:br`.
- `def _outer(el: etree._Element) -> etree._Element` — The element to position against: the run, or its `w:del` wrapper if it was deleted.
- `def diff_ops(old: str, new: str) -> list[tuple[int, int, str]]` — Non-equal regions as (old_start, old_end, replacement), from a token-level diff.
- `def apply_paragraph_edit(p: etree._Element, new_text: str, redline: Redline | None) -> None` — Applies one edit to one paragraph: diff, split atoms at op boundaries, insert/delete (or track) runs in reverse order.
- `def apply_edits(doc: DocxDocument, edits: list[Edit], track_changes: bool=True) -> list[Change]` — Apply validated edits to `doc` in place and return one Change per edit.

## Related

- [[docx-reader]]
- [[docx-redline]]
- [[models]]
