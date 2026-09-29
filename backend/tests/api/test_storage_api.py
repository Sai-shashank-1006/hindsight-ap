"""The API with its data in a database (SQLite here, MySQL in production), the paged queue and
its summary, and the data source in /health."""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import api
from app import storage
from app.storage import database
from tests.conftest import body

PROCESS, STORE = "/api/v1/invoice/process", "/api/v1/invoice/store-decision"
REASON = "Contract price changed from ₹500 to ₹550 effective 2026-07-01"


def reset_api():
    api.get_settings.cache_clear()
    api._reference.cache_clear()
    api._decision_log = None
    storage.dispose_engines()


@pytest.fixture
def db_client(tmp_path, monkeypatch, fake_hindsight, fake_groq):
    """The real storage (no decision-log override), in a SQLite file."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'paysage.db').as_posix()}")
    reset_api()
    api.app.dependency_overrides[api.get_hindsight_client] = lambda: fake_hindsight
    api.app.dependency_overrides[api.get_groq_client] = lambda: fake_groq
    with TestClient(api.app) as client:
        yield client
    api.app.dependency_overrides.clear()
    reset_api()


def test_decisions_in_the_database_survive_a_restart(db_client):
    db_client.post(PROCESS, json=body())
    assert db_client.post(STORE, json={"invoice_id": "INV001", "human_decision": "APPROVED",
                                       "human_reason": REASON}).json()["retained"] is True
    before = db_client.get("/api/v1/dashboard/stats").json()

    api._decision_log = None  # a restart: the log is replayed from the database
    api._reference.cache_clear()
    after = db_client.get("/api/v1/dashboard/stats").json()
    assert after == before and (after["total_decisions"], after["memories_retained"]) == (1, 1)
    assert db_client.get("/api/v1/invoices", params={"limit": 1}).json()[0]["status"] == "decided"

    engine = storage.engine_for(api.get_settings().database_url)
    with engine.connect() as conn:
        rows = conn.execute(sa.select(database.decision_events.c.kind, database.decision_events.c.scope)).all()
    assert rows == [("processed", "fixtures|hap-unit"), ("decided", "fixtures|hap-unit")]


def test_health_names_the_data_source(db_client):
    health = db_client.get("/health").json()
    assert (health["data_source"], health["dataset"], health["database"]) == ("sqlite", "fixtures", "connected")


def test_an_unreachable_database_is_a_503_that_says_why(monkeypatch, fake_hindsight):
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "TEST_SECRET_pw")
    monkeypatch.setenv("MYSQL_PORT", "1")
    reset_api()
    api.app.dependency_overrides[api.get_hindsight_client] = lambda: fake_hindsight
    try:
        with TestClient(api.app) as client:
            response = client.get("/api/v1/invoices")
            assert response.status_code == 503
            error = response.json()["error"]
            assert error["code"] == "database_unavailable"
            assert "127.0.0.1:1/paysage" in error["message"] and "TEST_SECRET" not in response.text
            health = client.get("/health").json()
            assert (health["data_source"], health["database"]) == ("mysql", "unreachable")
            assert "TEST_SECRET" not in client.get("/health").text
    finally:
        api.app.dependency_overrides.clear()
        reset_api()


# ── the paged queue and its summary (files) ─────────────────────────────────

def test_the_queue_pages_with_offset(client):
    ids = lambda **params: [i["invoice_id"] for i in client.get("/api/v1/invoices", params=params).json()]  # noqa: E731
    assert ids(limit=2) == ["INV001", "INV002"]
    assert ids(limit=2, offset=2) == ["INV003", "INV004"]
    assert ids(limit=2, offset=4) == ["INV005"]
    assert ids(limit=2, offset=10) == []
    assert client.get("/api/v1/invoices", params={"offset": -1}).status_code == 422


def test_the_queue_summary_counts_every_invoice(client):
    assert client.get("/api/v1/queue/summary").json() == {"total": 5, "pending": 5, "processed": 0, "decided": 0,
                                                          "first_open": 0}
    client.post(PROCESS, json=body())
    client.post(PROCESS, json=body("INV002"))
    client.post(STORE, json={"invoice_id": "INV001", "human_decision": "APPROVED", "human_reason": REASON})
    assert client.get("/api/v1/queue/summary").json() == {"total": 5, "pending": 3, "processed": 1, "decided": 1,
                                                          "first_open": 1}


def test_the_summary_when_everything_is_decided(client):
    for invoice in client.get("/api/v1/invoices", params={"limit": 50}).json():
        client.post(PROCESS, json={k: v for k, v in invoice.items() if k != "status"})
        client.post(STORE, json={"invoice_id": invoice["invoice_id"], "human_decision": "NEEDS_REVIEW",
                                 "human_reason": "Checked"})
    summary = client.get("/api/v1/queue/summary").json()
    assert (summary["decided"], summary["first_open"]) == (5, None)
