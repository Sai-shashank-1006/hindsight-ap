"""HTTP behaviour: validation, decisions, the queue, dashboards, health, CORS, errors and logs."""

import logging

import pytest
from fastapi.testclient import TestClient

import api
from app.models import PurchaseOrder
from tests.conftest import body
from tests.fakes import llm_json

REASON = "Contract price changed from ₹500 to ₹550 effective 2026-07-01"
PROCESS, STORE = "/api/v1/invoice/process", "/api/v1/invoice/store-decision"


def decide(client, invoice_id="INV001", decision="APPROVED", reason=REASON):
    return client.post(STORE, json={"invoice_id": invoice_id, "human_decision": decision, "human_reason": reason})


# ── /invoice/process ─────────────────────────────────────────────────────────

def test_process_returns_the_recommendation(client):
    data = client.post(PROCESS, json=body()).json()
    assert data["exception_detected"]["type"] == "PRICE_MISMATCH"
    assert (data["recommendation"], data["memory_status"], data["evidence_level"]) == ("NEEDS_REVIEW", "ok", "NO_EVIDENCE")


@pytest.mark.parametrize("change", [
    {"vendor": None}, {"invoice_price": -5}, {"quantity": 0}, {"invoice_price": "abc"},
    {"invoice_date": "28/09/2026"}, {"invoice_id": ""},
])
def test_invalid_invoices_are_422_never_500(client, change):
    payload = {**body(), **change}
    if change.get("vendor", "") is None:
        del payload["vendor"]
    response = client.post(PROCESS, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_quoted_po_price_that_disagrees_is_logged_and_ignored(client, caplog):
    with caplog.at_level(logging.INFO, "paysage"):
        data = client.post(PROCESS, json=body(po_price=550)).json()
    assert data["exception_detected"]["expected_value"] == 500
    assert "the PO record wins" in caplog.text


def test_unknown_vendor_is_404_naming_it(client):
    response = client.post(PROCESS, json=body(vendor="Nobody Pharma"))
    assert response.status_code == 404
    assert response.json()["error"] == {"code": "po_not_found",
                                         "message": "No purchase order on file for vendor 'Nobody Pharma'"}


# ── /invoice/store-decision ──────────────────────────────────────────────────

def test_store_decision(client, fake_hindsight):
    client.post(PROCESS, json=body())
    assert decide(client).json() == {"success": True, "retained": True, "memory_id": "ap-decision-INV001",
                                     "message": "Decision remembered in Hindsight as ap-decision-INV001."}
    assert len(fake_hindsight.calls_to("retain")) == 1


def test_store_decision_needs_a_processed_invoice(client):
    response = decide(client, "INV999")
    assert response.status_code == 404 and response.json()["error"]["code"] == "invoice_not_processed"


@pytest.mark.parametrize("decision, reason", [("APPROVED", ""), ("APPROVED", "   "), ("MAYBE", "fine")])
def test_store_decision_rejects_bad_input(client, decision, reason):
    client.post(PROCESS, json=body())
    assert decide(client, decision=decision, reason=reason).status_code == 422


def test_the_same_decision_twice_leaves_one_memory(client, fake_hindsight):
    client.post(PROCESS, json=body())
    assert decide(client).status_code == decide(client).status_code == 200
    assert list(fake_hindsight.documents("hap-unit")) == ["ap-decision-INV001"]
    assert client.get("/api/v1/dashboard/stats").json()["total_decisions"] == 1


def test_failed_retain_is_not_reported_as_success(client, fake_hindsight):
    client.post(PROCESS, json=body())
    fake_hindsight.fail_next(402, method="retain")
    data = decide(client).json()
    assert (data["success"], data["retained"], data["memory_id"]) == (False, False, None)
    assert "credits exhausted" in data["message"]


# ── queue ────────────────────────────────────────────────────────────────────

def test_next_and_list(client):
    assert client.get("/api/v1/invoice/next").json()["invoice_id"] == "INV001"
    client.post(PROCESS, json=body())
    assert client.get("/api/v1/invoice/next").json()["invoice_id"] == "INV002"
    listed = client.get("/api/v1/invoices", params={"limit": 3}).json()
    assert [(i["invoice_id"], i["status"]) for i in listed] == [("INV001", "processed"), ("INV002", "pending"),
                                                               ("INV003", "pending")]
    decide(client)
    assert client.get("/api/v1/invoices").json()[0]["status"] == "decided"
    assert client.get("/api/v1/invoices", params={"limit": 0}).status_code == 422


def test_next_when_the_queue_is_done(client):
    for invoice in client.get("/api/v1/invoices", params={"limit": 50}).json():
        client.post(PROCESS, json={k: v for k, v in invoice.items() if k != "status"})
    response = client.get("/api/v1/invoice/next")
    assert response.status_code == 404 and response.json()["error"]["code"] == "queue_empty"


# ── dashboard and vendors: local only ────────────────────────────────────────

def test_dashboard_and_vendors_make_no_groq_or_hindsight_calls(client, fake_hindsight, fake_groq):
    client.post(PROCESS, json=body())
    decide(client)
    client.post(PROCESS, json=body("INV003", vendor="XYZ Pharma", quantity=50))
    fake_hindsight.calls.clear()
    fake_groq.calls.clear()
    for path in ("/api/v1/dashboard", "/api/v1/dashboard/stats", "/api/v1/vendors", "/api/v1/vendor/ABC%20Pharma",
                 "/api/v1/vendor/ABC%20Pharma/timeline", "/api/v1/invoices", "/api/v1/invoice/next"):
        assert client.get(path).status_code == 200, path
    assert fake_hindsight.calls == [] and fake_groq.calls == []


def test_dashboard_numbers(client):
    client.post(PROCESS, json=body())
    decide(client)
    client.post(PROCESS, json=body("INV003", vendor="XYZ Pharma", quantity=50))
    decide(client, "INV003", "REJECTED", "No contract change on file")
    board = client.get("/api/v1/dashboard").json()
    assert (board["total_processed"], board["total_exceptions"], board["approval_rate"], board["active_vendors"]) == (2, 2, 0.5, 2)
    assert {"type": "PRICE_MISMATCH", "count": 2} in board["exception_breakdown"]
    assert [m["invoice_id"] for m in board["recent_memories"]] == ["INV003", "INV001"]
    stats = client.get("/api/v1/dashboard/stats").json()
    assert (stats["memories_retained"], stats["pending_decisions"]) == (2, 0)


def test_vendor_pages(client):
    vendors = {v["name"]: v for v in client.get("/api/v1/vendors").json()}
    assert set(vendors) == {"ABC Pharma", "XYZ Pharma"} and vendors["ABC Pharma"]["status"] == "new"
    client.post(PROCESS, json=body())
    decide(client)
    abc = client.get("/api/v1/vendor/ABC%20Pharma").json()
    assert (abc["total_decisions"], abc["approval_rate"], abc["status"]) == (1, 1.0, "reliable")
    assert abc["recent_exceptions"][0]["type"] == "PRICE_MISMATCH"
    assert client.get("/api/v1/vendor/abc%20pharma").status_code == 200  # case-insensitive
    timeline = client.get("/api/v1/vendor/ABC%20Pharma/timeline").json()
    assert [e["event"] for e in timeline] == ["processed", "decided"]
    assert client.get("/api/v1/vendor/Nobody").json()["error"]["code"] == "vendor_not_found"
    assert client.get("/api/v1/vendor/Nobody/timeline").status_code == 404


def test_inconsistent_vendor(client):
    for n, decision in enumerate(["APPROVED", "REJECTED"], 1):
        client.post(PROCESS, json=body(f"INV00{n}"))
        decide(client, f"INV00{n}", decision)
    assert client.get("/api/v1/vendor/ABC%20Pharma").json()["status"] == "inconsistent"


def test_vendors_seen_only_in_the_log_are_listed(client, reference):
    """A vendor with a PO but no profile in vendors.json still shows up once it has been processed."""
    reference.purchase_orders.append(PurchaseOrder(po_id="PO-NEW", vendor="New Co", expected_price=500,
                                                   expected_quantity=100, po_date="2026-09-01"))
    api.app.dependency_overrides[api.get_reference] = lambda: reference
    client.post(PROCESS, json=body(vendor="New Co"))
    new = [v for v in client.get("/api/v1/vendors").json() if v["name"] == "New Co"]
    assert new and (new[0]["payment_terms"], new[0]["status"]) == ("unknown", "new")


# ── health ───────────────────────────────────────────────────────────────────

def test_health_reports_status_without_secrets(client, fake_hindsight):
    response = client.get("/health")
    assert response.json() == {"groq": "configured", "hindsight": "reachable", "bank_id": "hap-unit",
                               "groq_model": "openai/gpt-oss-120b", "data_source": "files", "dataset": "fixtures",
                               "database": None}
    assert "TEST_SECRET" not in response.text
    assert fake_hindsight.calls_to("get_version")
    fake_hindsight.fail_next(401)
    assert client.get("/health").json()["hindsight"] == "unreachable"


def test_health_with_nothing_configured(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("HINDSIGHT_API_KEY")
    api.get_settings.cache_clear()
    try:
        with TestClient(api.app) as client:
            assert client.get("/health").json()["groq"] == "missing"
            assert client.get("/health").json()["hindsight"] == "missing"
    finally:
        api.get_settings.cache_clear()


def test_real_clients_are_built_lazily_without_network(monkeypatch):
    """No overrides: the dependencies build the real clients, and nothing connects until used."""
    api.get_settings.cache_clear()
    try:
        settings = api.get_settings()
        assert api.get_hindsight_client(settings) is api.get_hindsight_client(settings)  # cached
        assert api.get_groq_client(settings) is not None
        monkeypatch.delenv("GROQ_API_KEY")
        api.get_settings.cache_clear()
        assert api.get_groq_client(api.get_settings()) is None
    finally:
        api.get_settings.cache_clear()


# ── CORS, errors, logs ───────────────────────────────────────────────────────

@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:5173"])
def test_cors_preflight(client, origin):
    response = client.options(PROCESS, headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unexpected_error_is_a_clean_500_that_leaks_nothing(client, monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("boom with gsk_TEST_SECRET_DO_NOT_LEAK inside")

    monkeypatch.setattr(api.InvoiceProcessor, "process", boom)
    with caplog.at_level(logging.INFO), TestClient(api.app, raise_server_exceptions=False) as raw_client:
        response = raw_client.post(PROCESS, json=body())
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "message": "Internal server error. It has been logged."}}
    assert "Traceback" not in response.text and "TEST_SECRET" not in response.text
    assert "TEST_SECRET" not in caplog.text
    assert "unhandled RuntimeError" in caplog.text


def test_secrets_are_redacted_from_logs(caplog, monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "mysql_TEST_SECRET_pw")
    with caplog.at_level(logging.INFO, "paysage"):
        logging.getLogger("paysage").info("key is %s", "hs_TEST_SECRET_DO_NOT_LEAK")
        logging.getLogger("paysage").info("password is %s", "mysql_TEST_SECRET_pw")
    assert "TEST_SECRET" not in caplog.text and caplog.text.count("[redacted]") == 2


def test_unknown_route_uses_the_error_envelope(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"


def test_logs_show_every_pipeline_step_in_order(client, fake_groq, caplog):
    client.post(PROCESS, json=body())
    decide(client)
    caplog.clear()
    fake_groq.reply = llm_json("APPROVED", 0.9)
    with caplog.at_level(logging.INFO, "paysage"):
        client.post(PROCESS, json=body("INV002"))
        decide(client, "INV002")
    steps = [m.split(":", 1)[0] for m in caplog.messages]
    order = [steps.index(step) for step in ("rules", "recall", "reflect", "llm", "guardrail", "retain")]
    assert order == sorted(order)
