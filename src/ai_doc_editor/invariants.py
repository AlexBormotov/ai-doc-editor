"""Structure invariants: the oracle that decides whether an edit preserved the layout.

Each check returns a list of violations (empty means the invariant holds). Used by the tests,
by `evals/run_invariants.py`, and by the editor to stamp a "structure verified" result on a run.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from ai_doc_editor.docx.reader import NS, _story_parts, own_runs, paragraph_text, q, run_text

_ALL_P = etree.XPath(".//w:p", namespaces=NS)
_ALL_TBL = etree.XPath(".//w:tbl", namespaces=NS)
_ALL_SECT = etree.XPath(".//w:sectPr", namespaces=NS)


def _c14n(el: etree._Element | None) -> bytes:
    return b"" if el is None else etree.tostring(el, method="c14n")


def _in_ins(run: etree._Element, p: etree._Element) -> bool:
    parent = run.getparent()
    while parent is not None and parent is not p:
        if parent.tag == q("w:ins"):
            return True
        parent = parent.getparent()
    return False


def rejected_text(p: etree._Element) -> str:
    """Paragraph text with every tracked change rejected (insertions dropped, deletions kept)."""
    out = []
    for run in own_runs(p):
        if _in_ins(run, p):
            continue
        for child in run:
            if child.tag in (q("w:t"), q("w:delText")):
                out.append(child.text or "")
            elif child.tag == q("w:tab"):
                out.append("\t")
            elif child.tag in (q("w:br"), q("w:cr")):
                out.append("\n")
    return "".join(out)


def unchanged_regions(old: str, new: str) -> list[tuple[int, int, int]]:
    """(old_start, new_start, length) of the text a word-level edit leaves untouched."""
    from ai_doc_editor.docx.writer import diff_ops

    regions, a, b = [], 0, 0
    for i1, i2, repl in diff_ops(old, new):
        if i1 > a:
            regions.append((a, b, i1 - a))
        b += (i1 - a) + len(repl)
        a = i2
    if len(old) > a:
        regions.append((a, b, len(old) - a))
    return regions


def char_formats(p: etree._Element) -> list[tuple[str, bytes]]:
    """(character, canonical rPr) for each visible character of the paragraph."""
    out = []
    for run in own_runs(p):
        fmt = _c14n(run.find(q("w:rPr")))
        out.extend((ch, fmt) for ch in run_text(run))
    return out


def _table_shape(tbl: etree._Element) -> list[list[tuple[str, str]]]:
    shape = []
    for tr in tbl.findall(q("w:tr")):
        row = []
        for tc in tr.findall(q("w:tc")):
            tcpr = tc.find(q("w:tcPr"))
            span = tcpr.find(q("w:gridSpan")) if tcpr is not None else None
            vmerge = tcpr.find(q("w:vMerge")) if tcpr is not None else None
            row.append(
                (
                    span.get(q("w:val"), "1") if span is not None else "1",
                    vmerge.get(q("w:val"), "continue") if vmerge is not None else "",
                )
            )
        shape.append(row)
    return shape


def _entries(root: etree._Element, names: set[str]) -> list[tuple]:
    """What a package index means, independent of how it is written.

    `[Content_Types].xml`: the effective content type of every part (an Override wins over the
    extension Default; unused Defaults and redundant Overrides do not matter).
    `.rels`: the relationships as a sorted set.
    """
    if root.tag.endswith("}Types"):
        defaults = {
            c.get("Extension", "").lower(): c.get("ContentType")
            for c in root
            if c.tag.endswith("Default")
        }
        overrides = {
            c.get("PartName"): c.get("ContentType") for c in root if c.tag.endswith("Override")
        }
        return sorted(
            (n, overrides.get(f"/{n}") or defaults.get(n.rsplit(".", 1)[-1].lower()))
            for n in names
            if not n.endswith("/")
        )
    return sorted((child.tag, tuple(sorted(child.attrib.items()))) for child in root)


def _non_story_parts_equal(a: Path, b: Path, story_names: set[str]) -> list[str]:
    errors = []
    with zipfile.ZipFile(a) as za, zipfile.ZipFile(b) as zb:
        names_a, names_b = set(za.namelist()), set(zb.namelist())
        if names_a != names_b:
            errors.append(f"package parts differ: {sorted(names_a ^ names_b)}")
        for name in sorted(names_a & names_b):
            if Path(name).stem in story_names and name.startswith("word/"):
                continue
            da, db = za.read(name), zb.read(name)
            if da == db:
                continue
            if name.endswith((".xml", ".rels")):
                try:
                    xa, xb = etree.fromstring(da), etree.fromstring(db)
                    if _c14n(xa) == _c14n(xb):
                        continue
                    # Package indexes: entry order carries no meaning, compare as sets.
                    is_index = name.endswith((".rels", "[Content_Types].xml"))
                    if is_index and _entries(xa, names_a) == _entries(xb, names_b):
                        continue
                except etree.XMLSyntaxError:
                    pass
            errors.append(f"part changed: {name}")
    return errors


def check_docx(
    original: Path,
    edited: Path,
    expected: dict[str, str],
    tracked: bool,
) -> list[str]:
    """Violations of AC-1 (and AC-2 when `tracked`) between `original` and `edited`.

    `expected` maps the segment IDs that were edited to their new text.
    """
    from docx import Document

    errors: list[str] = []
    parts_a = dict(_story_parts(Document(str(original))))
    parts_b = dict(_story_parts(Document(str(edited))))
    if parts_a.keys() != parts_b.keys():
        return [f"story parts differ: {sorted(parts_a)} vs {sorted(parts_b)}"]
    errors += _non_story_parts_equal(original, edited, set(parts_a))

    for name, root_a in parts_a.items():
        root_b = parts_b[name]
        ps_a, ps_b = _ALL_P(root_a), _ALL_P(root_b)
        if len(ps_a) != len(ps_b):
            errors.append(f"{name}: paragraph count {len(ps_a)} -> {len(ps_b)}")
            continue
        tbls_a, tbls_b = _ALL_TBL(root_a), _ALL_TBL(root_b)
        if [_table_shape(t) for t in tbls_a] != [_table_shape(t) for t in tbls_b]:
            errors.append(f"{name}: table count or shape changed")
        if [_c14n(s) for s in _ALL_SECT(root_a)] != [_c14n(s) for s in _ALL_SECT(root_b)]:
            errors.append(f"{name}: section properties changed")

        edited_ps = {i for i in range(len(ps_a)) if f"{name}/p/{i}" in expected}
        # A paragraph that contains an edited paragraph (text box host) changes too.
        hosts = {i for i, p in enumerate(ps_a) for j in edited_ps if j != i and ps_a[j] in p.iter()}
        for i, (pa, pb) in enumerate(zip(ps_a, ps_b, strict=True)):
            seg_id = f"{name}/p/{i}"
            if _c14n(pa.find(q("w:pPr"))) != _c14n(pb.find(q("w:pPr"))):
                errors.append(f"{seg_id}: paragraph properties changed")
            if i in hosts:
                # Only the nested text box changed: the host's own text and formats must not.
                if char_formats(pa) != char_formats(pb):
                    errors.append(f"{seg_id}: text box host paragraph changed")
                continue
            if i not in edited_ps:
                if _c14n(pa) != _c14n(pb):
                    errors.append(f"{seg_id}: unedited paragraph changed")
                continue
            old = paragraph_text(pa)
            got = paragraph_text(pb)
            if got != expected[seg_id]:
                errors.append(f"{seg_id}: text {got!r} != expected {expected[seg_id]!r}")
            if tracked and rejected_text(pb) != old:
                errors.append(f"{seg_id}: rejecting all changes does not restore the original")
            if not tracked and (pb.find(f".//{q('w:ins')}") is not None):
                errors.append(f"{seg_id}: tracked change present with tracking off")
            fa, fb = char_formats(pa), char_formats(pb)
            # New text may only reuse formats already in the paragraph (no hidden, recoloured
            # or otherwise new formatting introduced by an edit).
            if {f for _, f in fb} - {f for _, f in fa}:
                errors.append(f"{seg_id}: edit introduced formatting not in the original")
            # "Unchanged text" is what the word-level diff of spec.md 4.2 leaves equal; a
            # character diff would pair stray matches (quotes, commas) across rewritten runs.
            for a0, b0, n in unchanged_regions(old, got):
                if [x[1] for x in fa[a0 : a0 + n]] != [x[1] for x in fb[b0 : b0 + n]]:
                    errors.append(f"{seg_id}: formatting of unchanged text changed")
                    break
    return errors


# -- PDF --------------------------------------------------------------------------------------


def _spans(page) -> list[dict]:
    import pymupdf

    out = []
    for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    out.append(span)
    return out


def _core(bbox):
    """A span's box without the top and bottom 20%: line boxes of adjacent lines touch."""
    import pymupdf

    r = pymupdf.Rect(bbox)
    inset = r.height * 0.2
    return pymupdf.Rect(r.x0, r.y0 + inset, r.x1, r.y1 - inset)


