---
title: src/ai_doc_editor/report.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/report.py`

Section: [[Backend]]

## Purpose

Change report as JSON and as a self-contained HTML page (AC-7).

## Functions

- `def word_diff_html(old: str, new: str) -> str` — Word-level diff of two texts as HTML with `<del>`/`<ins>`.
- `def write_json(report: ChangeReport, path: Path) -> None` — Writes the report as JSON.
- `def write_html(report: ChangeReport, path: Path) -> None` — Writes the self-contained HTML report (summary, structure check, scope, gate, change table).

## Related

- [[docx-writer]]
- [[models]]
