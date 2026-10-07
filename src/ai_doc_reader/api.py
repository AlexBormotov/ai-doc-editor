"""HTTP API (spec.md 4.6) with the Gradio UI mounted at /ui."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse

from ai_doc_reader import __version__
from ai_doc_reader.editor import SUPPORTED, DocumentError, edit_document
from ai_doc_reader.llm.base import LLMError
from ai_doc_reader.llm.registry import PROVIDERS, get_provider, list_models
from ai_doc_reader.presets import PRESETS, build_instruction
from ai_doc_reader.settings import get_settings

app = FastAPI(title="ai-doc-reader", version=__version__)
_SAFE_NAME = re.compile(r"[^\w.\-]+", re.UNICODE)


def runs_dir() -> Path:
    path = Path(get_settings().runs_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_run(filename: str) -> tuple[str, Path, Path]:
    """A fresh run directory and a safe path for the uploaded file inside it."""
    run_id = uuid.uuid4().hex[:12]
    run = runs_dir() / run_id
    (run / "in").mkdir(parents=True)
    name = _SAFE_NAME.sub("_", Path(filename).name) or "document"
    return run_id, run, run / "in" / name


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/ui")


@app.get("/api/providers")
def providers() -> dict:
    s = get_settings()
    return {
        "default": {"provider": s.default_provider, "model": s.default_model},
        "providers": {key: list_models(key) for key in PROVIDERS},
        "presets": PRESETS,
    }


@app.post("/api/edit")
async def edit(
    file: UploadFile = File(...),
    instruction: str = Form(""),
    preset: str = Form(""),
    provider: str = Form(""),
    model: str = Form(""),
    track_changes: bool = Form(True),
    convert_to: str = Form("none"),
) -> dict:
    s = get_settings()
    if Path(file.filename or "").suffix.lower() not in SUPPORTED:
        raise HTTPException(415, "upload a .docx, .doc or .pdf file")
    try:
        text = build_instruction(preset or None, instruction)
        llm = get_provider(provider or s.default_provider, model or s.default_model)
    except (ValueError, LLMError) as e:
        raise HTTPException(422, str(e)) from e
    run_id, run, src = new_run(file.filename or "document")
    with src.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        result = await run_in_threadpool(
            edit_document,
            src,
            text,
            llm,
            run / "out",
            track_changes,
            None,
            s,
            None if convert_to in ("", "none") else convert_to,
            instruction,
        )
    except DocumentError as e:
        raise HTTPException(422, str(e)) from e
    except LLMError as e:
        raise HTTPException(502, f"model backend failed: {e}") from e

    def url(path: Path | None) -> str | None:
        return f"/api/files/{run_id}/{path.relative_to(run / 'out').as_posix()}" if path else None

    return {
        "run_id": run_id,
        "result": url(result.output),
        "converted": url(result.converted),
        "gate": result.gate.model_dump() if result.gate else None,
        "report_html": url(result.report_html),
        "report_json": url(result.report_json),
        "structure_verified": not result.report.violations,
        "report": result.report.model_dump(),
    }


@app.get("/api/files/{run_id}/{name:path}")
def download(run_id: str, name: str) -> FileResponse:
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise HTTPException(404)
    base = (runs_dir() / run_id / "out").resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=path.name)


def _mount_ui() -> None:
    import gradio as gr

    from ai_doc_reader.ui import build_ui

    gr.mount_gradio_app(app, build_ui(), path="/ui", allowed_paths=[str(runs_dir())])


_mount_ui()
