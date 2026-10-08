---
title: src/ai_doc_editor/editor.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/editor.py`

Section: [[Backend]]

## Purpose

Orchestration: document in, edited document plus change report out (spec.md section 3).

## Classes

### `DocumentError` (ValueError)

The input cannot be processed (format, size, encryption).


### `EditResult`

Output paths of a run: edited file, report JSON/HTML, converted file, gate.

Fields: `output`, `report`, `report_json`, `report_html`, `converted`, `gate`


## Functions

- `def convert_output(path: Path, target: str, out_dir: Path, tol_pt: float) -> Conversion` — Convert `path` to `target` ("docx" | "pdf"); a file failing the gate is renamed.
- `def _batches(segments: list[Segment], max_chars: int) -> list[list[Segment]]` — Groups segments into batches of at most `max_chars` characters, never splitting a segment.
- `def resolve_scope(provider: LLMProvider, instruction: str, segments: list[Segment]) -> list[str] | None` — Ids the instruction targets, or None when it applies to the whole document.
- `def request_edits(provider: LLMProvider, instruction: str, segments: list[Segment], max_chars: int, progress: Progress | None=None) -> tuple[list[Edit], list[Change]]` — Ask the provider for edits batch by batch; returns valid edits and rejected changes.
- `def _apply_pdf(writer: PdfWriter, edits: list[Edit], by_id: dict[str, Segment], provider: LLMProvider, instruction: str) -> list[Change]` — AC-5: fits -> applied; else ask to shorten, then allow shrinking to 80%, else reject.
- `def normalise_input(src: Path, work_dir: Path, settings: Settings) -> Path` — Checks extension and size; converts `.doc` to `.docx` with LibreOffice.
- `def edit_document(src: Path, instruction: str, provider: LLMProvider, out_dir: Path, track_changes: bool=True, progress: Progress | None=None, settings: Settings | None=None, convert_to: str | None=None, scope_from: str | None=None) -> EditResult` — Edit `src` by `instruction`.

## Related

- [[convert]]
- [[docx-reader]]
- [[docx-writer]]
- [[invariants]]
- [[llm-base]]
- [[llm-prompts]]
- [[models]]
- [[pdf-reader]]
- [[pdf-writer]]
- [[report]]
- [[settings]]
- [[soffice]]
