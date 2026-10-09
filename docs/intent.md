---
id: REQ-001
title: Layout-preserving AI editing of Word and PDF documents
owner: alexvicbor (product owner and approver)
status: approved 2026-10-07 (grilling rounds 1-2)
review_date: 2026-10-08
---

# REQ-001. Layout-preserving AI editing of Word and PDF documents

## Outcome and who wants it

A prospective client asked whether we have done "AI-powered document processing and editing,
specifically working with different types of documents/files (primarily Word and PDF), analyzing and
editing their content using AI, while preserving the document structure and formatting, and
generating the final edited documents back in Word and PDF formats."

We want a small, runnable demo project that answers that question with working code. A user uploads
a `.docx`, `.doc` or `.pdf`, gives an instruction in natural language (or picks a preset), and gets
back the edited document in the same format. The AI changes text in place. It never re-lays-out the
document: unchanged objects stay byte-for-byte or position-for-position where they were, and changed
text stays inside the object it came from.

## Acceptance criteria

1. **AC-1.** A `.docx` file is edited by instruction and returned as `.docx`. Paragraph count, table
   count and table shape, section page setup (size, orientation, margins), headers and footers, and
   the run formatting of every unchanged character are identical to the input.
2. **AC-2.** Edits in `.docx` can be emitted as tracked changes (`w:ins` / `w:del`, author
   `AI Doc Editor`), so each edit can be accepted or rejected in Word. A UI switch controls this. It
   is on by default.
3. **AC-3.** A legacy `.doc` file is accepted. It is converted to `.docx` on input with LibreOffice
   headless and then handled as in AC-1.
4. **AC-4.** A digital (text-layer) `.pdf` is edited by instruction and returned as `.pdf`. Page
   count and page sizes are unchanged. Every unchanged text block keeps its text and its bounding box.
   Every changed block is written inside its original bounding box. Images and vector graphics are
   kept.
5. **AC-5.** When new PDF text does not fit its original box, the system first asks the model to
   shorten it, then shrinks the font to no less than 80% of the original size. If it still does not
   fit, the original text is kept and the segment is marked in the report. Blocks are never moved.
6. **AC-6.** The model never receives or produces a whole document. It receives segments with IDs
   and returns changes for those IDs only. A response with an unknown ID or an invalid schema is
   rejected for that segment and recorded in the report.
7. **AC-7.** Every run produces a change report (JSON and HTML): per segment the old text, the new
   text and a status (`applied`, `shrunk`, `shortened`, `rejected`, `skipped`).
8. **AC-8.** Format conversion is offered (DOCX to PDF, PDF to DOCX) behind a layout gate. The output
   is re-rendered and compared with the source: equal page count, page margins within 2 pt, text
   block positions within the configured tolerance, same text. If the gate fails, the file is not
   presented as the result. The user sees which page and block failed and may still download the
   file marked as "layout not verified".
9. **AC-9.** The LLM backend is selectable per request from: Ollama, LM Studio, OpenAI API,
   Anthropic API, Google Gemini API, and subscription CLIs (`claude`, `codex`, `agy`). Local models
   (Ollama, LM Studio) are the default. Ollama and LM Studio are installed by the user and are not
   part of this project's install.
10. **AC-10.** The service runs with `docker compose up` (app with LibreOffice inside) and locally
    with `uv run` on Python 3.12. It exposes an HTTP API and a clickable web UI with before/after
    page previews.
11. **AC-11.** A deterministic evaluation suite proves AC-1, AC-4, AC-5 and AC-6 on generated
    fixtures without a live model. A second suite measures real models (valid-JSON rate, invented-ID
    rate, task success, latency). README states the measured results for the recommended local
    models.
12. **AC-12.** Documents up to 200 pages and 100 MB are accepted.

## Out of scope

- OCR of scanned PDFs (README roadmap, v2).
- Password-protected or encrypted PDFs, PDF forms (AcroForm/XFA).
- Comments with edit rationale in DOCX (roadmap).
- Guaranteed rendering equality in Microsoft Word. LibreOffice is the reference renderer.
- Footnotes, endnotes, field codes, equations: paragraphs containing them are not edited and are
  reported as `skipped`.
- Pushing to a remote repository. Only on the owner's explicit command.
- User accounts, persistence of documents between runs, multi-tenant deployment.
