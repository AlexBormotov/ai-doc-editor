# ai-doc-editor

Edit Word and PDF documents with an LLM without breaking their layout.

Upload a `.docx`, `.doc` or `.pdf`, write an instruction ("make the tone formal", "replace Acme Corp
with Contoso Ltd", "translate to Russian", "remove personal data") or pick a preset, and get the
same document back with only the text changed. Tables, styles, margins, headers, images and page
breaks stay where they were. Word output can carry tracked changes, so every AI edit can be
accepted or rejected in Word.

Runs fully offline with local models (Ollama, LM Studio). Cloud APIs (OpenAI, Anthropic, Google)
and subscription CLIs (`claude`, `codex`, `agy`) plug in through the same interface.

> Status: in development. See `plan.md`.

## Why most "AI document editors" break formatting

The common approach converts the document to text or Markdown, asks the model to rewrite it, and
builds a new document from the answer. The model's output has no idea where a run of bold text
started, which table cell a sentence lived in, or how far a paragraph sat from the page edge. The
result looks like a different document.

## How this one works

The model never sees or writes a whole document.

1. **Parse into segments.** Each Word paragraph (body, tables, headers, footers, text boxes) and
   each PDF text block gets a stable ID.
2. **Ask for edits, not documents.** The model receives `[{id, text}]` and returns only the
   segments it changed: `{"edits": [{id, new_text}]}`. Answers with unknown IDs or an invalid schema
   are rejected, not guessed at.
3. **Write back in place.**
   - **Word:** a word-level diff between old and new text. Unchanged characters keep their original
     runs and formatting. Only the changed spans are replaced, optionally as tracked changes
     (`w:ins` / `w:del`).
   - **PDF:** only edited blocks are touched. The old text is removed with a redaction that leaves
     images and vector graphics alone. The new text is set in the same font, size, colour and
     alignment, inside the original block rectangle. If it does not fit, the model is asked to
     shorten it, then the font may shrink to 80%. If it still does not fit, the original stays and
     the report says why. Blocks never move.
4. **Prove it.** Every run produces a change report. A deterministic test suite checks, on
   generated documents, that untouched paragraphs, runs, tables, sections and PDF blocks are
   identical after editing.

## Format conversion with a layout gate

DOCX to PDF and PDF to DOCX are available, but a conversion is only presented as done when it
passes a layout gate: the result is re-rendered and compared with the source, page by page (same
page count, margins within 2 pt, text blocks in the same positions). If the gate fails, you see
which page and block moved, and you can still download the file marked "layout not verified".

Word is flow layout and PDF is fixed layout, so no tool can promise identical pages for every
document. This project measures each conversion instead of promising.

## Features

- Formats: `.docx`, `.doc` (converted on input), digital `.pdf`
- Presets: proofread, formalize, translate, anonymize, plus free-form instructions
- Tracked changes in Word output (on by default)
- Change report (HTML and JSON) with per-segment status
- Before and after page previews in the web UI
- HTTP API (FastAPI) and web UI (Gradio) in one process, plus a CLI
- LLM backends: Ollama, LM Studio, OpenAI, Anthropic, Google Gemini, `claude` / `codex` / `agy` CLIs
- Limits: 200 pages, 100 MB per document (configurable)

## Stack

Python 3.12, uv, FastAPI, Gradio, python-docx and lxml, PyMuPDF, pdf2docx, LibreOffice headless,
pydantic, pytest, ruff, Docker Compose.

## Quick start (planned)

```bash
# 1. A local model (installed by you, not by this project)
ollama pull gemma4:12b

# 2a. Docker (includes LibreOffice)
cp .env.example .env
docker compose up --build
# open http://localhost:8000/ui

# 2b. Or locally (Python 3.12, LibreOffice optional for .doc and conversion)
uv sync
uv run poe serve
```

CLI:

```bash
uv run ai-doc-editor edit contract.docx -i "Replace Acme Corp with Contoso Ltd" -o contract.edited.docx
```

## Recommended local models

To be filled with measured results from `evals/results/` (valid-JSON rate, task success, seconds
per page) on an 8 GB GPU. Candidates: `gemma4:12b` (default) and one or two 4-8B models.

## Limitations

- Scanned PDFs are not supported (no OCR yet).
- Password-protected PDFs and PDF forms are not supported.
- Paragraphs with fields, footnotes or equations are left unchanged and listed in the report.
- In PDFs, a block with mixed fonts is rewritten in its dominant style.
- Layout fidelity is measured against LibreOffice rendering; Microsoft Word may differ slightly.

## Roadmap

- **v2: OCR.** Scanned PDFs through Tesseract or docTR, with the recognised text layer edited the
  same way and written back as an invisible text layer over the image.
- Comments with the model's rationale next to each tracked change.
- Footnotes, endnotes and text inside fields.
- Async jobs and progress streaming for long documents.

## Project method

Built with an explicit intent, spec and plan chain (`intent.md`, `spec.md`, `plan.md`) and an
oracle-first test approach: the invariant checks decide whether formatting survived, not a human
eyeballing output.
