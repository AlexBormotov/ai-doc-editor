"""Orchestration: document in, edited document plus change report out (spec.md section 3)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ai_doc_reader.convert import Conversion, GateResult, docx_to_pdf, pdf_to_docx
from ai_doc_reader.docx.reader import read_docx
from ai_doc_reader.docx.writer import apply_edits
from ai_doc_reader.invariants import check_docx, check_pdf
from ai_doc_reader.llm.base import InvalidResponseError, LLMError, LLMProvider
from ai_doc_reader.llm.prompts import SYSTEM, edit_request, shorten_request
from ai_doc_reader.models import Change, ChangeReport, ChangeStatus, Edit, EditBatch, Segment
from ai_doc_reader.pdf.reader import read_pdf
from ai_doc_reader.pdf.writer import PdfWriter
from ai_doc_reader.report import write_html, write_json
from ai_doc_reader.settings import Settings, get_settings
from ai_doc_reader.soffice import convert

Progress = Callable[[float, str], None]
SUPPORTED = {".docx", ".doc", ".pdf"}


class DocumentError(ValueError):
    """The input cannot be processed (format, size, encryption)."""


@dataclass
class EditResult:
    output: Path
    report: ChangeReport
    report_json: Path
    report_html: Path
    converted: Path | None = None
    gate: GateResult | None = None


def convert_output(path: Path, target: str, out_dir: Path, tol_pt: float) -> Conversion:
    """Convert `path` to `target` ("docx" | "pdf"); a file failing the gate is renamed."""
    src_ext = path.suffix.lower().lstrip(".")
    if target == src_ext:
        raise DocumentError(f"the document is already .{target}")
    conv_dir = out_dir / "converted"
    if target == "pdf":
        conv = docx_to_pdf(path, conv_dir)
    elif target == "docx":
        conv = pdf_to_docx(path, conv_dir, tol_pt)
    else:
        raise DocumentError(f"cannot convert to {target!r}")
    if not conv.gate.passed:
        marked = conv.path.with_name(f"{conv.path.stem}.LAYOUT-NOT-VERIFIED{conv.path.suffix}")
        conv.path.replace(marked)
        conv.path = marked
    return conv


def _batches(segments: list[Segment], max_chars: int) -> list[list[Segment]]:
    batches: list[list[Segment]] = [[]]
    size = 0
    for seg in segments:
        if batches[-1] and size + len(seg.text) > max_chars:
            batches.append([])
            size = 0
        batches[-1].append(seg)
        size += len(seg.text)
    return [b for b in batches if b]


def request_edits(
    provider: LLMProvider,
    instruction: str,
    segments: list[Segment],
    max_chars: int,
    progress: Progress | None = None,
) -> tuple[list[Edit], list[Change]]:
    """Ask the provider for edits batch by batch; returns valid edits and rejected changes."""
    edits: list[Edit] = []
    rejected: list[Change] = []
    batches = _batches(segments, max_chars)
    for n, batch in enumerate(batches):
        if progress:
            progress(n / len(batches), f"Model: batch {n + 1} of {len(batches)}")
        by_id = {s.id: s for s in batch}
        payload = [{"id": s.id, "text": s.text} for s in batch]
        try:
            reply = provider.complete_json(SYSTEM, edit_request(instruction, payload), EditBatch)
        except InvalidResponseError as e:
            rejected += [
                Change(
                    id=s.id,
                    old_text=s.text,
                    status=ChangeStatus.REJECTED,
                    reason="invalid_response",
                    notes=[str(e)[:200]],
                    page=s.page,
                )
                for s in batch
            ]
            continue
        latest = {}
        for e in reply.edits:
            if e.id not in by_id:
                rejected.append(
                    Change(
                        id=e.id,
                        old_text="",
                        new_text=e.new_text,
                        status=ChangeStatus.REJECTED,
                        reason="unknown_id",
                    )
                )
            elif e.new_text != by_id[e.id].text:
                latest[e.id] = e  # a repeated id keeps the model's last answer
        edits += latest.values()
    return edits, rejected


def _apply_pdf(
    writer: PdfWriter,
    edits: list[Edit],
    by_id: dict[str, Segment],
    provider: LLMProvider,
    instruction: str,
) -> list[Change]:
    """AC-5: fits -> applied; else ask to shorten, then allow shrinking to 80%, else reject."""
    changes = []
    for e in edits:
        seg = by_id[e.id]
        base = dict(id=e.id, old_text=seg.text, page=seg.page, notes=writer.notes_for(e.id))
        if writer.measure(e.id, e.new_text) == 1.0:
            writer.stage(e.id, e.new_text)
            changes.append(Change(**base, new_text=e.new_text, status=ChangeStatus.APPLIED))
            continue
        short = None
        try:
            reply = provider.complete_json(
                SYSTEM,
                shorten_request(instruction, e.id, seg.text, e.new_text, len(seg.text)),
                EditBatch,
            )
            short = next((x.new_text for x in reply.edits if x.id == e.id), None)
        except LLMError:
            pass
        options = []
        if short:
            options.append((short, ChangeStatus.SHORTENED))
        options.append((e.new_text, ChangeStatus.SHRUNK))
        for text, status in options:
            scale = writer.measure(e.id, text)
            if scale is None:
                continue
            writer.stage(e.id, text)
            if scale < 1.0:
                if status == ChangeStatus.SHORTENED:
                    base["notes"] = [*base["notes"], "shortened"]
                status = ChangeStatus.SHRUNK
                base["notes"] = [*base["notes"], f"font scaled to {scale:.0%}"]
            changes.append(Change(**base, new_text=text, status=status))
            break
        else:
            changes.append(
                Change(
                    **base, new_text=e.new_text, status=ChangeStatus.REJECTED, reason="does_not_fit"
                )
            )
    return changes


def normalise_input(src: Path, work_dir: Path, settings: Settings) -> Path:
    ext = src.suffix.lower()
    if ext not in SUPPORTED:
        raise DocumentError(f"unsupported file type {ext!r}; use .docx, .doc or .pdf")
    if src.stat().st_size > settings.max_upload_mb * 1024 * 1024:
        raise DocumentError(f"file is larger than {settings.max_upload_mb} MB")
    if ext == ".doc":
        return convert(src, "docx", work_dir)
    return src


def edit_document(
    src: Path,
    instruction: str,
    provider: LLMProvider,
    out_dir: Path,
    track_changes: bool = True,
    progress: Progress | None = None,
    settings: Settings | None = None,
    convert_to: str | None = None,
) -> EditResult:
    s = settings or get_settings()
    started = time.monotonic()
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = normalise_input(src, out_dir, s)
    is_pdf = doc_path.suffix.lower() == ".pdf"
    output = out_dir / f"{src.stem}.edited{doc_path.suffix.lower()}"

    if is_pdf:
        doc = read_pdf(doc_path)
        if doc.doc.page_count > s.max_pages:
            raise DocumentError(f"document has more than {s.max_pages} pages")
    else:
        doc = read_docx(doc_path)
    segments = doc.segments
    editable = [x for x in segments if x.editable]
    report = ChangeReport(
        source_name=src.name,
        output_name=output.name,
        instruction=instruction,
        provider=provider.key,
        model=provider.model,
        track_changes=None if is_pdf else track_changes,
        segments_total=len(segments),
        segments_sent=len(editable),
    )
    report.changes += [
        Change(
            id=x.id, old_text=x.text, status=ChangeStatus.SKIPPED, reason=x.skip_reason, page=x.page
        )
        for x in segments
        if not x.editable and x.skip_reason != "fallback_copy"
    ]

    edits, rejected = request_edits(provider, instruction, editable, s.batch_chars, progress)
    report.changes += rejected
    if progress:
        progress(0.9, "Writing the document")
    by_id = {x.id: x for x in segments}
    if is_pdf:
        writer = PdfWriter(doc)
        report.changes += _apply_pdf(writer, edits, by_id, provider, instruction)
        writer.apply()
        writer.save(output)
    else:
        report.changes += apply_edits(doc, edits, track_changes)
        doc.save(output)

    if progress:
        progress(0.95, "Checking the structure")
    landed = {
        c.id: c.new_text
        for c in report.changes
        if c.status in (ChangeStatus.APPLIED, ChangeStatus.SHORTENED, ChangeStatus.SHRUNK)
    }
    report.violations = (
        check_pdf(doc_path, output, landed)
        if is_pdf
        else check_docx(doc_path, output, landed, track_changes)
    )
    order = {seg_id: i for i, seg_id in enumerate(by_id)}
    report.changes.sort(key=lambda c: order.get(c.id, len(order)))
    conv = None
    if convert_to:
        if progress:
            progress(0.97, f"Converting to {convert_to.upper()} and checking the layout")
        conv = convert_output(output, convert_to, out_dir, s.layout_tolerance_pt)
        report.conversion = conv.gate.model_dump() | {"file": conv.path.name}
    report.duration_s = time.monotonic() - started
    rj, rh = out_dir / "report.json", out_dir / "report.html"
    write_json(report, rj)
    write_html(report, rh)
    if progress:
        progress(1.0, "Done")
    return EditResult(
        output=output,
        report=report,
        report_json=rj,
        report_html=rh,
        converted=conv.path if conv else None,
        gate=conv.gate if conv else None,
    )
