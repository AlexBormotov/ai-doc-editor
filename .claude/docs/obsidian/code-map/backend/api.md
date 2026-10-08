---
title: src/ai_doc_editor/api.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/api.py`

Section: [[Backend]]

## Purpose

HTTP API (spec.md 4.6) with the Gradio UI mounted at /ui.

## Functions

- `def runs_dir() -> Path` — Absolute runs directory from settings, created on demand.
- `def new_run(filename: str) -> tuple[str, Path, Path]` — A fresh run directory and a safe path for the uploaded file inside it.
- `def health() -> dict` — `GET /health`: liveness probe with the package version.
- `def root() -> RedirectResponse` — `GET /`: redirects to the UI at `/ui`.
- `def providers() -> dict` — `GET /api/providers`: default provider/model, live model lists, presets.
- `async def edit(file: UploadFile=File(...), instruction: str=Form(''), preset: str=Form(''), provider: str=Form(''), model: str=Form(''), track_changes: bool=Form(True), convert_to: str=Form('none')) -> dict` — `POST /api/edit`: upload + instruction/preset + provider -> runs `edit_document` in a thread, returns download URLs, gate result, report.
- `def download(run_id: str, name: str) -> FileResponse` — `GET /api/files/{run_id}/{name}`: serves a run's output file; rejects bad run ids and path traversal.
- `def _mount_ui() -> None` — Mounts the Gradio UI at `/ui` with the runs dir as an allowed path.

## Related

- [[editor]]
- [[llm-base]]
- [[llm-registry]]
- [[package-init]]
- [[presets]]
- [[settings]]
- [[ui]]
