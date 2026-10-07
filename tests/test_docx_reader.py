from ai_doc_reader.docx.reader import read_docx


def test_report_segments_cover_body_tables_headers_textbox(fixtures):
    doc = read_docx(fixtures / "report_en.docx")
    texts = {s.text for s in doc.segments}
    assert "Quarterly Report for Acme Corp" in texts
    assert "Acme Corp - Quarterly Report" in texts  # header
    assert "Acme North" in texts  # table cell
    assert "Note: figures are unaudited and provided by Acme Corp." in texts  # text box
    assert any(t.startswith("This report was prepared by Acme Corp") for t in texts)


def test_mixed_run_paragraph_text_includes_hyperlink(fixtures):
    doc = read_docx(fixtures / "report_en.docx")
    seg = next(s for s in doc.segments if s.text.startswith("This report"))
    assert "the investor site." in seg.text
    assert seg.editable


def test_field_paragraph_is_skipped(fixtures):
    doc = read_docx(fixtures / "report_en.docx")
    footer = [s for s in doc.segments if s.id.startswith("footer")]
    assert footer and all(s.skip_reason == "field" for s in footer)


def test_ids_unique_and_stable(fixtures):
    a = read_docx(fixtures / "report_en.docx")
    b = read_docx(fixtures / "report_en.docx")
    ids = [s.id for s in a.segments]
    assert len(ids) == len(set(ids))
    assert ids == [s.id for s in b.segments]
    assert ids[0].startswith("document/p/")


def test_russian_contract(fixtures):
    doc = read_docx(fixtures / "contract_ru.docx")
    assert any("ivanov@romashka.example" in s.text for s in doc.segments)
    assert any(s.id.startswith("header") for s in doc.segments)
