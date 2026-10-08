---
title: Backend
tags:
  - backend
---

# Backend

Hub: [[INDEX]]

**Stack:** Python 3.12, uv, FastAPI + uvicorn, python-docx + lxml (DOCX), PyMuPDF (PDF),
pdf2docx, LibreOffice headless (`.doc` input, DOCX→PDF, previews, layout gate), pydantic /
pydantic-settings, `openai` and `anthropic` SDKs, subprocess for subscription CLIs, Docker
Compose. Tasks run through `poethepoet` (`uv run poe lint|test|test-all|eval|eval-models|serve`).

## Architecture

```
upload -> normalise (.doc -> .docx)                         [[editor]] [[soffice]]
       -> parse into segments                               [[docx-reader]] [[pdf-reader]]
       -> free-form instruction? scope step: the model picks target ids from an outline
       -> batches -> provider.complete_json() -> validate   [[llm-base]] [[llm-prompts]]
       -> writers apply edits in place                      [[docx-writer]] [[pdf-writer]]
       -> structure check (oracle)                          [[invariants]]
       -> change report (JSON + HTML)                       [[report]]
       -> optional conversion behind the layout gate        [[convert]]
```

Key rules (from `spec.md`):

- **The model never sees or writes a whole document.** It gets `[{id, text}]` and returns
  `{"edits": [{id, new_text}]}`. Unknown IDs, invalid JSON (after one retry), paragraph splits
  and emptied segments are rejected and reported.
- **DOCX:** a word-level diff decides which characters change; unchanged characters keep their
  runs and `w:rPr`; changes are written as `w:ins`/`w:del` tracked changes (author
  "AI Doc Editor") or directly. Paragraphs with fields, note references, equations or existing
  revisions are skipped.
- **PDF:** segments are rebuilt from lines (also across one-line blocks of browser-printed
  PDFs). Edited text is wrapped with real font metrics in the original font when it is
  embedded in full, else a URW substitute. A **section** (same column and size, up to a
  heading/graphic/image) reflows: an edited paragraph may change its line count and the
  paragraphs below it move by `dy`, redrawn from a stripped copy of the original page. Nothing
  crosses the barrier. Too long → ask the model to shorten → shrink to 80% → reject.
- **Providers** behind one interface: Ollama, LM Studio, OpenAI, Gemini (OpenAI-compatible),
  Anthropic (SDK), `claude`/`codex`/`agy` CLIs (headless, tools off, empty temp dir; from Docker
  through the host bridge on `127.0.0.1` with a token).

## HTTP API

- `GET /health`, `GET /api/providers`
- `POST /api/edit` (multipart: file, instruction, preset, provider, model, track_changes,
  convert_to) → download URLs, gate, report, `structure_verified`
- `GET /api/files/{run_id}/{name}` — downloads, path traversal rejected

## Code map

Core and orchestration:

- [[package-init]] — package version
- [[models]] — `Segment`, `Edit`, `EditBatch`, `Scope`, `Change`, `ChangeReport`
- [[settings]] — environment configuration
- [[editor]] — orchestration: scope, batches, PDF fit loop, structure check, report
- [[presets]] — proofread / formalize / translate / anonymize
- [[report]] — change report as JSON and HTML
- [[invariants]] — the oracle (also described in [[Evals]])

Formats:

- [[docx-reader]] — DOCX segments
- [[docx-writer]] — run-preserving diff writer
- [[docx-redline]] — tracked-change wrappers
- [[pdf-reader]] — PDF segments, alignment, free space
- [[pdf-writer]] — sections, reflow, fonts, drawing
- [[convert]] — conversions and the layout gate
- [[soffice]] — LibreOffice wrapper

LLM:

- [[llm-base]] — provider interface, JSON extraction, retry
- [[llm-prompts]] — system prompts, edit / shorten / scope requests
- [[llm-openai-compatible]] — Ollama, LM Studio, OpenAI, Gemini
- [[llm-anthropic-provider]] — Anthropic API
- [[llm-cli-provider]] — subscription CLIs and the bridge client
- [[llm-scripted]] — deterministic provider for tests and evals
- [[llm-registry]] — provider keys → instances, model lists

Entry points:

- [[api]] — FastAPI app
- [[cli]] — `ai-doc-editor edit|providers`
- [[scripts-cli-bridge]] — host bridge for CLIs used from Docker
