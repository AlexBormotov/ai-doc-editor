"""Deterministic provider for tests and the invariant eval: no model, regex rules only."""

from __future__ import annotations

import json
import re

from ai_doc_reader.llm.base import LLMProvider
from ai_doc_reader.llm.prompts import SEGMENTS_MARKER, parse_segments


class ScriptedProvider(LLMProvider):
    """Applies `rules` [(pattern, replacement), ...] to every segment and reports the changes.

    `raw_reply`, when set, is returned verbatim instead (to test invalid responses).
    """

    key = "scripted"

    def __init__(self, rules: list[tuple[str, str]] | None = None, raw_reply: str | None = None):
        super().__init__("rules")
        self.rules = [(re.compile(p), r) for p, r in (rules or [])]
        self.raw_reply = raw_reply
        self.calls = 0

    def complete_text(self, system: str, user: str, schema: dict) -> str:
        self.calls += 1
        if self.raw_reply is not None:
            return self.raw_reply
        if SEGMENTS_MARKER not in user:  # scope request: rules apply everywhere
            return json.dumps({"scope": "all", "ids": []})
        edits = []
        for seg in parse_segments(user):
            new = seg["text"]
            for pattern, repl in self.rules:
                new = pattern.sub(repl, new)
            if new != seg["text"]:
                edits.append({"id": seg["id"], "new_text": new})
        return json.dumps({"edits": edits}, ensure_ascii=False)
