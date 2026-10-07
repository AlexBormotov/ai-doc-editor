"""Apply edits to DOCX paragraphs in place (spec.md 4.2, DR-2).

A token-level diff between the old and new paragraph text decides which characters change.
Unchanged characters stay in their original runs with their original `w:rPr`. Replaced or
inserted text becomes a new run that copies the formatting of the text it replaces (or of its
neighbour, for a pure insertion). With tracking on, removals become `w:del` and additions `w:ins`.
Nothing outside the edited paragraph's runs is touched.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from lxml import etree

from ai_doc_editor.docx.reader import DocxDocument, own_runs, paragraph_text, q
from ai_doc_editor.docx.redline import Redline
from ai_doc_editor.models import Change, ChangeStatus, Edit

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_TEXT_TAGS = {"w:t", "w:tab", "w:br", "w:cr", "w:noBreakHyphen"}
_TOKEN = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


@dataclass
class _Atom:
    """A run holding exactly one content child, with its character span in the paragraph."""

    run: etree._Element
    start: int
    end: int

    @property
    def is_text(self) -> bool:
        return self.end > self.start


def _content_len(child: etree._Element) -> int:
    if child.tag == q("w:t"):
        return len(child.text or "")
    if child.tag in {q(t) for t in _TEXT_TAGS}:
        return 1
    return 0


def _split_run_children(run: etree._Element) -> list[etree._Element]:
    """Split a run into runs that each hold one content child; returns the new runs in order."""
    rpr = run.find(q("w:rPr"))
    children = [c for c in run if c.tag != q("w:rPr")]
    if len(children) <= 1:
        return [run]
    pieces = []
    for child in children:
        piece = etree.Element(q("w:r"))
        if rpr is not None:
            piece.append(copy.deepcopy(rpr))
        piece.append(child)  # moves the child out of the original run
        pieces.append(piece)
    for piece in pieces:
        run.addprevious(piece)
    run.getparent().remove(run)
    return pieces


def _atoms(p: etree._Element) -> list[_Atom]:
    atoms, pos = [], 0
    for run in own_runs(p):
        for piece in _split_run_children(run):
            content = [c for c in piece if c.tag != q("w:rPr")]
            n = _content_len(content[0]) if content else 0
            atoms.append(_Atom(piece, pos, pos + n))
            pos += n
    return atoms


def _split_atom(atoms: list[_Atom], pos: int) -> None:
    """Ensure no text atom spans `pos` strictly inside it (only `w:t` atoms can be split)."""
    for i, atom in enumerate(atoms):
        if atom.start < pos < atom.end:
            t = atom.run.find(q("w:t"))
            cut = pos - atom.start
            left = copy.deepcopy(atom.run)
            left_t = left.find(q("w:t"))
            left_t.text, t.text = t.text[:cut], t.text[cut:]
            left_t.set(XML_SPACE, "preserve")
            t.set(XML_SPACE, "preserve")
            atom.run.addprevious(left)
            atoms[i : i + 1] = [_Atom(left, atom.start, pos), _Atom(atom.run, pos, atom.end)]
            return


def _new_run(text: str, fmt_run: etree._Element | None) -> etree._Element:
    run = etree.Element(q("w:r"))
    if fmt_run is not None and fmt_run.find(q("w:rPr")) is not None:
        run.append(copy.deepcopy(fmt_run.find(q("w:rPr"))))
    for part in re.split(r"([\t\n])", text):
        if part == "\t":
            etree.SubElement(run, q("w:tab"))
        elif part == "\n":
            etree.SubElement(run, q("w:br"))
        elif part:
            t = etree.SubElement(run, q("w:t"))
            t.text = part
            t.set(XML_SPACE, "preserve")
    return run


def _outer(el: etree._Element) -> etree._Element:
    """The element to position against: the run, or its `w:del` wrapper if it was deleted."""
    parent = el.getparent()
    return parent if parent is not None and parent.tag == q("w:del") else el


def diff_ops(old: str, new: str) -> list[tuple[int, int, str]]:
    """Non-equal regions as (old_start, old_end, replacement), from a token-level diff."""
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    a_off = [0]
    for tok in a:
        a_off.append(a_off[-1] + len(tok))
    ops: list[tuple[int, int, str]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        start, end, repl = a_off[i1], a_off[i2], "".join(b[j1:j2])
        # Merge with the previous change when only whitespace separates them, so that
        # "Acme Corp" -> "Contoso Ltd" reads as one replacement, not two.
        if ops and old[ops[-1][1] : start].isspace():
            p_start, p_end, p_repl = ops[-1]
            ops[-1] = (p_start, end, p_repl + old[p_end:start] + repl)
        else:
            ops.append((start, end, repl))
    return ops


def apply_paragraph_edit(p: etree._Element, new_text: str, redline: Redline | None) -> None:
    old_text = paragraph_text(p)
    ops = diff_ops(old_text, new_text)
    if not ops:
        return
    atoms = _atoms(p)
    for i1, i2, _ in ops:
        _split_atom(atoms, i1)
        _split_atom(atoms, i2)
    for i1, i2, repl in reversed(ops):
        removed = [a for a in atoms if a.is_text and a.start >= i1 and a.end <= i2]
        if removed:
            fmt, anchor, before = removed[0].run, removed[-1].run, False
        else:
            prev = [a for a in atoms if a.is_text and a.end <= i1]
            nxt = [a for a in atoms if a.is_text and a.start >= i1]
            if prev:
                fmt, anchor, before = prev[-1].run, prev[-1].run, False
            else:
                fmt, anchor, before = nxt[0].run, nxt[0].run, True
        if repl:
            run = _new_run(repl, fmt)
            node = redline.wrap_insert(run) if redline else run
            target = _outer(anchor)
            target.addprevious(node) if before else target.addnext(node)
        for atom in removed:
            if redline:
                redline.wrap_delete(atom.run)
            else:
                atom.run.getparent().remove(atom.run)


def apply_edits(doc: DocxDocument, edits: list[Edit], track_changes: bool = True) -> list[Change]:
    """Apply validated edits to `doc` in place and return one Change per edit."""
    redline = Redline() if track_changes else None
    by_id = {s.id: s for s in doc.segments}
    changes = []
    for edit in edits:
        seg = by_id.get(edit.id)
        if seg is None:
            changes.append(
                Change(
                    id=edit.id,
                    old_text="",
                    new_text=edit.new_text,
                    status=ChangeStatus.REJECTED,
                    reason="unknown_id",
                )
            )
            continue
        if not seg.editable:
            changes.append(
                Change(
                    id=seg.id,
                    old_text=seg.text,
                    new_text=edit.new_text,
                    status=ChangeStatus.SKIPPED,
                    reason=seg.skip_reason,
                )
            )
            continue
        if edit.new_text.count("\n") > seg.text.count("\n"):
            changes.append(
                Change(
                    id=seg.id,
                    old_text=seg.text,
                    new_text=edit.new_text,
                    status=ChangeStatus.REJECTED,
                    reason="paragraph_split",
                )
            )
            continue
        if edit.new_text == seg.text:
            continue
        apply_paragraph_edit(doc.paragraphs[seg.id], edit.new_text, redline)
        changes.append(
            Change(
                id=seg.id, old_text=seg.text, new_text=edit.new_text, status=ChangeStatus.APPLIED
            )
        )
    return changes
