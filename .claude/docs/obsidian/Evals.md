---
title: Evals
tags:
  - evals
  - quality
---

# Evals and the oracle

Hub: [[INDEX]]

The method behind this project (`ai-factory-kit`): autonomy is earned by the **oracle**, the
check that decides whether work was done correctly. Here the oracle is the structure check in
[[invariants]], run on every edit and in every test.

## Structure check

- **DOCX** (`check_docx`): paragraph and table counts, table shapes, section properties, every
  other package part, full XML of every unedited paragraph, formatting of every unchanged
  character (aligned by the same word-level diff the writer uses), rejecting all tracked
  changes restores the original text, edits introduce no new formatting.
- **PDF** (`check_pdf`): page count and sizes, images, vector graphics; every untouched span
  keeps text and position (0.5 pt) or sits exactly `dy` lower if it moved within its section;
  moved text overlaps nothing that stayed; new text keeps its colour, does not shrink below
  80%, stays in its box and overlaps no other text or graphics.
- **Negative controls:** every check has a test that breaks the behaviour on purpose and
  expects the check to go red (`tests/test_docx_writer.py`, `tests/test_pdf.py`).

## Suites

- `uv run poe test` — unit tests without LibreOffice or a model; `poe test-all` adds tests
  marked `soffice`; `pytest -m live` runs Ollama and CLI smoke tests. CI runs lint, `test-all`
  and `eval`.
- `uv run poe eval` — [[evals-run-invariants]]: every fixture through the full pipeline with
  the scripted provider ([[llm-scripted]]); no model involved.
- `uv run poe eval-models` — [[evals-run-models]]: 8 tasks from `evals/tasks.yaml` (replace
  names, proofread, anonymise, translate, "first paragraph" — DOCX and PDF), checked
  deterministically; over-editing fails a task. Results in `evals/results/`.
- Fixtures — [[evals-make-fixtures]]: `report_en.docx`, `contract_ru.docx/.doc` and their LibreOffice
  PDFs, `layout.pdf` (columns, image, shaded box), `sections.pdf` (two sections, one line per
  text object, for reflow).

## Latest model results (8 tasks)

| Model | Passed | Structure |
|---|---|---|
| `cli:claude` haiku | 8/8 | 8/8 |
| `ollama` qwen3.5:9b (default) | 7/8 | 8/8 |
| `ollama` gemma4:12b | 5/8 | 8/8 |
| `ollama` qwen3.5:4b | 5/8 | 8/8 |

No model produced invalid JSON or invented IDs; failures are content mistakes (over-editing,
missed surname, wrong "first paragraph").
