---
title: Frontend
tags:
  - frontend
---

# Frontend

Hub: [[INDEX]]

**Stack:** Gradio 6 Blocks, mounted into the FastAPI app ([[api]]) at `/ui` — one process, one
container. Dark default theme; page previews are PNGs rendered with PyMuPDF (DOCX through
LibreOffice first).

## Routes

- `/ui` — the editor UI (public, no auth; the service is meant to run locally)
- `/` — redirects to `/ui`
- `/docs` — FastAPI Swagger UI for the HTTP API (see [[Backend]])

## Screen

- **Left:** document upload (`.docx`, `.doc`, `.pdf`), preset (default `(none)`), free-form
  instruction, provider and model (live list), "tracked changes" switch for Word, optional
  conversion (`docx` / `pdf`, layout-checked), "Edit document".
- **Right:** status (changed / rejected / skipped, time, provider/model; which segments the
  scope step chose; structure check; gate result), downloads (edited file, converted file,
  `report.html`, `report.json`), tabs **Preview** (before/after pages), **Changes** (the change
  report with a word-level diff, dark styling), **JSON** (raw report).

## Code map

- [[ui]] — layout and the button handler
- [[preview]] — before/after page images
