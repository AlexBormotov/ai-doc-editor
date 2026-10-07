import pymupdf
import pytest

from ai_doc_reader.invariants import check_pdf
from ai_doc_reader.pdf.reader import read_pdf
from ai_doc_reader.pdf.writer import MIN_SCALE, PdfWriter


def _seg(doc, prefix):
    return next(s for s in doc.segments if s.text.startswith(prefix))


# -- reader -------------------------------------------------------------------------------


def test_reader_splits_headings_lists_and_table_cells(fixtures):
    doc = read_pdf(fixtures / "report_en.pdf")
    texts = [s.text for s in doc.segments]
    assert "Quarterly Report for Acme Corp" in texts  # heading not merged with the paragraph
    assert "Acme Corp opened two new offices." in texts  # list item without its bullet
    assert "Elect the new auditor." in texts  # numbered item without "2."
    assert "Acme North" in texts and "North" in texts  # table cells stay separate
    assert not any(t.startswith("") or t[:3] in ("1. ", "2. ", "3. ") for t in texts)


def test_reader_joins_wrapped_lines_and_infers_alignment(fixtures):
    doc = read_pdf(fixtures / "layout.pdf")
    title = _seg(doc, "Acme Corp Service")
    body = _seg(doc, "This agreement")
    assert doc.layout[title.id].align == "center"
    assert len(doc.layout[body.id].lines) == 2
    assert "Client. Acme Corp will provide support services" in body.text


def test_free_space_stops_at_neighbours_and_cell_borders(fixtures):
    doc = read_pdf(fixtures / "layout.pdf")
    left = doc.layout[_seg(doc, "Left column").id]
    right = doc.layout[_seg(doc, "Правая").id]
    assert left.avail.x1 < right.rect.x0  # never grows into the other column
    contact = doc.layout[_seg(doc, "Contact").id]
    assert contact.avail.x1 <= 523  # stays inside the shaded box


# -- writer -------------------------------------------------------------------------------

EDITS = {
    "layout.pdf": {
        "Acme Corp Service": "Contoso Ltd Service Agreement",
        "This agreement": (
            "This agreement is made between Contoso Ltd and the Client. Contoso Ltd will "
            "provide support services during business hours."
        ),
        "Правая": "Правая колонка. Оплата производится в течение пятнадцати дней.",
        "Contact": "Contact: support@contoso.example, phone +1 555 0199.",
    },
    "report_en.pdf": {
        "Quarterly Report for": "Quarterly Report for Contoso Ltd",
        "We recieve": (
            "We receive many questions about the merger, and we believe the answers below "
            "address the most common ones."
        ),
        "Acme North": "Contoso North",
        "Acme Corp opened": "Contoso Ltd opened two new offices.",
    },
    "contract_ru.pdf": {
        "Контактное лицо Поставщика": (
            "Контактное лицо Поставщика: [ФИО], тел. [ТЕЛЕФОН], e-mail: [EMAIL]."
        ),
        "Поставщик обязуется": (
            "Поставщик обязуется передать товар в сроки, указанные в Приложении 1, "
            "а Покупатель обязуется принять и оплатить товар."
        ),
    },
}


@pytest.mark.parametrize("name", sorted(EDITS))
def test_edits_preserve_layout(fixtures, tmp_path, name):
    src = fixtures / name
    doc = read_pdf(src)
    writer = PdfWriter(doc)
    expected = {}
    for prefix, new_text in EDITS[name].items():
        seg = _seg(doc, prefix)
        assert writer.stage(seg.id, new_text) is not None, prefix
        expected[seg.id] = new_text
    writer.apply()
    out = tmp_path / name
    writer.save(out)
    assert check_pdf(src, out, expected) == []


def test_too_long_text_is_refused_not_moved(fixtures):
    doc = read_pdf(fixtures / "layout.pdf")
    writer = PdfWriter(doc)
    seg = _seg(doc, "Contact")
    assert writer.measure(seg.id, "word " * 200) is None
    assert writer.stage(seg.id, "word " * 200) is None
    assert seg.id not in writer.pending


def test_slightly_long_text_is_shrunk_within_limit(fixtures):
    doc = read_pdf(fixtures / "layout.pdf")
    writer = PdfWriter(doc)
    seg = _seg(doc, "Contact")
    longer = "Contact: customer-support@contoso.example, phone +1 555 0199, ext. 12345."
    scale = writer.measure(seg.id, longer)
    assert scale is not None and MIN_SCALE <= scale < 1.0


def test_existing_fonts_are_reused_when_embedded_in_full(fixtures):
    doc = read_pdf(fixtures / "layout.pdf")
    writer = PdfWriter(doc)
    assert writer.notes_for(_seg(doc, "This agreement").id) == []
    doc2 = read_pdf(fixtures / "report_en.pdf")
    notes = PdfWriter(doc2).notes_for(_seg(doc2, "We recieve").id)
    assert notes == ["font_substituted: Cambria -> serif"]


@pytest.mark.parametrize("breakage", ["shift_untouched", "text_outside"])
def test_negative_control_layout_break_is_detected(fixtures, tmp_path, breakage):
    """Break one behaviour on purpose: the invariant check must go red."""
    src = fixtures / "layout.pdf"
    doc = read_pdf(src)
    writer = PdfWriter(doc)
    seg = _seg(doc, "Contact")
    writer.stage(seg.id, "Contact: support@contoso.example, phone +1 555 0199.")
    expected = {seg.id: "Contact: support@contoso.example, phone +1 555 0199."}
    writer.apply()
    page = doc.doc[0]
    if breakage == "shift_untouched":
        victim = doc.layout[_seg(doc, "Left column").id].lines[0].spans[0]
        page.add_redact_annot(pymupdf.Rect(victim["bbox"]), fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        x, y = victim["origin"]
        page.insert_text((x + 6, y), victim["text"], fontsize=victim["size"])
    else:
        page.insert_text((300, 600), "stray text", fontsize=10)
    out = tmp_path / "broken.pdf"
    doc.doc.save(str(out))
    assert check_pdf(src, out, expected), "invariant check missed a layout break"
