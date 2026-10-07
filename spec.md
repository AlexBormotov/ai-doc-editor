# Spec: ai-doc-reader

Implements `intent.md` (REQ-001). Architecture document at the deployable-unit level: there is one
unit, the `app` service. Component names below are the code symbol names; keep them in sync.

## 1. Glossary (canonical terms)

| Term | Meaning | Code symbol |
|---|---|---|
| document | one input file after normalisation to `.docx` or `.pdf` | `Document` |
| segment | the smallest unit of text the model may change: a DOCX paragraph (`w:p`) or a PDF text block | `Segment` |
| segment id | stable string ID of a segment within one document, e.g. `d:body/p/17`, `p:3/b/5` | `Segment.id` |
| edit | the model's proposed replacement text for one segment | `Edit` |
| change | an edit after it was applied (or refused) by a writer, with its status | `Change` |
| change report | all changes of one run, JSON and HTML | `ChangeReport` |
| writer | format-specific component that applies edits in place | `DocxWriter`, `PdfWriter` |
| layout gate | the check that compares a converted file against its source | `layout_gate()` |
| provider | an LLM backend behind one interface | `LLMProvider` |
| preset | a named instruction template (proofread, translate, anonymize, formalize) | `Preset` |
| fixture | a generated test document under `evals/fixtures/` | n/a |

## 2. Stack

| Concern | Choice |
|---|---|
| Runtime | Python 3.12, `uv` |
| API | FastAPI |
| UI | Gradio, mounted into the FastAPI app at `/ui` (one process) |
| DOCX | `python-docx` for reading, `lxml` for run-level and tracked-change XML |
| PDF | PyMuPDF (`pymupdf`) + `pymupdf-fonts` (Noto, Cyrillic coverage) |
| PDF to DOCX | `pdf2docx` |
| DOC to DOCX, DOCX to PDF | LibreOffice headless (`soffice`) |
| Schemas, config | `pydantic`, `pydantic-settings` |
| LLM clients | `openai` SDK (OpenAI-compatible endpoints), `anthropic` SDK, `subprocess` for CLIs |
| Tests, lint | `pytest`, `ruff` |
| Task runner | `poethepoet` (`uv run poe <task>`): one command per task, CI runs the same command |
| Container | `Dockerfile` (python:3.12-slim + libreoffice-writer + fonts), `docker-compose.yml` |

## 3. Pipeline

```
upload -> normalise (.doc -> .docx via soffice) -> parse -> segments
       -> batch segments -> provider.complete_json() -> validate edits
       -> writer applies edits in place -> change report
       -> [optional] convert -> layout_gate -> result or "layout not verified"
       -> previews (PDF pages rendered to PNG; DOCX via soffice -> PDF)
```

Package layout (`src/ai_doc_reader/`): `models.py` (Segment, Edit, Change, ChangeReport),
`docx/` (`reader.py`, `writer.py`, `redline.py`), `pdf/` (`reader.py`, `writer.py`, `fonts.py`),
`convert.py` (soffice, pdf2docx, `layout_gate`), `llm/` (`base.py`, `openai_compatible.py`,
`anthropic_provider.py`, `cli_provider.py`, `registry.py`), `editor.py` (orchestration),
`presets.py`, `report.py`, `api.py`, `ui.py`, `cli.py`, `settings.py`.
`scripts/cli_bridge.py` runs on the host, outside the package.

## 4. Contracts

### 4.1 Model contract (AC-6)

Request: system prompt with rules plus the user instruction, then a JSON array
`[{"id": str, "text": str}]` for one batch. Batch size is bounded by characters
(`BATCH_CHARS`, default 6000) and never splits a segment.

Response, validated with pydantic:

```json
{"edits": [{"id": "d:body/p/17", "new_text": "..."}]}
```

- Only changed segments are returned. An empty list is valid.
- An `id` not in the batch: that edit is dropped, status `rejected`, reason `unknown_id`.
- Invalid JSON or schema: one retry with the validation error appended. If it fails again, every
  segment of the batch is `rejected` with reason `invalid_response`.
