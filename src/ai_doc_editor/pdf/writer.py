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

from ai_doc_editor.pdf.reader import PdfDocument, PdfSegment

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
class Section:
    """Segments that reflow together: one column, one font size, ending at a barrier."""

    page: int
    members: list[str]
    limit: float  # flow: lowest y content may reach; fixed: lowest baseline allowed
    flow: bool


@dataclass
class SectionLayout:
    placements: dict[str, Placement] = field(default_factory=dict)  # edited segments
    moves: dict[str, float] = field(default_factory=dict)  # unedited segments shifted by dy
    marker_moves: dict[str, float] = field(default_factory=dict)  # edited segments that moved


def _x_overlap(a: pymupdf.Rect, b: pymupdf.Rect) -> bool:
    overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
    return overlap > 0.5 * min(a.width, b.width)


@dataclass
class PdfWriter:
    pdf: PdfDocument
    pending: dict[str, str] = field(default_factory=dict)  # staged edits: id -> new text
    # What apply() did, for the structure check: moved clips (page, rect, dy) and the boxes
    # edited text was allowed to use.
    moved: list[tuple[int, pymupdf.Rect, float]] = field(default_factory=list)
    boxes: dict[str, pymupdf.Rect] = field(default_factory=dict)
    _fonts: dict[tuple[int, str], FontChoice] = field(default_factory=dict)
    _sections: dict[str, Section] = field(default_factory=dict)
    _obstacles: dict[int, list[pymupdf.Rect]] = field(default_factory=dict)
    _pristine: pymupdf.Document = field(init=False)
    _old: dict[str, str] = field(init=False)
    _skipped: set[str] = field(init=False)

    def __post_init__(self) -> None:
        # An untouched copy: the source of moved paragraphs and of the page's graphics.
        self._pristine = pymupdf.open("pdf", self.pdf.doc.tobytes())
        self._old = {x.id: x.text for x in self.pdf.segments}
        self._skipped = {x.id for x in self.pdf.segments if not x.editable}

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

    # -- sections ------------------------------------------------------------------------

    def _page_obstacles(self, page_no: int) -> list[pymupdf.Rect]:
        if page_no not in self._obstacles:
            page = self._pristine[page_no]
            rects = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()]
            rects += [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
            # A page-sized fill is the paper background (browsers draw one), not an obstacle.
            half = page.rect.get_area() / 2
            self._obstacles[page_no] = [r for r in rects if r.get_area() < half]
        return self._obstacles[page_no]

    def section(self, seg_id: str) -> Section:
        """The run of segments an edit of `seg_id` may reflow, and how low it may reach.

        Members: `seg_id` and the segments below it in the same column with the same font size,
        up to a barrier (a heading or other size, a drawing, an image, skipped text). Content may
        flow down to 2 pt above the barrier, or to the page's lowest text if there is none. A
        segment inside a box or a table cell, or crossed by graphics, does not flow: it keeps
        the fixed box of its own lines.
        """
        if seg_id in self._sections:
            return self._sections[seg_id]
        seg = self.pdf.layout[seg_id]
        on_page = [i for i, x in self.pdf.layout.items() if x.page == seg.page]
        col = seg.avail or seg.rect
        obstacles = [o for o in self._page_obstacles(seg.page) if _x_overlap(o, col)]
        enclosed = any(
            o.x0 <= seg.rect.x0 + 0.5
            and o.x1 >= seg.rect.x1 - 0.5
            and o.y0 <= seg.rect.y0 + 0.5
            and o.y1 >= seg.rect.y1 - 0.5
            and o.width > 2
            and o.height > 2
            for o in obstacles
        )
        if enclosed or any(o.intersects(seg.rect) for o in obstacles):
            sec = Section(seg.page, [seg_id], seg.lines[-1].spans[0]["origin"][1], False)
            self._sections[seg_id] = sec
            return sec
        below = sorted(
            (
                i
                for i in on_page
                if i != seg_id
                and self.pdf.layout[i].rect.y0 > seg.rect.y0 + 0.5
                and _x_overlap(self.pdf.layout[i].avail or self.pdf.layout[i].rect, col)
            ),
            key=lambda i: self.pdf.layout[i].rect.y0,
        )
        members, barrier = [seg_id], None
        for i in below:
            other = self.pdf.layout[i]
            prev = self.pdf.layout[members[-1]]
            hit = [o for o in obstacles if o.y0 < other.rect.y1 and o.y1 > prev.rect.y1 - 0.5]
            if hit:
                barrier = min(o.y0 for o in hit)
                break
            if abs(other.style.size - seg.style.size) > 0.6 or i in self._skipped:
                barrier = other.rect.y0
                break
            members.append(i)
        if barrier is None:
            last = self.pdf.layout[members[-1]]
            hit = [o for o in obstacles if o.y0 >= last.rect.y1 - 0.5]
            if hit:
                barrier = min(o.y0 for o in hit)
        if barrier is not None:
            # 2 pt clear of the barrier, but never stricter than the original layout.
            limit = max(barrier - 2, self.pdf.layout[members[-1]].rect.y1)
        else:
            limit = max(self.pdf.layout[i].rect.y1 for i in on_page)
        sec = Section(seg.page, members, limit, True)
        for i in members:
            self._sections[i] = sec  # a later, higher edit takes the lower ones into its section
        return sec

    # -- layout --------------------------------------------------------------------------

    def _wrap(
        self,
        seg: PdfSegment,
        text: str,
        scale: float,
        first_baseline: float,
        last_allowed: float | None,
    ) -> Placement | None:
        """Wrap `text` from `first_baseline` down. None if a word is too wide or, when
        `last_allowed` is set, if a baseline would fall below it."""
        font = self.font_for(seg).font
        size = seg.style.size * scale
        pitch = seg.line_pitch * scale
        box = seg.avail or seg.rect
        right = box.x1 + 0.5
        words = text.split()
        placed: list[tuple[float, float, float, list[str], bool]] = []
        i = 0
        while i < len(words):
            n = len(placed)
            baseline = first_baseline + n * pitch
            if last_allowed is not None and baseline > last_allowed + 0.01:
                return None
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

    def _layout_section(
        self, sec: Section, texts: dict[str, str], scale: float
    ) -> SectionLayout | None:
        """Place every member of `sec` top-down, keeping the original spacing between them."""
        out = SectionLayout()
        prev_orig_last = prev_new_last = 0.0
        bottom = 0.0
        for n, seg_id in enumerate(sec.members):
            seg = self.pdf.layout[seg_id]
            orig_first = seg.lines[0].spans[0]["origin"][1]
            orig_last = seg.lines[-1].spans[0]["origin"][1]
            start = orig_first if n == 0 else prev_new_last + (orig_first - prev_orig_last)
            dy = start - orig_first
            if seg_id in texts:
                placement = self._wrap(
                    seg, texts[seg_id], scale, start, None if sec.flow else sec.limit
                )
                if placement is None:
                    return None
                out.placements[seg_id] = placement
                new_last = placement.lines[-1][2] if placement.lines else start
                # Same descent below the last baseline as the original text had.
                bottom = new_last + (seg.rect.y1 - orig_last) * scale
                if abs(dy) > 0.01:
                    out.marker_moves[seg_id] = dy
            else:
                new_last = orig_last + dy
                bottom = seg.rect.y1 + dy
                if abs(dy) > 0.01:
                    out.moves[seg_id] = dy
            prev_orig_last, prev_new_last = orig_last, new_last
        if sec.flow and bottom > sec.limit + 0.5:
            return None
        return out

    def _section_scale(self, sec: Section, texts: dict[str, str]) -> float | None:
        return next(
            (sc for sc in _SCALES if self._layout_section(sec, texts, sc) is not None), None
        )

    def fit(self, texts: dict[str, str]) -> dict[str, float | None]:
        """Scale per edited segment (1.0 = no shrink), or None for edits that cannot be placed
        even at MIN_SCALE. Edits in one section share a scale; when a section cannot hold all
        of them, the edit that grew most is dropped and the rest are fitted again."""
        result: dict[str, float | None] = {}
        todo = dict(texts)
        while todo:
            groups: dict[int, tuple[Section, list[str]]] = {}
            for seg_id in sorted(todo, key=self._pos):
                sec = self.section(seg_id)
                groups.setdefault(id(sec), (sec, []))[1].append(seg_id)
            dropped = None
            scales: dict[str, float | None] = {}
            for sec, ids in groups.values():
                scale = self._section_scale(sec, {i: todo[i] for i in ids})
                if scale is None:
                    dropped = max(ids, key=lambda i: len(todo[i]) - len(self._old[i]))
                    break
                scales.update(dict.fromkeys(ids, scale))
            if dropped is None:
                result.update(scales)
                return result
            result[dropped] = None
            del todo[dropped]
        return result

    def _pos(self, seg_id: str) -> tuple[int, float]:
        seg = self.pdf.layout[seg_id]
        return (seg.page, seg.rect.y0)

    def measure(self, seg_id: str, text: str) -> float | None:
        """Scale at which `text` fits `seg_id` together with the edits already staged."""
        return self.fit({**self.pending, seg_id: text}).get(seg_id)

    def stage(self, seg_id: str, text: str) -> float | None:
        """Queue `text` for `seg_id`; returns the scale used, or None if it does not fit."""
        scale = self.measure(seg_id, text)
        if scale is not None:
            self.pending[seg_id] = text
        return scale

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

    def _markers_of(self, seg: PdfSegment) -> list[pymupdf.Rect]:
        """List markers on the segment's lines, left of its text."""
        out = []
        for m in self.pdf.markers.get(seg.page, []):
            cy = (m.y0 + m.y1) / 2
            if m.x1 <= seg.rect.x0 + 1 and any(ln.bbox[1] <= cy <= ln.bbox[3] for ln in seg.lines):
                out.append(m)
        return out

    def _clip(self, seg: PdfSegment) -> pymupdf.Rect:
        x0 = min([seg.rect.x0, *(m.x0 for m in self._markers_of(seg))])
        return pymupdf.Rect(
            x0 - 1, seg.rect.y0 - 0.5, (seg.avail or seg.rect).x1 + 1, seg.rect.y1 + 0.5
        )

    def _show_moved(self, page: pymupdf.Page, clip: pymupdf.Rect, dy: float) -> None:
        """Redraw the original content inside `clip` shifted by `dy`, fonts and all.

        The source is a copy of the original page from which all text and images outside the
        clip are removed, so no hidden copy of other text ends up in the file.
        """
        src = pymupdf.open()
        src.insert_pdf(self._pristine, from_page=page.number, to_page=page.number)
        sp = src[0]
        for block in sp.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    r = pymupdf.Rect(span["bbox"])
                    if not clip.contains((r.tl + r.br) / 2):
                        sp.add_redact_annot(r, fill=False, cross_out=False)
        others = [pymupdf.Rect(i["bbox"]) for i in sp.get_image_info()]
        others += [pymupdf.Rect(d["rect"]) for d in sp.get_drawings()]
        for r in others:
            if not r.intersects(clip):
                sp.add_redact_annot(r + (-0.5, -0.5, 0.5, 0.5), fill=False, cross_out=False)
        sp.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
        page.show_pdf_page(clip + (0, dy, 0, dy), src, 0, clip=clip)

    def apply(self) -> None:
        """Write all staged edits; segments below an edit in its section move with it."""
        self.moved.clear()
        self.boxes.clear()
        fits = self.fit(self.pending)
        texts = {i: t for i, t in self.pending.items() if fits.get(i) is not None}
        groups: dict[int, tuple[Section, dict[str, str]]] = {}
        for seg_id, text in sorted(texts.items(), key=lambda kv: self._pos(kv[0])):
            sec = self.section(seg_id)
            groups.setdefault(id(sec), (sec, {}))[1][seg_id] = text
        by_page: dict[int, list[tuple[Section, SectionLayout]]] = {}
        for sec, part in groups.values():
            lay = self._layout_section(sec, part, fits[next(iter(part))])
            by_page.setdefault(sec.page, []).append((sec, lay))
        for page_no, items in by_page.items():
            page = self.pdf.doc[page_no]
            moves: list[tuple[pymupdf.Rect, float]] = []
            for _sec, lay in items:
                for seg_id in [*lay.placements, *lay.moves]:
                    seg = self.pdf.layout[seg_id]
                    for line in seg.lines:
                        for span in line.spans:
                            r = pymupdf.Rect(span["bbox"])
                            inset = r.height * 0.2  # stay clear of the lines above and below
                            page.add_redact_annot(
                                pymupdf.Rect(r.x0, r.y0 + inset, r.x1, r.y1 - inset),
                                fill=False,
                                cross_out=False,
                            )
                    dy = lay.moves.get(seg_id, lay.marker_moves.get(seg_id, 0.0))
                    if seg_id in lay.moves:
                        moves.append((self._clip(seg), dy))
                    elif dy:
                        for m in self._markers_of(seg):
                            page.add_redact_annot(m, fill=False, cross_out=False)
                            moves.append((m + (-0.5, -0.5, 0.5, 0.5), dy))
                    if seg_id in lay.moves:
                        for m in self._markers_of(seg):
                            page.add_redact_annot(m, fill=False, cross_out=False)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            )
            for _sec, lay in items:
                for seg_id, placement in lay.placements.items():
                    seg = self.pdf.layout[seg_id]
                    self._draw(page, seg, placement)
                    box = seg.avail or seg.rect
                    # The area the new lines occupy: first line's ascent to last line's descent.
                    if placement.lines:
                        top = placement.lines[0][2] - placement.size
                        bottom = placement.lines[-1][2] + 0.35 * placement.size
                    else:
                        top, bottom = seg.rect.y0, seg.rect.y1
                    self.boxes[seg_id] = pymupdf.Rect(box.x0, top, box.x1, bottom)
            for clip, dy in moves:
                self._show_moved(page, clip, dy)
                self.moved.append((page_no, clip, dy))
        self.pending.clear()

    def save(self, path: Path) -> None:
        self.pdf.doc.save(str(path), garbage=3, deflate=True)
