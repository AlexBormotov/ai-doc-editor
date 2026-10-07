"""Split a digital PDF into paragraph-like segments (spec.md 4.3, DR-3).

PyMuPDF's own blocks often merge a heading with the paragraph under it, or all items of a list,
so segments are rebuilt from lines: a new segment starts at a list marker, at a change of the
dominant font or size, or at a vertical gap larger than half a line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ai_doc_reader.models import Segment

_MARKER = re.compile(r"^(?:[•▪◦–—\-\*]|\d{1,3}[.)]|[a-zA-Z][.)])$")
_SYMBOL_FONTS = re.compile(r"symbol|wingding|dingbat", re.I)


@dataclass
class Style:
    font: str
    size: float
    color: int
    flags: int

    @property
    def key(self) -> tuple[str, float]:
        return (self.font, round(self.size, 1))


@dataclass
class Line:
    bbox: tuple[float, float, float, float]
    spans: list[dict]  # text spans after the marker
    marker: list[dict]  # list marker spans, kept untouched
    text: str
    style: Style


@dataclass
class PdfSegment:
    """Layout information the writer needs for one segment."""

    page: int
    lines: list[Line]
    rect: pymupdf.Rect
    style: Style
    align: str  # left | center | right | justify
    line_pitch: float
    mixed_style: bool
    # The rectangle the new text may use: `rect` widened horizontally into free space only.
    avail: pymupdf.Rect | None = None


@dataclass
class PdfDocument:
    path: Path
    doc: pymupdf.Document
    segments: list[Segment] = field(default_factory=list)
    layout: dict[str, PdfSegment] = field(default_factory=dict)


def _dominant_style(spans: list[dict]) -> Style:
    weights: dict[tuple, int] = {}
    for s in spans:
        k = (s["font"], round(s["size"], 2), s["color"], s["flags"])
        weights[k] = weights.get(k, 0) + len(s["text"].strip())
    font, size, color, flags = max(weights, key=weights.get)
    return Style(font, size, color, flags)


def _split_marker(spans: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(spans) < 2:
        return [], spans
    first = spans[0]
    text = first["text"].strip()
    is_marker = bool(_MARKER.match(text)) or (
        _SYMBOL_FONTS.search(first["font"]) is not None and len(text) == 1
    )
    if is_marker and spans[1]["bbox"][0] > first["bbox"][2] + 1:
        return [first], spans[1:]
    return [], spans


def _make_line(raw: dict) -> Line | None:
    spans = [s for s in raw["spans"] if s["text"]]
    if not spans or not "".join(s["text"] for s in spans).strip():
        return None
    marker, body = _split_marker(spans)
    text = "".join(s["text"] for s in body).strip()
    x0 = min(s["bbox"][0] for s in body)
    x1 = max(s["bbox"][2] for s in body)
    y0 = min(s["bbox"][1] for s in body)
    y1 = max(s["bbox"][3] for s in body)
    return Line((x0, y0, x1, y1), body, marker, text, _dominant_style(body))


def _is_marker_only(line: Line) -> bool:
    text = line.text.strip()
    return bool(_MARKER.match(text)) or (
        _SYMBOL_FONTS.search(line.style.font) is not None and len(text) <= 1
    )


def _join(lines: list[Line]) -> str:
    out = lines[0].text
    for line in lines[1:]:
        out += line.text if out.endswith("-") and not out.endswith(" -") else " " + line.text
    return out


def _alignment(lines: list[Line], page_width: float) -> str:
    x0s = [ln.bbox[0] for ln in lines]
    x1s = [ln.bbox[2] for ln in lines]
    if len(lines) == 1:
        center = (x0s[0] + x1s[0]) / 2
        return "center" if abs(center - page_width / 2) < 3 and x0s[0] > 100 else "left"
    body = lines[:-1]
    same_left = max(x0s) - min(x0s) < 2
    same_right = max(x1s) - min(x1s) < 2
    if same_left and max(ln.bbox[2] for ln in body) - min(ln.bbox[2] for ln in body) < 2:
        # One full line proves nothing (ragged text wraps too); two equal right edges do.
        return "justify" if len(body) >= 2 else "left"
    if same_left:
        return "left"
    if same_right:
        return "right"
    centers = [(a + b) / 2 for a, b in zip(x0s, x1s, strict=True)]
    if max(centers) - min(centers) < 2:
        return "center"
    return "left"


def _segment(page_no: int, lines: list[Line], page_width: float) -> PdfSegment:
    rect = pymupdf.Rect(
        min(ln.bbox[0] for ln in lines),
        lines[0].bbox[1],
        max(ln.bbox[2] for ln in lines),
        lines[-1].bbox[3],
    )
    if len(lines) > 1:
        pitch = (lines[-1].bbox[1] - lines[0].bbox[1]) / (len(lines) - 1)
    else:
        pitch = lines[0].bbox[3] - lines[0].bbox[1]
    spans = [s for ln in lines for s in ln.spans if s["text"].strip()]
    styles = {(s["font"], round(s["size"], 1), s["color"]) for s in spans}
    return PdfSegment(
        page=page_no,
        lines=lines,
        rect=rect,
        style=_dominant_style(spans),
        align=_alignment(lines, page_width),
        line_pitch=pitch,
        mixed_style=len(styles) > 1,
    )


def _free_space(page: pymupdf.Page, segs: list[PdfSegment], obstacles: list[pymupdf.Rect]) -> None:
    """Set `seg.avail`: the segment's rect widened left/right up to the nearest obstacle.

    Obstacles are other text, list markers, images and vector graphics on the same lines. A
    drawing that encloses the segment (a table cell, a shaded box) limits it at its own edges.
    The page's text area (the union of all text) is the outer limit. Never widened vertically.
    """
    if not segs:
        return
    text_left = min(s.rect.x0 for s in segs)
    text_right = max(s.rect.x1 for s in segs)
    pad = 2.0
    drawings = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()]
    images = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    for seg in segs:
        r = seg.rect
        left, right = text_left, text_right
        band = [
            o
            for o in obstacles + images + [x.rect for x in segs if x is not seg]
            if o.y1 > r.y0 + 1 and o.y0 < r.y1 - 1
        ]
        for d in drawings:
            if not (d.y1 > r.y0 + 1 and d.y0 < r.y1 - 1):
                continue
            if d.x0 <= r.x0 + 0.5 and d.x1 >= r.x1 - 0.5 and d.width > 2:
                left, right = max(left, d.x0 + pad), min(right, d.x1 - pad)  # enclosing box
            else:
                band.append(d)
        for o in band:
            if o.x0 >= r.x1 - 0.5:
                right = min(right, o.x0 - pad)
            elif o.x1 <= r.x0 + 0.5:
                left = max(left, o.x1 + pad)
        left, right = min(left, r.x0), max(right, r.x1)
        if seg.align == "center":
            grow = min(r.x0 - left, right - r.x1)
            seg.avail = pymupdf.Rect(r.x0 - grow, r.y0, r.x1 + grow, r.y1)
        elif seg.align == "right":
            seg.avail = pymupdf.Rect(left, r.y0, r.x1, r.y1)
        else:
            seg.avail = pymupdf.Rect(r.x0, r.y0, right, r.y1)


def _page_segments(page: pymupdf.Page, page_no: int) -> list[tuple[PdfSegment, str | None]]:
    out: list[tuple[PdfSegment, str | None]] = []
    markers: list[pymupdf.Rect] = []
    data = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)
    for block in data["blocks"]:
        if block.get("type") != 0:
            continue
        current: list[Line] = []
        current_skip: str | None = None
        after_marker = False
        for raw in block["lines"]:
            line = _make_line(raw)
            if line is None:
                continue
            if _is_marker_only(line):
                # A list marker extracted as its own line: never edited, starts a new item.
                markers.append(pymupdf.Rect(line.bbox))
                after_marker = True
                continue
            markers.extend(pymupdf.Rect(m["bbox"]) for m in line.marker)
            skip = None if tuple(raw["dir"]) == (1.0, 0.0) else "rotated_text"
            if current:
                prev = current[-1]
                gap = line.bbox[1] - prev.bbox[3]
                height = prev.bbox[3] - prev.bbox[1]
                side_by_side = line.bbox[1] < prev.bbox[3] - 0.5 * height  # next column/cell
                # Line 2 may sit left of line 1 (first-line indent); otherwise left edges match.
                x_jump = abs(line.bbox[0] - prev.bbox[0]) > 3 and not (
                    len(current) == 1 and 0 < prev.bbox[0] - line.bbox[0] <= 50
                )
                if (
                    after_marker
                    or line.marker
                    or line.style.key != current[0].style.key
                    or gap > 0.5 * height
                    or side_by_side
                    or x_jump
                    or skip != current_skip
                ):
                    out.append((_segment(page_no, current, page.rect.width), current_skip))
                    current = []
            if not current:
                current_skip = skip
            current.append(line)
            after_marker = False
        if current:
            out.append((_segment(page_no, current, page.rect.width), current_skip))
    _free_space(page, [seg for seg, _ in out], markers)
    return out


def read_pdf(path: Path) -> PdfDocument:
    doc = pymupdf.open(str(path))
    if doc.needs_pass or doc.is_encrypted:
        raise ValueError("encrypted PDFs are not supported")
    result = PdfDocument(path=path, doc=doc)
    for page_no, page in enumerate(doc):
        for k, (seg, skip) in enumerate(_page_segments(page, page_no)):
            seg_id = f"p{page_no}/s{k}"
            result.layout[seg_id] = seg
            result.segments.append(
                Segment(
                    id=seg_id,
                    text=_join(seg.lines),
                    page=page_no,
                    bbox=tuple(seg.rect),
                    skip_reason=skip,
                )
            )
    return result
