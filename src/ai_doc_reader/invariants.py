"""Structure invariants: the oracle that decides whether an edit preserved the layout.

Each check returns a list of violations (empty means the invariant holds). Used by the tests,
by `evals/run_invariants.py`, and by the editor to stamp a "structure verified" result on a run.
"""

from __future__ import annotations

import zipfile
from difflib import SequenceMatcher
from pathlib import Path

from lxml import etree

from ai_doc_reader.docx.reader import NS, _story_parts, own_runs, paragraph_text, q, run_text

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
                    if _c14n(etree.fromstring(da)) == _c14n(etree.fromstring(db)):
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
            sm = SequenceMatcher(None, [c for c, _ in fa], [c for c, _ in fb], autojunk=False)
            for blk in sm.get_matching_blocks():
                for k in range(blk.size):
                    if fa[blk.a + k][1] != fb[blk.b + k][1]:
                        errors.append(f"{seg_id}: formatting of unchanged text changed")
                        break
                else:
                    continue
                break
    return errors
