"""Tracked-change (redline) elements: `w:ins` and `w:del` (spec.md 4.2)."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

from lxml import etree

from ai_doc_editor.docx.reader import q

AUTHOR = "AI Doc Editor"


class Redline:
    """Creates revision wrappers that share one author and timestamp, with unique IDs."""

    def __init__(self, author: str = AUTHOR, start_id: int = 900_000):
        self.author = author
        self.date = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._ids = itertools.count(start_id)

    def _wrapper(self, tag: str) -> etree._Element:
        el = etree.Element(q(tag))
        el.set(q("w:id"), str(next(self._ids)))
        el.set(q("w:author"), self.author)
        el.set(q("w:date"), self.date)
        return el

    def wrap_insert(self, run: etree._Element) -> etree._Element:
        ins = self._wrapper("w:ins")
        ins.append(run)
        return ins

    def wrap_delete(self, run: etree._Element) -> None:
        """Wrap `run` in place with `w:del`; its `w:t` children become `w:delText`."""
        for t in run.findall(q("w:t")):
            t.tag = q("w:delText")
        wrapper = self._wrapper("w:del")
        run.addprevious(wrapper)
        wrapper.append(run)
