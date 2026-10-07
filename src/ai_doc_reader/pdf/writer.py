"""Rewrite edited PDF segments inside their original rectangles (spec.md 4.3, AC-4, AC-5).

Only segments with an edit are touched. Their text spans are removed with redactions that keep
images and vector graphics. The new text is wrapped to the segment's width and set on the
original baselines, in the segment's dominant style and alignment. Nothing is moved: if the text
needs more lines than the segment's height allows, the font is scaled down (to MIN_SCALE at most).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ai_doc_reader.pdf.reader import PdfDocument, PdfSegment

MIN_SCALE = 0.8  # AC-5: the font may shrink to no less than 80% of its original size
_SCALES = [round(1 - i * 0.02, 2) for i in range(int((1 - MIN_SCALE) / 0.02) + 1)]
_SUBSET = re.compile(r"^[A-Z]{6}\+")
_SANS = re.compile(r"sans|arial|helvetica|calibri|verdana|segoe|tahoma|gothic", re.I)
_SERIF = re.compile(r"serif|times|roman|cambria|georgia|garamond|book|charis", re.I)
_MONO = re.compile(r"mono|courier|consol", re.I)
# Built-in fallback faces (URW Nimbus, with Cyrillic): family -> (regular, bold, italic, both)
_FALLBACK = {
    "serif": ("tiro", "tibo", "tiit", "tibi"),
    "sans-serif": ("helv", "hebo", "heit", "hebi"),
    "monospace": ("cour", "cobo", "coit", "cobi"),
}


def _norm_font(name: str) -> str:
    return re.sub(r"[\s\-_,]", "", _SUBSET.sub("", name)).lower()


@dataclass
class FontChoice:
    font: pymupdf.Font
    substituted: str | None = None  # "Cambria -> serif" when the original could not be reused


@dataclass
class Placement:
    """Where each wrapped line of new text goes."""

    scale: float
    size: float
    lines: list[tuple[float, float, float, list[str], bool]]  # (x0, x1, baseline, words, last)


@dataclass
class PdfWriter:
    pdf: PdfDocument
    pending: dict[str, tuple[str, Placement]] = field(default_factory=dict)
    _fonts: dict[tuple[int, str], FontChoice] = field(default_factory=dict)

    # -- fonts ---------------------------------------------------------------------------

    def font_for(self, seg: PdfSegment) -> FontChoice:
        key = (seg.page, seg.style.font)
        if key not in self._fonts:
            self._fonts[key] = self._embedded(seg) or self._fallback(seg)
        return self._fonts[key]

    def _embedded(self, seg: PdfSegment) -> FontChoice | None:
        """Reuse the document's own font when it is embedded in full (not a subset)."""
        doc = self.pdf.doc
        wanted = _norm_font(seg.style.font)
        for xref, _ext, _type, basefont, _name, _enc in doc[seg.page].get_fonts():
            if _norm_font(basefont) != wanted or _SUBSET.match(basefont):
                continue
            _bname, fext, _ftype, buf = doc.extract_font(xref)
            if buf and fext not in ("n/a", ""):
                return FontChoice(pymupdf.Font(fontbuffer=buf))
        return None

    @staticmethod
    def _fallback(seg: PdfSegment) -> FontChoice:
        name, flags = seg.style.font, seg.style.flags
        if _MONO.search(name) or flags & 8:
            family = "monospace"
        elif _SANS.search(name):
            family = "sans-serif"
        elif _SERIF.search(name) or flags & 4:
            family = "serif"
        else:
            family = "sans-serif"
        bold = bool(flags & 16 or re.search(r"bold|black|heavy|semibold", name, re.I))
        italic = bool(flags & 2 or re.search(r"italic|oblique", name, re.I))
        code = _FALLBACK[family][(1 if bold else 0) + (2 if italic else 0)]
        return FontChoice(pymupdf.Font(code), f"{_SUBSET.sub('', name)} -> {family}")

    # -- layout --------------------------------------------------------------------------

    def _layout(self, seg: PdfSegment, text: str, scale: float) -> Placement | None:
        font = self.font_for(seg).font
        size = seg.style.size * scale
        pitch = seg.line_pitch * scale
        first_baseline = seg.lines[0].spans[0]["origin"][1]
        # New lines may use baselines down to the original last baseline, never below it.
        last_baseline = seg.lines[-1].spans[0]["origin"][1] + 0.01
        box = seg.avail or seg.rect
        right = box.x1 + 0.5
        words = text.split()
        placed: list[tuple[float, float, float, list[str], bool]] = []
        i = 0
        while i < len(words):
            n = len(placed)
            baseline = first_baseline + n * pitch
            if baseline > last_baseline:
                return None  # out of vertical room
            x0 = seg.lines[n].bbox[0] if n < len(seg.lines) else seg.rect.x0
            if seg.align in ("center", "right"):
                x0 = box.x0  # centred and right-aligned text may also grow leftwards
            width = right - x0
            line = [words[i]]
            if font.text_length(words[i], size) > width:
                return None  # one word wider than the box
            i += 1
            while i < len(words):
                trial = " ".join([*line, words[i]])
                if font.text_length(trial, size) > width:
                    break
                line.append(words[i])
                i += 1
            placed.append((x0, right, baseline, line, i >= len(words)))
        return Placement(scale, size, placed)

    def measure(self, seg_id: str, text: str) -> float | None:
        """Largest scale (1.0 = no shrink) at which `text` fits the segment, or None."""
        seg = self.pdf.layout[seg_id]
        for scale in _SCALES:
            if self._layout(seg, text, scale) is not None:
                return scale
        return None

    def stage(self, seg_id: str, text: str) -> float | None:
        """Queue `text` for `seg_id`; returns the scale used, or None if it does not fit."""
        seg = self.pdf.layout[seg_id]
        for scale in _SCALES:
            placement = self._layout(seg, text, scale)
            if placement is not None:
                self.pending[seg_id] = (text, placement)
                return scale
        return None

    def notes_for(self, seg_id: str) -> list[str]:
        seg = self.pdf.layout[seg_id]
        notes = []
        font = self.font_for(seg)
        if font.substituted:
            notes.append(f"font_substituted: {font.substituted}")
        if seg.mixed_style:
            notes.append("style_flattened")
        return notes

    # -- write ---------------------------------------------------------------------------

    def _draw(self, page: pymupdf.Page, seg: PdfSegment, placement: Placement) -> None:
        font = self.font_for(seg).font
        size = placement.size
        c = seg.style.color
        color = ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)
        tw = pymupdf.TextWriter(page.rect, color=color)
        space = font.text_length(" ", size)
        for x0, x1, baseline, words, last in placement.lines:
            line_text = " ".join(words)
            w = font.text_length(line_text, size)
            if seg.align == "justify" and not last and len(words) > 1:
                gap = space + (x1 - x0 - w) / (len(words) - 1)
                x = x0
                for word in words:
                    tw.append((x, baseline), word, font=font, fontsize=size)
                    x += font.text_length(word, size) + gap
                continue
            if seg.align == "right":
                x = x1 - w
            elif seg.align == "center":
                x = x0 + (x1 - x0 - w) / 2
            else:
                x = x0
            tw.append((x, baseline), line_text, font=font, fontsize=size)
        tw.write_text(page)

    def apply(self) -> None:
        by_page: dict[int, list[str]] = {}
        for seg_id in self.pending:
            by_page.setdefault(self.pdf.layout[seg_id].page, []).append(seg_id)
        for page_no, ids in by_page.items():
            page = self.pdf.doc[page_no]
            for seg_id in ids:
                for line in self.pdf.layout[seg_id].lines:
                    for span in line.spans:
                        r = pymupdf.Rect(span["bbox"])
                        inset = r.height * 0.2  # stay clear of the lines above and below
                        page.add_redact_annot(
                            pymupdf.Rect(r.x0, r.y0 + inset, r.x1, r.y1 - inset),
                            fill=False,
                            cross_out=False,
                        )
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            )
            for seg_id in ids:
                _text, placement = self.pending[seg_id]
                self._draw(page, self.pdf.layout[seg_id], placement)
        self.pending.clear()

    def save(self, path: Path) -> None:
        self.pdf.doc.save(str(path), garbage=3, deflate=True)
