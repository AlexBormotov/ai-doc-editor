---
title: src/ai_doc_editor/pdf/writer.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/pdf/writer.py`

Section: [[Backend]]

## Purpose

Rewrite edited PDF segments inside their original rectangles (spec.md 4.3, AC-4, AC-5).

## Classes

### `FontChoice`

The font used for new text and, if substituted, what replaced what.

Fields: `font`, `substituted`


### `Placement`

Where each wrapped line of new text goes.

Fields: `scale`, `size`, `lines`


### `Section`

Segments that reflow together: one column, one font size, ending at a barrier.

Fields: `page`, `members`, `limit`, `flow`


### `SectionLayout`

Result of laying out a section: placements of edited members, `dy` of moved ones.

Fields: `placements`, `moves`, `marker_moves`


### `PdfWriter`

Stages edits, fits them into sections, applies redactions, new text and moves.

Fields: `pdf`, `pending`, `moved`, `boxes`, `_fonts`, `_sections`, `_obstacles`, `_pristine`, `_old`, `_skipped`

- `def __post_init__(self) -> None` — Keeps a pristine copy of the PDF, the old texts and the skipped IDs.
- `def font_for(self, seg: PdfSegment) -> FontChoice` — Cached font choice per (page, font): embedded full font, else a fallback.
- `def _embedded(self, seg: PdfSegment) -> FontChoice | None` — Reuse the document's own font when it is embedded in full (not a subset).
- `def _fallback(seg: PdfSegment) -> FontChoice` — Built-in URW face chosen by name and flags (serif / sans / mono, bold, italic).
- `def _page_obstacles(self, page_no: int) -> list[pymupdf.Rect]` — Drawings and images of a page, minus a page-sized background fill.
- `def section(self, seg_id: str) -> Section` — The run of segments an edit of `seg_id` may reflow, and how low it may reach.
- `def _wrap(self, seg: PdfSegment, text: str, scale: float, first_baseline: float, last_allowed: float | None) -> Placement | None` — Wrap `text` from `first_baseline` down. None if a word is too wide or, when `last_allowed` is set, if a baseline would fall below it.
- `def _layout_section(self, sec: Section, texts: dict[str, str], scale: float) -> SectionLayout | None` — Place every member of `sec` top-down, keeping the original spacing between them.
- `def _section_scale(self, sec: Section, texts: dict[str, str]) -> float | None` — Largest scale in `_SCALES` at which the section layout fits, or None.
- `def fit(self, texts: dict[str, str]) -> dict[str, float | None]` — Scale per edited segment (1.0 = no shrink), or None for edits that cannot be placed even at MIN_SCALE. Edits in one section share a scale; when a section cannot hold all of them, the edit that grew most is dropped and the rest are fitted again.
- `def _pos(self, seg_id: str) -> tuple[int, float]` — (page, top) of a segment, to process sections top-down.
- `def measure(self, seg_id: str, text: str) -> float | None` — Scale at which `text` fits `seg_id` together with the edits already staged.
- `def stage(self, seg_id: str, text: str) -> float | None` — Queue `text` for `seg_id`; returns the scale used, or None if it does not fit.
- `def notes_for(self, seg_id: str) -> list[str]` — Report notes for a segment: font substitution, flattened style.
- `def _draw(self, page: pymupdf.Page, seg: PdfSegment, placement: Placement) -> None` — Sets a placement with `TextWriter`, honouring alignment and justification.
- `def _markers_of(self, seg: PdfSegment) -> list[pymupdf.Rect]` — List markers on the segment's lines, left of its text.
- `def _clip(self, seg: PdfSegment) -> pymupdf.Rect` — Clip rectangle of a segment for moving it: its lines plus list markers, column width.
- `def _show_moved(self, page: pymupdf.Page, clip: pymupdf.Rect, dy: float) -> None` — Redraw the original content inside `clip` shifted by `dy`, fonts and all.
- `def apply(self) -> None` — Write all staged edits; segments below an edit in its section move with it.
- `def save(self, path: Path) -> None` — Saves the edited PDF (garbage collection + deflate).

## Functions

- `def _norm_font(name: str) -> str` — Font name without subset prefix, spaces and dashes, lower-case.
- `def _x_overlap(a: pymupdf.Rect, b: pymupdf.Rect) -> bool` — True when two rectangles share more than half of the narrower width.

## Related

- [[pdf-reader]]
