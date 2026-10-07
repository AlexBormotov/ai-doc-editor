import pymupdf
import pytest

from ai_doc_editor.invariants import check_pdf
from ai_doc_editor.pdf.reader import read_pdf
from ai_doc_editor.pdf.writer import MIN_SCALE, PdfWriter


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
    assert check_pdf(src, out, expected, writer.moved, writer.boxes) == []


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


@pytest.mark.parametrize("breakage", ["shift_untouched", "text_outside", "hidden_colour"])
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
    elif breakage == "text_outside":
        page.insert_text((300, 600), "stray text", fontsize=10)
    else:
        writer2 = PdfWriter(read_pdf(src))
        seg2 = writer2.pdf.layout[seg.id]
        seg2.style.color = 0xFFFFFF  # white text: content hidden
        writer2.stage(seg.id, expected[seg.id])
        writer2.apply()
        doc = writer2.pdf
    out = tmp_path / "broken.pdf"
    doc.doc.save(str(out))
    assert check_pdf(src, out, expected), "invariant check missed a layout break"


def _block(text, x0, y0, x1, size=10.5, font="Body"):
    span = {
        "text": text,
        "font": font,
        "size": size,
        "color": 0,
        "flags": 4,
        "bbox": (x0, y0, x1, y0 + size * 1.07),
        "origin": (x0, y0 + size * 0.85),
    }
    return {"type": 0, "lines": [{"spans": [span], "dir": (1.0, 0.0)}]}


def test_one_line_per_block_pdfs_are_joined_into_paragraphs():
    """Regression: browser-printed PDFs emit every line as its own block."""
    from ai_doc_editor.pdf.reader import segment_lines

    blocks = [
        _block("1. About This Certification", 54, 182, 273, size=18, font="Head"),
        _block("The certification validates that an individual can design,", 54, 219, 531),
        _block("build, and deliver solutions on the platform. It is intended for", 54, 238, 541),
        _block("practitioners in an architect role.", 54, 255, 300),
        _block("This guide is the authoritative reference for candidates. It", 54, 279, 530),
        _block("describes the exam format.", 54, 296, 250),
        _block("• Design and prototype solutions", 54, 330, 400),
        _block("• Select appropriate models", 54, 347, 380),
    ]
    segs, _ = segment_lines(blocks, 0, 595)
    texts = [" ".join(ln.text for ln in seg.lines) for seg, _ in segs]
    assert texts == [
        "1. About This Certification",
        "The certification validates that an individual can design, build, and deliver "
        "solutions on the platform. It is intended for practitioners in an architect role.",
        "This guide is the authoritative reference for candidates. It describes the exam format.",
        "• Design and prototype solutions",
        "• Select appropriate models",
    ]


# -- reflow inside a section ---------------------------------------------------------------

LONGER = (
    "The certification confirms that a person can design, build and deliver production-grade "
    "AI solutions from the first prototype to a system that runs every day. It is meant for "
    "practitioners in an architect role who choose models, connect them to enterprise systems, "
    "and take responsibility for evaluation, security and governance of what they ship."
)
SHORTER = "The certification shows that a person can build production AI systems."


def _reflow(fixtures, tmp_path, text):
    src = fixtures / "sections.pdf"
    doc = read_pdf(src)
    writer = PdfWriter(doc)
    scale = writer.stage("p0/s1", text)
    writer.apply()
    out = tmp_path / "out.pdf"
    writer.save(out)
    return src, out, writer, scale


def _line_tops(path, prefix):
    page = pymupdf.open(str(path))[0]
    return [
        round(ln["bbox"][1], 1)
        for b in page.get_text("dict")["blocks"]
        for ln in b.get("lines", [])
        if "".join(s["text"] for s in ln["spans"]).startswith(prefix)
    ]


def test_longer_paragraph_pushes_the_rest_of_its_section_down(fixtures, tmp_path):
    src, out, writer, scale = _reflow(fixtures, tmp_path, LONGER)
    assert scale == 1.0
    (_page, _clip, dy), *_ = writer.moved
    assert dy > 10  # the next paragraph moved down by at least one line
    assert _line_tops(out, "This guide")[0] > _line_tops(src, "This guide")[0] + 10
    assert _line_tops(out, "2. Purpose") == _line_tops(src, "2. Purpose")  # next section stays
    assert check_pdf(src, out, {"p0/s1": LONGER}, writer.moved, writer.boxes) == []


def test_shorter_paragraph_pulls_the_rest_of_its_section_up(fixtures, tmp_path):
    src, out, writer, _ = _reflow(fixtures, tmp_path, SHORTER)
    assert writer.moved and writer.moved[0][2] < -10
    assert _line_tops(out, "2. Purpose") == _line_tops(src, "2. Purpose")
    assert check_pdf(src, out, {"p0/s1": SHORTER}, writer.moved, writer.boxes) == []


def test_section_never_runs_into_the_next_heading(fixtures, tmp_path):
    doc = read_pdf(fixtures / "sections.pdf")
    writer = PdfWriter(doc)
    assert writer.measure("p0/s1", LONGER * 4) is None  # would cross "2. Purpose"


def test_moved_text_is_one_copy_only(fixtures, tmp_path):
    """The moved paragraph is drawn from a stripped copy: no hidden duplicates of other text."""
    _src, out, _w, _ = _reflow(fixtures, tmp_path, LONGER)
    raw = pymupdf.open(str(out))[0].get_text(
        flags=pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_MEDIABOX_CLIP
    )
    assert raw.count("2. Purpose of the Credential") == 1
    assert raw.count("Read it in full before scheduling your exam.") == 1


@pytest.mark.parametrize("breakage", ["wrong_dy", "undeclared_move"])
def test_negative_control_reflow_errors_are_detected(fixtures, tmp_path, breakage):
    src, out, writer, _ = _reflow(fixtures, tmp_path, LONGER)
    moved = list(writer.moved)
    if breakage == "wrong_dy":
        moved = [(p, clip, dy + 6) for p, clip, dy in moved]
    else:
        moved = []
    assert check_pdf(src, out, {"p0/s1": LONGER}, moved, writer.boxes)
