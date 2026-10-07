# Plan: ai-doc-reader

Implements `intent.md` (REQ-001) per `spec.md`. Approver: alexvicbor. Deadline: end of 2026-10-07.

Each step lands as one commit. Every step is reversed with `git revert <sha>`; no step needs more
than that (G9). A step is done only when its **check** command exits 0. The check commands are the
same ones CI runs.

Deviation rule (approved, Q19): if implementation proves a fact in this plan false, work does not
stop. The contradicting evidence is logged in **Deviations** below with the step, the fact, the
evidence and the alternative taken. The nearest safe alternative is used. The deviation is flagged
in the final report.

## Facts this plan rests on

| # | Fact | How verified |
|---|---|---|
| F1 | `uv`, Docker Desktop, Ollama (`gemma4:12b`), LM Studio, `claude`, `codex`, `agy` are installed on the dev machine | checked 2026-10-06/07 |
| F2 | LibreOffice is **not** installed locally | checked 2026-10-06 |
| F3 | `make` is not installed; `winget` and `choco` are | checked 2026-10-07 |
| F4 | GPU RTX 4070 Laptop 8 GB, RAM 32 GB | `nvidia-smi` |
| F5 | `agy -p` supports `--output-format json`, `--json-schema`, `--sandbox`, `--mode plan` | `agy --help` |
| F6 | Docker Desktop lets a container reach a host service bound to `127.0.0.1` via `host.docker.internal` | **unverified**, checked in step 9 |
| F7 | PyMuPDF `insert_htmlbox` supports `scale_low` and reports the scale used | **unverified**, checked in step 5 |

## Steps

### 0. Repository skeleton
Files: `pyproject.toml` (Python 3.12, deps from spec section 2, poe tasks), `.gitignore`,
`.env.example`, `src/ai_doc_reader/__init__.py`, `tests/test_smoke.py`, `AGENTS.md`, `CLAUDE.md`,
`.github/workflows/ci.yml`.
`.gitignore` excludes `ai-factory-kit/`, `CONTEXT.md` and `GRILL.md` (client correspondence and
private notes), `samples/private/`, `runs/`, `.env`.
Poe tasks: `lint` (ruff check + format check), `test` (pytest -m "not live and not soffice"),
`test-all`, `eval`, `eval-models`, `fixtures`, `serve`.
Check: `uv sync && uv run poe lint && uv run poe test`.

### 1. Fixtures generator
Files: `evals/make_fixtures.py`. Generates DOCX: headings, styled runs (bold, italic, colour,
hyperlink) inside one paragraph, a numbered and a bulleted list, a 3x4 table with merged cells,
header and footer with page number field, two-column section, custom margins, landscape section,
RU and EN text, a text box. PDFs are produced from the DOCX with soffice (Docker or local) and are
**committed**, so tests do not need LibreOffice. Plus one PDF built directly with PyMuPDF (exact
coordinates, image, vector line) for writer tests.
Check: `uv run poe fixtures` creates the files; `uv run poe test` passes.

### 2. Models, segment reader for DOCX
Files: `models.py`, `docx/reader.py`, `tests/test_docx_reader.py`.
Check: tests assert segment count and IDs on fixtures, and that field or footnote paragraphs are
`skipped`.

### 3. DOCX writer with run-preserving diff and tracked changes (AC-1, AC-2)
Files: `docx/writer.py`, `docx/redline.py`, `evals/invariants.py` (DOCX part),
`tests/test_docx_writer.py`.
`invariants.py` checks: paragraph and table counts, table shapes, `sectPr` equality, header and
footer XML equality for unedited parts, `w:rPr` equality for every unchanged character.
Negative control test: mutate one `w:rPr` in the output and assert the invariant check fails.
Check: `uv run poe test`. Tracked-changes output opens in LibreOffice without error (soffice test,
marked `soffice`).

### 4. PDF reader
Files: `pdf/reader.py`, `tests/test_pdf_reader.py`. Blocks, dominant style, alignment inference.
Check: `uv run poe test`.

### 5. PDF writer with fit and shrink (AC-4, AC-5)
Files: `pdf/writer.py`, `pdf/fonts.py`, `evals/invariants.py` (PDF part), `tests/test_pdf_writer.py`.
`invariants.py` checks: page count and sizes, untouched blocks keep text and bbox (0.5 pt), edited
blocks lie inside their original bbox, image and drawing counts unchanged.
Negative control: shift one untouched block and assert the check fails.
Verify F7 first.
Check: `uv run poe test`.

