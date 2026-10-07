"""Gradio UI: upload, instruction, provider; before/after previews, change table, downloads."""

from __future__ import annotations

import re
import shutil

import gradio as gr

from ai_doc_editor.editor import DocumentError, edit_document
from ai_doc_editor.llm.base import LLMError
from ai_doc_editor.llm.registry import PROVIDERS, get_provider, list_models
from ai_doc_editor.models import ChangeStatus
from ai_doc_editor.presets import PRESETS, build_instruction
from ai_doc_editor.preview import render_pages
from ai_doc_editor.settings import get_settings

_BODY = re.compile(r"<body>(.*)</body>", re.S)
_STYLE = re.compile(r"<style>(.*?)</style>", re.S)

INTRO = """# AI Doc Editor
Edit **Word** (`.docx`, `.doc`) and **PDF** documents with an LLM **without breaking the layout**.
The model only sees text segments and returns changes for them; every change is written back into
the object it came from, and a structure check proves that everything else is untouched."""


def _models(provider: str):
    s = get_settings()
    models = list_models(provider)
    value = s.default_model if provider == s.default_provider and s.default_model else None
    value = value or (models[0] if models else "")
    return gr.Dropdown(choices=models, value=value)


def _report_fragment(html_text: str) -> str:
    """The report page's body and styles, for embedding in the UI."""
    body = _BODY.search(html_text)
    style = _STYLE.search(html_text)
    css = style.group(1).replace("body{", ".ade-report{") if style else ""
    return f"<style>{css}</style><div class=ade-report>{body.group(1) if body else ''}</div>"


def run(file, preset, instruction, provider, model, track, convert_to, progress=gr.Progress()):
    if not file:
        raise gr.Error("Upload a .docx, .doc or .pdf file.")
    try:
        text = build_instruction(preset if preset != "(none)" else None, instruction)
        llm = get_provider(provider, model or "")
    except (ValueError, LLMError) as e:
        raise gr.Error(str(e)) from e

    from ai_doc_editor.api import new_run

    _run_id, run_dir, src = new_run(file)
    shutil.copyfile(file, src)
    try:
        result = edit_document(
            src,
            text,
            llm,
            run_dir / "out",
            track_changes=track,
            progress=lambda f, m: progress(f, desc=m),
            convert_to=None if convert_to == "none" else convert_to,
            scope_from=instruction,
        )
    except (DocumentError, LLMError) as e:
        raise gr.Error(str(e)) from e

    progress(0.99, desc="Rendering previews")
    previews = run_dir / "previews"
    before = render_pages(src, previews, "before")
    after = render_pages(result.output, previews, "after")
    r = result.report
    landed = r.count(ChangeStatus.APPLIED) + r.count(ChangeStatus.SHORTENED)
    landed += r.count(ChangeStatus.SHRUNK)
    lines = [
        f"**{landed}** segment(s) changed, **{r.count(ChangeStatus.REJECTED)}** rejected, "
        f"**{r.count(ChangeStatus.SKIPPED)}** skipped · {r.duration_s:.1f} s · "
        f"{r.provider} / {r.model}",
        (
            f"🎯 Instruction applied to **{len(r.scope)}** segment(s) chosen by the model: "
            + ", ".join(f"`{i}`" for i in r.scope[:8])
        )
        if r.scope
        else "🎯 Instruction applied to the whole document.",
        "✅ **Structure check passed**: untouched content is unchanged."
        if not r.violations
        else "❌ **Structure check failed:** " + "; ".join(r.violations[:5]),
    ]
    if result.gate:
        if result.gate.passed:
            lines.append(f"✅ Converted to {result.gate.target.upper()}: layout check passed.")
        else:
            lines.append(
                f"⚠️ Converted to {result.gate.target.upper()}, but **layout NOT verified** "
                f"(file marked accordingly): " + "; ".join(result.gate.failures[:4])
            )
    files = [str(result.output), str(result.report_html), str(result.report_json)]
    if result.converted:
        files.insert(1, str(result.converted))
    report_html = _report_fragment(result.report_html.read_text(encoding="utf-8"))
    return (
        "\n\n".join(lines),
        files,
        [(str(p), f"before · page {i + 1}") for i, p in enumerate(before)],
        [(str(p), f"after · page {i + 1}") for i, p in enumerate(after)],
        report_html,
        r.model_dump(),
    )


def build_ui() -> gr.Blocks:
    s = get_settings()
    with gr.Blocks(title="AI Doc Editor") as demo:
        gr.Markdown(INTRO)
        with gr.Row():
            with gr.Column(scale=1, min_width=320):
                file = gr.File(label="Document", file_types=[".docx", ".doc", ".pdf"])
                preset = gr.Dropdown(
                    ["(none)", *PRESETS], value="(none)", label="Preset (optional)"
                )
                instruction = gr.Textbox(
                    label="Instruction (combined with the preset, if one is chosen)",
                    placeholder="e.g. Replace Acme Corp with Contoso Ltd",
                    lines=3,
                )
                with gr.Row():
                    provider = gr.Dropdown(PROVIDERS, value=s.default_provider, label="Provider")
                    model = gr.Dropdown(
                        list_models(s.default_provider),
                        value=s.default_model,
                        label="Model",
                        allow_custom_value=True,
                    )
                track = gr.Checkbox(
                    value=True, label="Word: tracked changes (accept/reject in Word)"
                )
                convert_to = gr.Radio(
                    ["none", "docx", "pdf"], value="none", label="Also convert to (layout-checked)"
                )
                go = gr.Button("Edit document", variant="primary")
            with gr.Column(scale=2):
                status = gr.Markdown()
                downloads = gr.File(label="Downloads", file_count="multiple")
                with gr.Tabs():
                    with gr.Tab("Preview"):
                        with gr.Row():
                            before = gr.Gallery(label="Before", columns=1, height=640)
                            after = gr.Gallery(label="After", columns=1, height=640)
                    with gr.Tab("Changes"):
                        changes = gr.HTML()
                    with gr.Tab("JSON"):
                        raw = gr.JSON()
        provider.change(_models, provider, model)
        go.click(
            run,
            [file, preset, instruction, provider, model, track, convert_to],
            [status, downloads, before, after, changes, raw],
        )
    return demo