def _close(a, b, tol: float) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def check_pdf(
    original: Path,
    edited: Path,
    expected: dict[str, str],
    moved: list[tuple[int, Any, float]] | None = None,
    boxes: dict[str, Any] | None = None,
) -> list[str]:
    """Violations of AC-4 between `original` and `edited`.

    `expected` maps edited segment IDs (as produced by `read_pdf(original)`) to their new text.
    `moved` lists the regions the writer shifted vertically inside a section, as
    (page, rect, dy); `boxes` the area each edited segment's text was allowed to use (by default
    its own widened rectangle). Untouched text must keep its text and position (0.5 pt), or sit
    exactly `dy` lower if it lies in a moved region. Moved text must not overlap text that did
    not move. New text must lie inside its box and must not overlap any other text. Images and
    vector graphics must be unchanged. Page count and sizes must be unchanged.
    """
    import pymupdf

    from ai_doc_editor.pdf.reader import read_pdf
    from ai_doc_editor.pdf.writer import MIN_SCALE

    errors: list[str] = []
    src = read_pdf(original)
    a, b = src.doc, pymupdf.open(str(edited))
    if a.page_count != b.page_count:
        return [f"page count {a.page_count} -> {b.page_count}"]
    for n, (pa, pb) in enumerate(zip(a, b, strict=True)):
        if not _close(pa.rect, pb.rect, 0.01):
            errors.append(f"page {n}: size changed")
        imgs_a = sorted(tuple(round(x, 1) for x in i["bbox"]) for i in pa.get_image_info())
        imgs_b = sorted(tuple(round(x, 1) for x in i["bbox"]) for i in pb.get_image_info())
        if imgs_a != imgs_b:
            errors.append(f"page {n}: images changed")
        draw_a = sorted(tuple(round(x, 1) for x in d["rect"]) for d in pa.get_drawings())
        draw_b = sorted(tuple(round(x, 1) for x in d["rect"]) for d in pb.get_drawings())
        if draw_a != draw_b:
            errors.append(f"page {n}: vector graphics changed")

        edited_here = {sid: src.layout[sid] for sid in expected if src.layout[sid].page == n}
        removed = {
            (s["text"], tuple(round(x, 1) for x in s["bbox"]))
            for seg in edited_here.values()
            for line in seg.lines
            for s in line.spans
        }
        kept = [
            s
            for s in _spans(pa)
            if (s["text"], tuple(round(x, 1) for x in s["bbox"])) not in removed
        ]
        shifts = [(pymupdf.Rect(r), dy) for p, r, dy in (moved or []) if p == n]

        def target(span: dict, shifts=shifts) -> tuple[pymupdf.Rect, float]:
            r = pymupdf.Rect(span["bbox"])
            centre = (r.tl + r.br) / 2
            dy = next((d for clip, d in shifts if clip.contains(centre)), 0.0)
            return r + (0, dy, 0, dy), dy

        expected_at = [target(s) for s in kept]
        new_spans = _spans(pb)
        matched: set[int] = set()
        for s, (want_box, _dy) in zip(kept, expected_at, strict=True):
            hit = next(
                (
                    i
                    for i, t in enumerate(new_spans)
                    if i not in matched
                    and t["text"] == s["text"]
                    and _close(t["bbox"], want_box, 0.5)
                ),
                None,
            )
            if hit is None:
                errors.append(f"page {n}: untouched text moved or lost: {s['text'][:40]!r}")
            else:
                matched.add(hit)
        kept_rects = [_core(box) for box, _dy in expected_at]
        # Shapes and images that touched no text originally (not backgrounds or cell borders
        # under text, not hairlines such as underlines): new text must stay off them.
        text_boxes = [pymupdf.Rect(sp["bbox"]) for sp in _spans(pa)]
        graphics = [
            r
            for r in [pymupdf.Rect(d["rect"]) for d in pa.get_drawings()]
            + [pymupdf.Rect(i["bbox"]) for i in pa.get_image_info()]
            if min(r.width, r.height) > 3 and not any(r.intersects(t) for t in text_boxes)
        ]
        still = [_core(box) for box, dy in expected_at if not dy]
        for box, dy in expected_at:
            if dy and any((_core(box) & k).get_area() > 1.0 for k in still if k.intersects(box)):
                errors.append(f"page {n}: moved text overlaps text that did not move")
                break
        placed: dict[str, list[dict]] = {sid: [] for sid in edited_here}
        for i, t in enumerate(new_spans):
            if i in matched:
                continue
            r = pymupdf.Rect(t["bbox"])
            owner = None
            for sid, seg in edited_here.items():
                box = pymupdf.Rect((boxes or {}).get(sid) or seg.avail or seg.rect)
                vtol = 0.35 * seg.style.size
                if (
                    r.x0 >= box.x0 - 1
                    and r.x1 <= box.x1 + 1
                    and r.y0 >= box.y0 - vtol
                    and r.y1 <= box.y1 + vtol
                ):
                    owner = sid
                    break
            if owner is None:
                errors.append(f"page {n}: new text outside its segment: {t['text'][:40]!r}")
                continue
            placed[owner].append(t)
            # New text keeps the segment's colour and may shrink only down to MIN_SCALE, so an
            # edit cannot hide content (white or microscopic text).
            seg = edited_here[owner]
            if t["color"] != seg.style.color:
                errors.append(f"{owner}: new text colour {t['color']:06x} != original")
            if t["size"] < seg.style.size * MIN_SCALE - 0.05:
                errors.append(f"{owner}: new text size {t['size']:.1f} below the shrink limit")
            for k in kept_rects + graphics:
                inter = _core(t["bbox"]) & k
                if not inter.is_empty and inter.get_area() > 1.0:
                    errors.append(f"page {n}: new text overlaps other content: {t['text'][:40]!r}")
                    break
        for sid, spans in placed.items():
            spans.sort(key=lambda s: (round(s["origin"][1], 1), s["origin"][0]))
            got = " ".join(" ".join(s["text"] for s in spans).split())
            want = " ".join(expected[sid].split())
            if got != want:
                errors.append(f"{sid}: text {got!r} != expected {want!r}")
    return errors
