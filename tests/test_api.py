"""API: practice list, review decisions, export gating, smoke endpoint."""
import pytest
from fastapi.testclient import TestClient

from onboarding import app as app_module
from onboarding.review import ReviewStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(app_module, "store", ReviewStore(tmp_path / "review.sqlite"))
    app_module.cached_analysis.cache_clear()
    return TestClient(app_module.app)


def test_index_and_practices(client):
    assert "Onboarding" in client.get("/").text
    cards = client.get("/api/practices").json()
    assert [c["id"] for c in cards] == ["p01", "p02", "p03", "p04", "p05", "p06"]
    assert {c["status"] for c in cards} == {"draft", "ready"}


def test_practice_detail_has_sources_for_every_row(client):
    data = client.get("/api/practices/p01").json()
    assert set(data["files"]) == {"hours.txt", "providers.csv", "call_script.md", "faq.md", "protocols.md"}
    assert all(r["source"] for r in data["rows"])
    assert data["checker"] == "mock"


def test_unknown_practice_and_issue(client):
    assert client.get("/api/practices/p99").status_code == 404
    assert client.post("/api/practices/p01/issues/nope", json={"action": "reject"}).status_code == 404


def test_export_blocked_then_allowed(client):
    assert client.get("/api/practices/p02/export").status_code == 409
    issues = client.get("/api/practices/p02").json()["issues"]
    rf = next(i for i in issues if i["type"] == "red_flag_no_escalation")
    ah = next(i for i in issues if i["type"] == "missing_after_hours")

    # Nothing to accept for after-hours: the reviewer has to supply the value.
    assert client.post(f"/api/practices/p02/issues/{ah['id']}", json={"action": "accept"}).status_code == 422
    client.post(f"/api/practices/p02/issues/{rf['id']}", json={"action": "accept"})
    data = client.post(f"/api/practices/p02/issues/{ah['id']}",
                       json={"action": "edit", "value": "Calls forward to the on-call line at (555) 555-0158."}).json()
    assert data["can_export"] and data["status"] == "needs review"

    resp = client.get("/api/practices/p02/export")
    assert resp.status_code == 200 and resp.json()["timezone"]["value"] == "America/Phoenix"

    assert client.get("/api/practices/p02/smoke").json()["passed"] == 10
    assert client.post("/api/practices/p02/reset").json()["status"] == "draft"
