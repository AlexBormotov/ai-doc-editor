---
title: src/ai_doc_editor/llm/prompts.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/llm/prompts.py`

Section: [[Backend]]

## Purpose

Prompts for the segment-edit contract (spec.md 4.1).

## Functions

- `def edit_request(instruction: str, segments: list[dict], position: tuple[int, int, int] | None=None) -> str` — `position` = (first, last, total): where this batch sits in the document, 1-based.
- `def shorten_request(instruction: str, seg_id: str, old: str, new: str, max_chars: int) -> str` — Second call of AC-5: the edit does not fit its place on the page.
- `def parse_segments(user_message: str) -> list[dict]` — Recover the segments array from a request built by `edit_request`.
- `def scope_request(instruction: str, outline: list[tuple[str, str]], width: int=60) -> str` — Builds the scope prompt: instruction + outline lines `id | start of text`.