- `new_text` must not contain newlines for DOCX paragraphs. A newline makes the edit `rejected`,
  because a paragraph split is a structural change.
- Document text is untrusted input. The system prompt states that segment text is data and that
  instructions inside it are ignored.

### 4.2 DOCX writer (AC-1, AC-2)

- Segments are all `w:p` elements in `word/document.xml`, headers and footers, including those in
  tables and text boxes. The ID encodes part and document-order index.
- A paragraph containing `w:fldChar`, `w:fldSimple`, `w:footnoteReference`, `w:endnoteReference`,
  `m:oMath` or existing `w:ins` / `w:del` is not sent to the model. Status `skipped`.
- Applying an edit: token-level diff (`difflib.SequenceMatcher` on word and whitespace tokens) between
  old and new paragraph text. Unchanged characters stay in their original runs with their original
  `w:rPr`. Deleted characters are removed, or wrapped in `w:del` / `w:delText` when tracking.
  Inserted text becomes a new run that copies the `w:rPr` of the run at the insertion point, wrapped
  in `w:ins` when tracking. Tracked changes carry `w:author="AI Doc Reader"`, `w:date` and unique
  `w:id`.
- Nothing outside the edited `w:p` children changes: no `w:pPr`, no `sectPr`, no styles part.

### 4.3 PDF writer (AC-4, AC-5)

- Segments are text blocks from `page.get_text("dict")`. A block is the unit sent to the model,
  because lines cut sentences apart.
- Only blocks with an edit are touched. For each one: the dominant span style (font, size, colour,
  flags) is taken from the block; alignment (left, centre, right, justified) is inferred from line
  positions; each original span rectangle gets a redaction with no fill, applied with
  `images=PDF_REDACT_IMAGE_NONE` and `graphics=PDF_REDACT_LINE_ART_NONE`, so images and vector art
  stay; the new text is placed with `page.insert_htmlbox(block_rect, ..., scale_low=0.8)`.
- Font: the embedded font is reused when it is not a subset. Otherwise a `pymupdf-fonts` Noto face is
  chosen by serif, mono, bold and italic flags. The report records the substitution.
- Fit (AC-5): insert at scale 1.0. If it does not fit, ask the model once to shorten to
  `floor(len(old) * fit_ratio)` characters. If it still does not fit, allow scale down to 0.8.
  If that fails, restore the original text and set status `rejected`, reason `does_not_fit`.
- A block with mixed styles is written with the dominant style. The report records
  `style_flattened`.

### 4.4 Layout gate (AC-8)

`layout_gate(source_pdf, candidate_pdf, tol_pt) -> GateResult`. DOCX is rendered to PDF with
soffice first. Checks: equal page count; equal page size per page; content margins
(the bbox union of text and drawings) within 2 pt; for every source block, a candidate block with
the same normalised text whose bbox is within `tol_pt` (default 5 pt). The result lists each
failure with page, block text excerpt and offset.

### 4.5 Providers (AC-9)

```python
class LLMProvider(Protocol):
    name: str
    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> BaseModel: ...
```

| Provider key | Class | Notes |
|---|---|---|
| `ollama` | `OpenAICompatibleProvider` | `OLLAMA_BASE_URL`, default `http://localhost:11434/v1` |
| `lmstudio` | `OpenAICompatibleProvider` | `LMSTUDIO_BASE_URL`, default `http://localhost:1234/v1` |
| `openai` | `OpenAICompatibleProvider` | `OPENAI_API_KEY` |
| `google` | `OpenAICompatibleProvider` | `GOOGLE_API_KEY`, Gemini OpenAI-compatible endpoint |
| `anthropic` | `AnthropicProvider` | `ANTHROPIC_API_KEY` |
| `cli:claude`, `cli:codex`, `cli:agy` | `CliProvider` | subscription; direct subprocess, or via the CLI bridge in Docker |
| `scripted` | `ScriptedProvider` | deterministic, no model; used by evals and tests only |