### 6. Providers (AC-9)
Files: `llm/*.py`, `tests/test_llm_contract.py` (validation, unknown ID, retry; uses
`ScriptedProvider` and a fake HTTP server, no network).
Live smoke tests, marked `live`: Ollama `gemma4:12b`, LM Studio if a model is loaded, each CLI with a
tiny prompt. API-key providers are tested only if their key is present in the local `.env`.
Check: `uv run poe test`; `uv run pytest -m live -k ollama` passes.

### 7. Editor orchestration, presets, change report (AC-6, AC-7)
Files: `editor.py`, `presets.py`, `report.py`, `cli.py`, `tests/test_editor.py`.
Shortening loop of AC-5 wired here. CLI: `uv run ai-doc-reader edit IN -i "..." [--preset] [--provider] [--model] [--no-track] [--convert-to]`.
Check: `uv run poe test`; `uv run poe eval` runs the deterministic suite (scripted provider over all
fixtures with invariants) and exits 0.

### 8. Conversion and layout gate (AC-3, AC-8)
Files: `convert.py`, `tests/test_convert.py` (marked `soffice`).
`.doc` input: one fixture `.doc` is produced by soffice and committed.
Check: `uv run poe test-all` inside Docker (or locally if LibreOffice is installed).

### 9. API, UI, Docker (AC-10)
Files: `api.py`, `ui.py`, `settings.py`, `Dockerfile`, `docker-compose.yml`,
`scripts/cli_bridge.py`, `tests/test_api.py`.
UI: upload, preset, instruction, provider, model (live list), track changes, convert to; output:
before/after page previews side by side, change table, downloads, gate result.
Verify F6 with a throwaway container before writing the bridge.
Check: `docker compose up -d --build`; `curl localhost:8000/health`; one end-to-end edit through the
API with Ollama on a DOCX and a PDF fixture; screenshot of the UI.

### 10. Model evaluation (AC-11)
Files: `evals/tasks.yaml` (deterministic tasks: replace names, anonymise emails and phones,
translate EN to RU checked by Cyrillic ratio, proofread planted typos), `evals/run_models.py`,
`evals/results/*.json`.
Models: `gemma4:12b` plus one or two smaller models (4-8B) pulled into Ollama. Pulling a model is a
download of several GB on the owner's machine; it is approved as part of this plan.
Check: `uv run poe eval-models --provider ollama --model gemma4:12b` writes a result file.

### 11. README
Files: `README.md` (from `DESCRIPTION.md` plus measured results, quick start, model list for
Ollama and LM Studio, limitations, roadmap with OCR as v2).
Check: every command in README's quick start is run once from a clean clone.

## Evidence

Each step's commit message names the step. Review log, written backward from the criteria: per AC,
the check that goes red when the AC is violated. Run on 2026-10-07: `uv run poe test-all`
(55 passed) and `uv run poe eval` (9/9) in a clean clone; Docker smoke (`/health`, `/ui`, PDF
proofread with `qwen3.5:9b` via the API) passed.

| AC | Check that goes red | Negative control |
|---|---|---|
| AC-1 | `check_docx` in `tests/test_docx_writer.py::test_edits_preserve_structure`, `tests/test_editor.py::test_docx_end_to_end`, `evals/run_invariants.py` | `test_negative_control_formatting_change_is_detected` (edited and unedited paragraph) |
| AC-2 | `check_docx(tracked=True)`: rejecting all revisions must restore the original; `test_replacement_inherits_formatting_of_replaced_text` checks `w:ins` author | covered by the same negative control |
| AC-3 | `test_legacy_doc_is_converted_on_input`, `.doc` rows of `poe eval` | none |
| AC-4 | `check_pdf` in `tests/test_pdf.py::test_edits_preserve_layout`, `test_pdf_end_to_end`, `poe eval` | `test_negative_control_layout_break_is_detected` (moved untouched text, stray text, hidden white text) |
| AC-5 | `test_pdf_too_long_edit_is_shortened_by_second_call`, `test_slightly_long_text_is_shrunk_within_limit`, `test_too_long_text_is_refused_not_moved`; `check_pdf` size floor | the hidden-text control covers the size/colour checks' wiring only for colour; size floor has no dedicated control |
| AC-6 | `test_skipped_unknown_and_split_are_reported`, `test_invalid_response_rejects_batch_and_leaves_document_unchanged`, `test_llm_contract.py` (retry, schema) | none |
| AC-7 | `test_docx_end_to_end` (report JSON), statuses asserted across `test_editor.py` | none |
| AC-8 | `tests/test_convert.py` (gate passes, failing gate marks the file, word moved is reported) | `test_gate_passes_identical_and_flags_moved_text` |
| AC-9 | `test_registry_knows_every_provider`; live: `pytest -m live` (Ollama, `claude`, `codex`, `agy` passed); OpenAI/Anthropic/Google API not run (no keys); LM Studio not run (server down) | none |
| AC-10 | `tests/test_api.py`; Docker smoke above | none |
| AC-11 | `poe eval` (deterministic) and `evals/results/summary.md` (measured) | the eval runs every check above |
| AC-12 | limits are settings (`MAX_PAGES=200`, `MAX_UPLOAD_MB=100`) | **uncovered**: no test uploads a 200-page or 100 MB file |

