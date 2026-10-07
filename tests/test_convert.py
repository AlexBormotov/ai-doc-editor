import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from ai_doc_editor.convert import layout_gate
from ai_doc_editor.editor import edit_document
from ai_doc_editor.llm.scripted import ScriptedProvider

RULES = [("Acme", "Contoso")]


def _font_installed(name: str) -> bool:
    if sys.platform == "win32":
        return any(Path("C:/Windows/Fonts").glob(f"{name.lower()}*"))
    if shutil.which("fc-list"):
        out = subprocess.run(["fc-list"], capture_output=True, text=True).stdout
        return name.lower() in out.lower()
    return False


def test_gate_passes_identical_and_flags_moved_text(fixtures, tmp_path):
    src = fixtures / "layout.pdf"
    assert layout_gate(src, src, 5, "pdf").passed

    doc = pymupdf.open(str(src))
    page = doc[0]
    words = [w for w in page.get_text("words") if w[4] == "Left"]
    x0, y0, x1, y1 = words[0][:4]
    page.add_redact_annot(pymupdf.Rect(x0, y0, x1, y1), fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    page.insert_text((x0 + 20, y1 - 2), "Left", fontsize=10)
    moved = tmp_path / "moved.pdf"
    doc.save(str(moved))
    gate = layout_gate(src, moved, 5, "pdf")
    assert not gate.passed
    assert any("'Left' moved" in f for f in gate.failures)


@pytest.mark.soffice
@pytest.mark.skipif(
    not _font_installed("Cambria"),
    reason="the fixture uses Cambria; with a substitute font the gate correctly fails",
)
def test_pdf_to_docx_passes_gate_on_simple_document(fixtures, tmp_path):
    result = edit_document(
        fixtures / "contract_ru.pdf", "x", ScriptedProvider(RULES), tmp_path, convert_to="docx"
    )
    assert result.gate.passed, result.gate.failures
    assert result.converted.suffix == ".docx"
    assert "LAYOUT-NOT-VERIFIED" not in result.converted.name


@pytest.mark.soffice
def test_pdf_to_docx_failing_gate_is_marked_not_presented(fixtures, tmp_path):
    result = edit_document(
        fixtures / "layout.pdf", "x", ScriptedProvider(RULES), tmp_path, convert_to="docx"
    )
    assert not result.gate.passed
    assert "LAYOUT-NOT-VERIFIED" in result.converted.name
    assert result.report.conversion["passed"] is False


@pytest.mark.soffice
def test_docx_to_pdf_uses_reference_renderer(fixtures, tmp_path):
    result = edit_document(
        fixtures / "report_en.docx", "x", ScriptedProvider(RULES), tmp_path, convert_to="pdf"
    )
    assert result.gate.passed and result.gate.note
    assert pymupdf.open(str(result.converted)).page_count == 2
