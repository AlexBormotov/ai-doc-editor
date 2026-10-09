---
title: Planning
tags:
  - planning
---

# Planning

Hub: [[INDEX]]

The approval chain of the method kit lives in `docs/`: `intent.md` → `spec.md` → `plan.md`. Deviations from the plan are recorded in `plan.md` → Deviations, never silently.

## Current stage

Demo for a client request about AI-powered Word/PDF editing that preserves structure and
formatting. Plan steps 0–11 are done, plus owner-requested changes after delivery: paragraph
segmentation for browser-printed PDFs, the scope step for targeted instructions, PDF section
reflow, rename to `ai-doc-editor`. Public repository: github.com/AlexBormotov/ai-doc-editor.

## Known limitations

- No OCR: scanned PDFs are not supported.
- Password-protected PDFs and PDF forms are not supported.
- DOCX paragraphs with fields, note references, equations or existing revisions are skipped.
- PDF: subset fonts cannot be reused → metric-similar substitute; mixed inline styles are
  flattened to the dominant style.
- PDF reflow stays within one section on one page; nothing moves across pages.
- Layout fidelity of DOCX is defined by LibreOffice and depends on available fonts.
- AC-12 (200 pages / 100 MB) has no test with a file of that size.

## Roadmap

- v2: OCR for scanned PDFs (Tesseract / docTR), editing the recognised text layer.
- Keep inline styles in PDF edits (map the word diff onto spans, like the DOCX writer).
- Comments with the model's reasoning next to tracked changes.
- Footnotes, endnotes, text inside fields.
- Async jobs with progress streaming for long documents.

Completed work is logged in [[Timeline]].
