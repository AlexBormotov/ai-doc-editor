import json

import pytest

from ai_doc_reader.docx.reader import read_docx
from ai_doc_reader.editor import DocumentError, edit_document
from ai_doc_reader.llm.base import LLMProvider
from ai_doc_reader.llm.prompts import parse_segments
from ai_doc_reader.llm.scripted import ScriptedProvider
from ai_doc_reader.models import ChangeStatus
from ai_doc_reader.presets import build_instruction

RULES = [("Acme Corp", "Contoso Ltd"), ("recieve", "receive"), ("beleive", "believe")]


@pytest.mark.parametrize("name", ["report_en.docx", "contract_ru.docx"])
@pytest.mark.parametrize("track", [True, False])
def test_docx_end_to_end(fixtures, tmp_path, name, track):
    result = edit_document(
        fixtures / name, "replace", ScriptedProvider(RULES), tmp_path, track_changes=track
    )
    r = result.report
    assert result.output.exists() and result.report_html.exists()
    assert r.violations == []
    if name == "report_en.docx":
        assert r.count(ChangeStatus.APPLIED) >= 5
        assert r.count(ChangeStatus.SKIPPED) >= 1  # footer with PAGE field
    data = json.loads(result.report_json.read_text(encoding="utf-8"))
    assert data["provider"] == "scripted"


@pytest.mark.parametrize("name", ["report_en.pdf", "layout.pdf", "contract_ru.pdf"])
def test_pdf_end_to_end(fixtures, tmp_path, name):
    result = edit_document(fixtures / name, "replace", ScriptedProvider(RULES), tmp_path)
    assert result.report.violations == []
    assert result.output.suffix == ".pdf"


class Shortener(LLMProvider):
    """First call: a far too long edit. Second call (shorten request): a short one."""

    key = "fake"

    def __init__(self):
        super().__init__("m")
        self.calls = 0

    def complete_text(self, system, user, schema):
        self.calls += 1
        seg = next(s for s in parse_segments(user) if s["text"].startswith("Contact"))
        if self.calls == 1:
            text = "Contact our support team " * 20
        else:
            text = "Contact: help@contoso.example."
        return json.dumps({"edits": [{"id": seg["id"], "new_text": text}]})


def test_pdf_too_long_edit_is_shortened_by_second_call(fixtures, tmp_path):
    provider = Shortener()
    result = edit_document(fixtures / "layout.pdf", "x", provider, tmp_path)
    change = next(c for c in result.report.changes if c.old_text.startswith("Contact"))
    assert change.status == ChangeStatus.SHORTENED
    assert change.new_text == "Contact: help@contoso.example."
    assert provider.calls == 2
    assert result.report.violations == []


def test_invalid_response_rejects_batch_and_leaves_document_unchanged(fixtures, tmp_path):
    result = edit_document(
        fixtures / "report_en.docx", "x", ScriptedProvider(raw_reply="garbage"), tmp_path
    )
    statuses = {c.status for c in result.report.changes}
    assert ChangeStatus.REJECTED in statuses and ChangeStatus.APPLIED not in statuses
    assert all(c.reason in ("invalid_response", "field") for c in result.report.changes)
    assert result.report.violations == []


def test_unsupported_input_is_refused(tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("hi")
    with pytest.raises(DocumentError):
        edit_document(bad, "x", ScriptedProvider(), tmp_path / "out")


def test_presets_combine_with_instruction():
    text = build_instruction("proofread", "Use British spelling.")
    assert text.startswith("Fix spelling") and text.endswith("Use British spelling.")
    with pytest.raises(ValueError):
        build_instruction(None, " ")


@pytest.mark.soffice
def test_legacy_doc_is_converted_on_input(fixtures, tmp_path):
    result = edit_document(fixtures / "contract_ru.doc", "x", ScriptedProvider(RULES), tmp_path)
    assert result.output.suffix == ".docx"
    assert result.report.violations == []


def test_emptied_segment_is_rejected_not_applied(fixtures, tmp_path):
    """Regression: a model 'merges' a line into its neighbour by emptying it."""

    class Emptier(LLMProvider):
        key = "fake"

        def __init__(self):
            super().__init__("m")

        def complete_text(self, system, user, schema):
            seg = next(s for s in parse_segments(user) if s["text"].startswith("Contact"))
            return json.dumps({"edits": [{"id": seg["id"], "new_text": "  "}]})

    result = edit_document(fixtures / "layout.pdf", "x", Emptier(), tmp_path)
    change = next(c for c in result.report.changes if c.old_text.startswith("Contact"))
    assert (change.status, change.reason) == (ChangeStatus.REJECTED, "emptied")
    assert result.report.violations == []


class ScopeThenScripted(LLMProvider):
    """First call answers the scope request, later calls behave like ScriptedProvider."""

    key = "fake"

    def __init__(self, scope_reply):
        super().__init__("m")
        self.scope_reply = scope_reply
        self.inner = ScriptedProvider([("Acme Corp", "Contoso Ltd")])
        self.edit_batches = []

    def complete_text(self, system, user, schema):
        if "OUTLINE:" in user:
            return json.dumps(self.scope_reply)
        self.edit_batches.append([s["id"] for s in parse_segments(user)])
        return self.inner.complete_text(system, user, schema)


def test_targeted_instruction_edits_only_the_chosen_segments(fixtures, tmp_path):
    doc_ids = [s.id for s in read_docx(fixtures / "report_en.docx").segments if s.editable]
    target = doc_ids[2]
    provider = ScopeThenScripted({"scope": "ids", "ids": [target, "made/up/1"]})
    result = edit_document(
        fixtures / "report_en.docx", "x", provider, tmp_path, scope_from="the first paragraph"
    )
    assert result.report.scope == [target]  # the invented id is dropped
    assert provider.edit_batches == [[target]]
    assert result.report.violations == []


def test_scope_all_or_failure_means_whole_document(fixtures, tmp_path):
    provider = ScopeThenScripted({"scope": "all", "ids": []})
    result = edit_document(
        fixtures / "report_en.docx", "x", provider, tmp_path, scope_from="replace everywhere"
    )
    assert result.report.scope is None
    assert sum(len(b) for b in provider.edit_batches) > 10

    provider = ScopeThenScripted({"scope": "ids", "ids": ["nope"]})
    result = edit_document(
        fixtures / "report_en.docx", "x", provider, tmp_path / "2", scope_from="x"
    )
    assert result.report.scope is None
