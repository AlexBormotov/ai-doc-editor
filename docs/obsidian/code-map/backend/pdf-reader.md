---
title: src/ai_doc_editor/pdf/reader.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/pdf/reader.py`

Section: [[Backend]]

## Purpose

Split a digital PDF into paragraph-like segments (spec.md 4.3, DR-3).

## Classes

### `Style`

Dominant span style: font, size, colour, flags.

Fields: `font`, `size`, `color`, `flags`

- `def key(self) -> tuple[str, float]` — (font, rounded size): what must match for lines to share a segment.

### `Line`

One text line: bbox, text spans, list-marker spans, text, style.

Fields: `bbox`, `spans`, `marker`, `text`, `style`


### `PdfSegment`

Layout information the writer needs for one segment.

Fields: `page`, `lines`, `rect`, `style`, `align`, `line_pitch`, `mixed_style`, `avail`


### `PdfDocument`

Parsed PDF: PyMuPDF document, segments, layout per segment, list markers per page.

Fields: `path`, `doc`, `segments`, `layout`, `markers`


## Functions

- `def _dominant_style(spans: list[dict]) -> Style` — Style covering the most characters among spans.
- `def _split_marker(spans: list[dict]) -> tuple[list[dict], list[dict]]` — Separates a leading list-marker span from the line's text spans.
- `def _make_line(raw: dict) -> Line | None` — Builds a `Line` from a raw PyMuPDF line (None if empty).
- `def _is_marker_only(line: Line) -> bool` — True for a line that is just a list marker (bullet or number).
- `def _join(lines: list[Line]) -> str` — Joins line texts into segment text (no space after a trailing hyphen).
- `def _alignment(lines: list[Line], page_width: float) -> str` — Infers left / center / right / justify from line edges.
- `def _segment(page_no: int, lines: list[Line], page_width: float) -> PdfSegment` — Builds a `PdfSegment` (rect, dominant style, alignment, pitch) from lines.
- `def _free_space(page: pymupdf.Page, segs: list[PdfSegment], obstacles: list[pymupdf.Rect]) -> None` — Set `seg.avail`: the segment's rect widened left/right up to the nearest obstacle.
- `def _ends_paragraph(prev: Line, line: Line, current: list[Line]) -> bool` — True when the first word of `line` would have fitted at the end of `prev`.
- `def segment_lines(blocks: list[dict], page_no: int, page_width: float) -> tuple[list[tuple[PdfSegment, str | None]], list[pymupdf.Rect]]` — Group the text lines of a page into segments; returns segments and list-marker rects.
- `def _page_segments(page: pymupdf.Page, page_no: int) -> tuple[list[tuple[PdfSegment, str | None]], list[pymupdf.Rect]]` — Segments and list markers of one page, with free space computed.
- `def read_pdf(path: Path) -> PdfDocument` — Opens a PDF (rejects encrypted ones) and returns segments `pN/sK`, layout and markers.

## Related

- [[models]]
