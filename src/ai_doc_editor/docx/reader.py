"""Split a DOCX into paragraph segments (spec.md 4.2).

Every `w:p` in the main document, headers and footers is a candidate, including paragraphs in
tables and text boxes. A segment's text is the concatenation of its own runs (not those of
paragraphs nested inside it, e.g. a text box anchored in it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as open_docx
from docx.opc.constants import CONTENT_TYPE as CT
from lxml import etree

from ai_doc_editor.models import Segment

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "mc": MC, "m": M}

_STORY_TYPES = {CT.WML_DOCUMENT_MAIN, CT.WML_HEADER, CT.WML_FOOTER}

# Paragraph content we do not edit: fields, notes, equations, existing revisions.
# Compiled XPath: python-docx overrides `element.xpath()` and rejects `namespaces=`.
_SKIP_XPATHS = {
    reason: etree.XPath(xp, namespaces=NS)
    for reason, xp in {
        "field": ".//w:fldChar | .//w:fldSimple | .//w:instrText",
        "note_reference": ".//w:footnoteReference | .//w:endnoteReference",
        "equation": ".//m:oMath | .//m:oMathPara",
        "existing_revision": ".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo",
    }.items()
}
_IN_FALLBACK = etree.XPath("ancestor::mc:Fallback", namespaces=NS)


def q(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def own_runs(p: etree._Element) -> list[etree._Element]:
    """Runs whose nearest enclosing paragraph is `p`, in document order."""
    return [r for r in p.iter(q("w:r")) if _nearest_paragraph(r) is p]


def _nearest_paragraph(el: etree._Element) -> etree._Element | None:
    parent = el.getparent()
    while parent is not None and parent.tag != q("w:p"):
        parent = parent.getparent()
    return parent


def run_text(r: etree._Element) -> str:
    out = []
    for child in r:
        if child.tag == q("w:t"):
            out.append(child.text or "")
        elif child.tag == q("w:tab"):
            out.append("\t")
        elif child.tag in (q("w:br"), q("w:cr")):
            out.append("\n")
        elif child.tag == q("w:noBreakHyphen"):
            out.append("‑")
    return "".join(out)


def paragraph_text(p: etree._Element) -> str:
    return "".join(run_text(r) for r in own_runs(p))


def _skip_reason(p: etree._Element) -> str | None:
    if _IN_FALLBACK(p):
        return "fallback_copy"
    for reason, xp in _SKIP_XPATHS.items():
        hits = [el for el in xp(p) if _nearest_paragraph(el) is p]
        if hits:
            return reason
    return None


@dataclass
class DocxDocument:
    """A parsed DOCX: the python-docx object plus a map from segment ID to `w:p` element."""

    path: Path
    doc: object
    segments: list[Segment] = field(default_factory=list)
    paragraphs: dict[str, etree._Element] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        self.doc.save(path)


def _story_parts(doc) -> list[tuple[str, etree._Element]]:
    parts = []
    for part in doc.part.package.iter_parts():
        if part.content_type in _STORY_TYPES:
            name = Path(str(part.partname)).stem  # document, header1, footer2, ...
            parts.append((name, part.element))
    # Main document first, then headers and footers by name, for a stable order.
    parts.sort(key=lambda x: (x[0] != "document", x[0]))
    return parts


def read_docx(path: Path) -> DocxDocument:
    doc = open_docx(str(path))
    result = DocxDocument(path=path, doc=doc)
    for part_name, root in _story_parts(doc):
        for i, p in enumerate(root.iter(q("w:p"))):
            text = paragraph_text(p)
            if not text.strip():
                continue
            seg_id = f"{part_name}/p/{i}"
            result.segments.append(Segment(id=seg_id, text=text, skip_reason=_skip_reason(p)))
            result.paragraphs[seg_id] = p
    return result