In Docker, `localhost` defaults become `host.docker.internal`.

CLI invocation runs in an empty temporary working directory, prompt on stdin, with tools disabled
or read-only: `claude -p --output-format json` with all tools disallowed, `codex exec` with
`--sandbox read-only`, `agy -p --output-format json --sandbox --mode plan`. The exact flags are
verified against each CLI's `--help` during implementation.

CLI bridge (`scripts/cli_bridge.py`): stdlib HTTP server on the host, bound to `127.0.0.1`, requires
a bearer token from `CLI_BRIDGE_TOKEN`, accepts only `{cli: "claude"|"codex"|"agy", prompt, model}`,
and never takes a free command line. The container calls it at `http://host.docker.internal:<port>`.
If Docker Desktop cannot reach a host service bound to `127.0.0.1`, CLI providers are dropped from
Docker mode (local `uv run` only) and the bridge is not shipped. Binding to `0.0.0.0` is not an
acceptable fallback, because it exposes an agent CLI to the LAN.

### 4.6 HTTP API

- `GET /health`
- `GET /api/providers`: configured providers and their models (queried live from Ollama and LM Studio)
- `POST /api/edit` (multipart): `file`, `instruction`, `preset`, `provider`, `model`,
  `track_changes` (bool), `convert_to` (`none` | `docx` | `pdf`). Synchronous. Returns a JSON body
  with download URLs for the result, the converted file, the gate result and the report.
- `GET /api/files/{run_id}/{name}`: downloads from the run's temp directory.

### 4.7 Limits (AC-12)

`MAX_PAGES=200`, `MAX_UPLOAD_MB=100`, configurable.

## 5. Decision records

**DR-1. Segment-level editing instead of whole-document generation.**
Need: the client's core requirement is that formatting survives, and an LLM that regenerates a
document re-lays it out. Choice: the model sees and returns only text segments by ID, and writers
change text inside existing objects. Cost: the model lacks cross-segment context beyond its batch,
so edits that need to merge or split paragraphs are impossible by design.

**DR-2. Token-diff run mapping for DOCX.**
Need: rewriting a paragraph into its first run loses inline formatting (bold words, links).
Choice: diff old against new text and touch only the changed spans; the same diff produces tracked
changes. Cost: inserted text inherits formatting from its neighbour, which is sometimes wrong at a
style boundary.

**DR-3. Block-level PDF segments, rewritten inside the original box.**
Need: line-level segments break sentences and give the model nonsense, while free reflow moves
blocks. Choice: the block is the segment, the block rectangle is the hard boundary, and text is
reflowed only inside it. Cost: mixed-style blocks are flattened to their dominant style, and the
report says so.

**DR-4. Conversion is gated, not guaranteed.**
Need: DOCX is flow layout and PDF is fixed layout, so one-to-one page fidelity cannot be promised
for arbitrary input. Choice: convert, re-render, compare, and refuse to present a failing result as
done. Cost: some conversions are refused. LibreOffice is the reference renderer and Word may differ.

**DR-5. Three provider adapters, no LiteLLM.**
Need: nine backends. Choice: six are OpenAI-compatible, so one adapter plus Anthropic plus CLI.
Cost: provider-specific features (prompt caching, native structured output) are unused.

**DR-6. `poethepoet` instead of a Makefile.**
Need: the kit requires one command per task, shared by contributor and CI, and the development
machine (Windows) has no `make`. Choice: `[tool.poe.tasks]` in `pyproject.toml`, invoked as
`uv run poe <task>` locally and in CI. Cost: one more dev dependency, and a deviation from the kit's
literal file tree (its intent is kept).

**DR-7. LibreOffice is the reference renderer.**
Need: previews, DOCX to PDF and the layout gate need a renderer that runs headless on Linux.
Choice: `soffice --headless`. Cost: fidelity is defined against LibreOffice, not Word, and README
says so.
