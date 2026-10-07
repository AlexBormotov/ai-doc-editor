import pytest
from fastapi.testclient import TestClient

from ai_doc_reader import api
from ai_doc_reader.llm.scripted import ScriptedProvider


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    api.get_settings.cache_clear()
    monkeypatch.setattr(
        api, "get_provider", lambda key, model: ScriptedProvider([("Acme Corp", "Contoso Ltd")])
    )
    yield TestClient(api.app)
    api.get_settings.cache_clear()


def test_health_and_providers(client):
    assert client.get("/health").json()["status"] == "ok"
    data = client.get("/api/providers").json()
    assert "ollama" in data["providers"] and "proofread" in data["presets"]


def test_edit_docx_and_download(client, fixtures):
    with (fixtures / "report_en.docx").open("rb") as f:
        resp = client.post(
            "/api/edit",
            files={"file": ("report_en.docx", f)},
            data={"instruction": "Replace Acme Corp with Contoso Ltd", "track_changes": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["structure_verified"] is True
    assert body["result"].endswith("report_en.edited.docx")
    file = client.get(body["result"])
    assert file.status_code == 200 and file.content[:2] == b"PK"
    assert client.get(body["report_html"]).status_code == 200


def test_rejects_bad_type_and_path_traversal(client):
    resp = client.post("/api/edit", files={"file": ("x.txt", b"hi")}, data={"preset": "proofread"})
    assert resp.status_code == 415
    assert client.get("/api/files/abcdef012345/../../secret").status_code == 404
    assert client.get("/api/files/not-a-run/x").status_code == 404


def test_missing_instruction_is_422(client, fixtures):
    with (fixtures / "layout.pdf").open("rb") as f:
        resp = client.post("/api/edit", files={"file": ("layout.pdf", f)}, data={})
    assert resp.status_code == 422
