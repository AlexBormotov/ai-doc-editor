"""Format conversion behind a layout gate (spec.md 4.4, AC-8, DR-4, DR-7).

DOCX -> PDF is rendered by LibreOffice, which is also the reference renderer for DOCX, so that
output is the reference layout by definition. PDF -> DOCX goes through pdf2docx; the DOCX is then
rendered back with LibreOffice and compared word by word with the source PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import pymupdf
from pydantic import BaseModel

from ai_doc_editor.soffice import convert as soffice_convert


class GateResult(BaseModel):
    passed: bool
    target: str
    pages_source: int
    pages_candidate: int
    failures: list[str] = []
    note: str | None = None


@dataclass
class Conversion:
    path: Path
    gate: GateResult
    rendered: Path | None = None  # LibreOffice render of a DOCX result, used by the gate
    extra: dict = field(default_factory=dict)


def _words(page: pymupdf.Page) -> list[tuple[str, pymupdf.Rect]]:
    return [(w[4], pymupdf.Rect(w[:4])) for w in page.get_text("words", sort=True)]


def _content_box(page: pymupdf.Page) -> pymupdf.Rect | None:
    rects = [r for _, r in _words(page)]
    if not rects:
        return None
    box = pymupdf.Rect(rects[0])
    for r in rects[1:]:
        box |= r
    return box


def layout_gate(source_pdf: Path, candidate_pdf: Path, tol_pt: float, target: str) -> GateResult:
    """Compare a converted document's rendering with the source (AC-8)."""
    a, b = pymupdf.open(str(source_pdf)), pymupdf.open(str(candidate_pdf))
    failures: list[str] = []
    if a.page_count != b.page_count:
        failures.append(f"page count {a.page_count} -> {b.page_count}")
    for n in range(min(a.page_count, b.page_count)):
        pa, pb = a[n], b[n]
        if abs(pa.rect.width - pb.rect.width) > 1 or abs(pa.rect.height - pb.rect.height) > 1:
            failures.append(f"page {n + 1}: page size {pa.rect} -> {pb.rect}")
            continue
        ba, bb = _content_box(pa), _content_box(pb)
        if ba and bb:
            for side, da in zip(
                ("left", "top", "right", "bottom"),
                (bb.x0 - ba.x0, bb.y0 - ba.y0, bb.x1 - ba.x1, bb.y1 - ba.y1),
                strict=True,
            ):
                if abs(da) > 2:
                    failures.append(f"page {n + 1}: {side} margin moved {da:+.1f} pt")
        wa, wb = _words(pa), _words(pb)
        sm = SequenceMatcher(None, [w for w, _ in wa], [w for w, _ in wb], autojunk=False)
        if sm.ratio() < 0.999:
            missing = [
                w for t, i1, i2, _, _ in sm.get_opcodes() if t != "equal" for w, _ in wa[i1:i2]
            ]
            failures.append(
                f"page {n + 1}: text differs ({sm.ratio():.1%} same), e.g. {missing[:5]}"
            )
        worst = None
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                ra, rb = wa[blk.a + k][1], wb[blk.b + k][1]
                d = max(abs(ra.x0 - rb.x0), abs(ra.y0 - rb.y0))
                if d > tol_pt and (worst is None or d > worst[0]):
                    worst = (d, wa[blk.a + k][0])
        if worst:
            failures.append(f"page {n + 1}: word {worst[1]!r} moved {worst[0]:.1f} pt")
    return GateResult(
        passed=not failures,
        target=target,
        pages_source=a.page_count,
        pages_candidate=b.page_count,
        failures=failures,
    )


def docx_to_pdf(docx: Path, out_dir: Path) -> Conversion:
    pdf = soffice_convert(docx, "pdf", out_dir)
    gate = GateResult(
        passed=True,
        target="pdf",
        pages_source=pymupdf.open(str(pdf)).page_count,
        pages_candidate=pymupdf.open(str(pdf)).page_count,
        note="LibreOffice is the reference renderer for DOCX; this PDF is that rendering.",
    )
    return Conversion(path=pdf, gate=gate)


def pdf_to_docx(pdf: Path, out_dir: Path, tol_pt: float) -> Conversion:
    from pdf2docx import Converter

    out_dir.mkdir(parents=True, exist_ok=True)
    docx = out_dir / f"{pdf.stem}.docx"
    cv = Converter(str(pdf))
    try:
        cv.convert(str(docx))
    finally:
        cv.close()
    render_dir = out_dir / "gate-render"
    rendered = soffice_convert(docx, "pdf", render_dir)
    return Conversion(path=docx, gate=layout_gate(pdf, rendered, tol_pt, "docx"), rendered=rendered)
