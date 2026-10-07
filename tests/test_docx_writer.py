import zipfile

import pytest
from lxml import etree

from ai_doc_reader.docx.reader import paragraph_text, q, read_docx
from ai_doc_reader.docx.writer import apply_edits, diff_ops
from ai_doc_reader.invariants import check_docx, rejected_text
from ai_doc_reader.models import ChangeStatus, Edit


def _edits_for(doc):
    by_text = {s.text: s for s in doc.segments}
    intro = next(s for s in doc.segments if s.text.startswith("This report"))
    typo = next(s for s in doc.segments if s.text.startswith("We recieve"))
    return {
        intro.id: intro.text.replace("Acme Corp", "Contoso Ltd").replace("strongly", "sharply"),
        typo.id: typo.text.replace("recieve", "receive")
        .replace("beleive", "believe")
        .replace("adress", "address"),
        by_text["Acme Corp - Quarterly Report"].id: "Contoso Ltd - Quarterly Report",
        by_text["Acme North"].id: "Contoso North",
        by_text["Note: figures are unaudited and provided by Acme Corp."].id: (
            "Note: figures are unaudited and provided by Contoso Ltd."
        ),
    }


@pytest.mark.parametrize("tracked", [True, False])
def test_edits_preserve_structure(fixtures, tmp_path, tracked):
    src = fixtures / "report_en.docx"
    doc = read_docx(src)
    expected = _edits_for(doc)
    changes = apply_edits(doc, [Edit(id=k, new_text=v) for k, v in expected.items()], tracked)
    assert all(c.status == ChangeStatus.APPLIED for c in changes)
    out = tmp_path / "out.docx"
    doc.save(out)
    assert check_docx(src, out, expected, tracked) == []


def test_replacement_inherits_formatting_of_replaced_text(fixtures, tmp_path):
    doc = read_docx(fixtures / "report_en.docx")
    intro = next(s for s in doc.segments if s.text.startswith("This report"))
    apply_edits(doc, [Edit(id=intro.id, new_text=intro.text.replace("Acme Corp", "Contoso"))])
    p = doc.paragraphs[intro.id]
    ins_runs = p.findall(f".//{q('w:ins')}/{q('w:r')}")
    assert len(ins_runs) == 1
    assert ins_runs[0].find(f"{q('w:rPr')}/{q('w:b')}") is not None
    assert ins_runs[0].getparent().get(q("w:author")) == "AI Doc Reader"
    assert paragraph_text(p).startswith("This report was prepared by Contoso for")
    assert rejected_text(p) == intro.text


def test_skipped_unknown_and_split_are_reported(fixtures):
    doc = read_docx(fixtures / "report_en.docx")
    footer = next(s for s in doc.segments if s.id.startswith("footer"))
    body = next(s for s in doc.segments if s.editable)
    changes = apply_edits(
        doc,
        [
            Edit(id="document/p/99999", new_text="x"),
            Edit(id=footer.id, new_text="Seite 1"),
            Edit(id=body.id, new_text="one\ntwo"),
        ],
    )
    assert [(c.status, c.reason) for c in changes] == [
        (ChangeStatus.REJECTED, "unknown_id"),
        (ChangeStatus.SKIPPED, "field"),
        (ChangeStatus.REJECTED, "paragraph_split"),
    ]


def test_diff_ops_are_token_level():
    assert diff_ops("the cat sat", "the dog sat") == [(4, 7, "dog")]
    assert diff_ops("abc", "abc") == []
    assert diff_ops("by Acme Corp for", "by Contoso Ltd for") == [(3, 12, "Contoso Ltd")]


def _rewrite_document_xml(path, mutate):
    with zipfile.ZipFile(path) as z:
        items = {n: z.read(n) for n in z.namelist()}
    root = etree.fromstring(items["word/document.xml"])
    mutate(root)
    items["word/document.xml"] = etree.tostring(root, xml_declaration=True, standalone=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in items.items():
            z.writestr(n, data)


@pytest.mark.parametrize("target", ["unedited", "edited"])
def test_negative_control_formatting_change_is_detected(fixtures, tmp_path, target):
    """Break one behaviour on purpose: the invariant check must go red."""
    src = fixtures / "report_en.docx"
    doc = read_docx(src)
    expected = _edits_for(doc)
    apply_edits(doc, [Edit(id=k, new_text=v) for k, v in expected.items()], True)
    out = tmp_path / "out.docx"
    doc.save(out)
    assert check_docx(src, out, expected, True) == []

    intro_idx = int(next(k for k in expected if k.startswith("document")).split("/")[-1])

    def mutate(root):
        ps = list(root.iter(q("w:p")))
        if target == "edited":
            p = ps[intro_idx]
            run = next(r for r in p.iter(q("w:r")) if r.find(q("w:t")) is not None)
        else:
            p = next(p for i, p in enumerate(ps) if i != intro_idx and p.find(q("w:r")) is not None)
            run = p.find(q("w:r"))
        rpr = run.find(q("w:rPr"))
        if rpr is None:
            rpr = etree.SubElement(run, q("w:rPr"))
            run.insert(0, rpr)
        etree.SubElement(rpr, q("w:strike"))

    _rewrite_document_xml(out, mutate)
    errors = check_docx(src, out, expected, True)
    assert errors, "invariant check missed a formatting change"


@pytest.mark.soffice
def test_tracked_output_opens_in_libreoffice(fixtures, tmp_path):
    from ai_doc_reader.soffice import convert

    doc = read_docx(fixtures / "report_en.docx")
    expected = _edits_for(doc)
    apply_edits(doc, [Edit(id=k, new_text=v) for k, v in expected.items()], True)
    out = tmp_path / "tracked.docx"
    doc.save(out)
    pdf = convert(out, "pdf", tmp_path)
    assert pdf.stat().st_size > 0


def test_full_rewrite_of_mixed_format_paragraph_passes_structure_check(fixtures, tmp_path):
    """Regression: a translation rewrites every word of a paragraph with bold runs."""
    src = fixtures / "contract_ru.docx"
    doc = read_docx(src)
    seg = next(s for s in doc.segments if s.text.startswith("ООО «Ромашка»"))
    new = (
        "JSC «Romashka», represented by its General Director Ivanov Petr Sergeevich, acting on "
        "the basis of the Charter, hereinafter the «Supplier», and JSC «Vasilek», hereinafter "
        "the «Buyer», have concluded this contract."
    )
    for tracked in (True, False):
        d = read_docx(src)
        apply_edits(d, [Edit(id=seg.id, new_text=new)], tracked)
        out = tmp_path / f"out-{tracked}.docx"
        d.save(out)
        assert check_docx(src, out, {seg.id: new}, tracked) == []
