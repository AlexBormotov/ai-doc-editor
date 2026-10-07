import json
from types import SimpleNamespace

import openai
import pytest

from ai_doc_reader.llm.base import InvalidResponseError, LLMProvider, extract_json, strict_schema
from ai_doc_reader.llm.openai_compatible import OpenAICompatibleProvider
from ai_doc_reader.llm.prompts import SYSTEM, edit_request, parse_segments
from ai_doc_reader.llm.registry import get_provider
from ai_doc_reader.llm.scripted import ScriptedProvider
from ai_doc_reader.models import EditBatch


class Replies(LLMProvider):
    key = "fake"

    def __init__(self, replies):
        super().__init__("m")
        self.replies = list(replies)
        self.prompts = []

    def complete_text(self, system, user, schema):
        self.prompts.append(user)
        return self.replies.pop(0)


def test_extract_json_strips_fences_and_prose():
    assert extract_json('```json\n{"edits": []}\n```') == '{"edits": []}'
    assert extract_json('Sure! {"edits": []} done') == '{"edits": []}'
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_strict_schema_inlines_refs_and_closes_objects():
    s = strict_schema(EditBatch)
    assert "$defs" not in json.dumps(s)
    item = s["properties"]["edits"]["items"]
    assert item["additionalProperties"] is False
    assert item["required"] == ["id", "new_text"]


def test_invalid_reply_is_retried_once_with_the_error():
    p = Replies(["not json", '{"edits": [{"id": "a", "new_text": "b"}]}'])
    batch = p.complete_json(SYSTEM, edit_request("x", [{"id": "a", "text": "c"}]), EditBatch)
    assert batch.edits[0].new_text == "b"
    assert "previous reply was not valid" in p.prompts[1]


def test_invalid_twice_raises():
    p = Replies(["nope", '{"edits": "wrong"}'])
    with pytest.raises(InvalidResponseError):
        p.complete_json(SYSTEM, "u", EditBatch)


def test_scripted_provider_returns_only_changed_segments():
    p = ScriptedProvider(rules=[("Acme Corp", "Contoso Ltd")])
    segs = [{"id": "1", "text": "Acme Corp is here"}, {"id": "2", "text": "nothing"}]
    batch = p.complete_json(SYSTEM, edit_request("replace", segs), EditBatch)
    assert [(e.id, e.new_text) for e in batch.edits] == [("1", "Contoso Ltd is here")]


def test_request_round_trips_segments():
    segs = [{"id": "p0/s1", "text": "Привет «мир»"}]
    assert parse_segments(edit_request("do", segs)) == segs


def test_openai_compatible_falls_back_when_structured_output_unsupported(monkeypatch):
    p = OpenAICompatibleProvider("lmstudio", "m", "http://localhost:1/v1", "", 5)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if "response_format" in kwargs:
            req = SimpleNamespace(method="POST", url="u", headers={})
            resp = SimpleNamespace(status_code=400, headers={}, request=req, text="")
            raise openai.BadRequestError("response_format not supported", response=resp, body=None)
        msg = SimpleNamespace(content='{"edits": []}')
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(p.client.chat.completions, "create", create)
    assert p.complete_json(SYSTEM, "u", EditBatch).edits == []
    assert "response_format" not in calls[-1]


def test_registry_knows_every_provider():
    for key in ["ollama", "lmstudio", "openai", "anthropic", "google", "cli:claude"]:
        assert get_provider(key, "m").key == key


@pytest.mark.live
def test_live_ollama_edit():
    p = get_provider("ollama", "qwen3.5:4b")
    segs = [{"id": "s1", "text": "We recieve many questions."}, {"id": "s2", "text": "Fine."}]
    batch = p.complete_json(SYSTEM, edit_request("Fix spelling mistakes.", segs), EditBatch)
    assert [e.id for e in batch.edits] == ["s1"]
    assert "receive" in batch.edits[0].new_text


@pytest.mark.live
@pytest.mark.parametrize("cli,model", [("claude", "haiku"), ("codex", ""), ("agy", "")])
def test_live_cli_edit(cli, model):
    p = get_provider(f"cli:{cli}", model)
    segs = [{"id": "s1", "text": "Acme Corp signs."}]
    batch = p.complete_json(
        SYSTEM, edit_request("Replace Acme Corp with Contoso.", segs), EditBatch
    )
    assert batch.edits and "Contoso" in batch.edits[0].new_text