## Deviations

| Step | Planned | Actual | Why |
|---|---|---|---|
| 3, 5 | invariant checks in `evals/invariants.py` | `src/ai_doc_reader/invariants.py` | the editor also uses them to stamp a "structure verified" result on every run, so they belong to the package; `evals/` imports them |
| 3 | per-token ops | ops separated only by whitespace are merged | "Acme Corp" -> "Contoso Ltd" reads as one tracked replacement instead of two |
| 4 | segment = PyMuPDF text block | segments rebuilt from lines (split at list markers, font/size change, vertical gap, side-by-side cells, x jumps) | PyMuPDF merges a heading with the paragraph below and all list items or table cells into one block (seen on `report_en.pdf`) |
| 5 | F7: `insert_htmlbox` with `scale_low` | F7 holds, but the approach was replaced: words are wrapped with font metrics and set with `TextWriter` on the original baselines | Story adds its own margins and uses the fallback font's natural line height, so even the unchanged original text did not fit its box (scale 0.52-0.81 on every segment) |
| 5 | fallback fonts from `pymupdf-fonts` (Noto) | PyMuPDF built-in URW faces (`tiro`/`helv`/`cour` + bold/italic), which cover Cyrillic; `pymupdf-fonts` moved to dev (fixtures only) | `pymupdf-fonts` has no serif face |
| 6 | default local model `gemma4:12b` | default `qwen3.5:9b`; `gemma4:12b` kept in the list | the installed `gemma4:12b` needs a newer Ollama than the installed 0.30.7 (`412: requires a newer version of Ollama`; the 0.35.1 update is staged in the Ollama app). The owner's Ollama was not updated without asking |
| 6 | live smoke test for LM Studio | not run | the LM Studio server is not running and `lms` cannot start it. Same OpenAI-compatible code path as Ollama, which passed |
| 6 | provider call as specified | Ollama calls send `reasoning_effort: "none"` | qwen3.5 thinks by default: 37 s vs 3 s for the same tiny edit |
| 6 | invariants as in steps 3 and 5 | added after a background security review: PDF new text must keep the original colour and not shrink below 80%; DOCX edits may only reuse run formats already in the paragraph; text box host paragraphs are compared, not skipped | an edit could otherwise hide content (white or tiny text, `w:vanish`) and still pass |
| 9 | F6 unverified | F6 holds: a container reached a host service bound to `127.0.0.1` via `host.docker.internal` (Docker Desktop 28.3). The CLI bridge ships; tested end to end (`cli:claude` from the container) | |
| 9 | compose publishes port 8000 | host port is `APP_PORT` (default 8000) | port 8000 is taken on the dev machine by another service |
| 9 | UI checked with a screenshot | UI rendered in Chrome (title and upload control seen), then `ui.run` exercised directly for DOCX->PDF and PDF->DOCX with previews | the automation browser window was 313x297 px and file upload from the extension is limited to shared files |
| 9 | gate results identical locally and in Docker | they differ: in Docker, PDF->DOCX of `contract_ru.pdf` fails the gate (text differs, margins move up to 11 pt) while it passes on Windows | the source PDF uses Cambria, which Linux replaces with Caladea; the gate reports this honestly. README documents that fidelity depends on the fonts LibreOffice has |
| 9 | package index compared as XML | `[Content_Types].xml` compared by the effective content type of each part, `.rels` as a set | Linux LibreOffice writes redundant Overrides and python-docx drops them on save; the meaning is identical |
| 5 | AC-4 "changed block written inside its original bounding box" | written inside the original box **widened horizontally into free space only** (up to the nearest text, list marker, image, drawing or enclosing table cell / box, and never beyond the page's text area); never moved or widened vertically | a substituted font is wider than the original (Helvetica vs Calibri), so a one-line heading or table cell could not hold even its own unchanged text. The invariant check enforces the widened box and additionally forbids overlap with any untouched text |
