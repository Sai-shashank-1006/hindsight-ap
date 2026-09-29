"""The response shapes the frontend depends on: keys AND types.

Rates and confidence are fractions (the UI multiplies by 100: 94 would render as 9400%).
"""

import datetime as dt

from tests.conftest import body

REASON = "Contract price changed from ₹500 to ₹550 effective 2026-07-01"
PROCESS_KEYS = {"invoice_id", "vendor", "exception_detected", "exceptions", "hindsight_memories", "reflection",
                "memory_status", "evidence_level", "recommendation", "confidence", "explanation"}
MEMORY_KEYS = {"text", "vendor", "exception_type", "po_price", "invoice_price", "decision", "human_reason", "created_at"}


def fraction(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def run_story(client):
    client.post("/api/v1/invoice/process", json=body())
    client.post("/api/v1/invoice/store-decision", json={"invoice_id": "INV001", "human_decision": "APPROVED", "human_reason": REASON})
    return client.post("/api/v1/invoice/process", json=body("INV002")).json()


def test_process_response_shape(client):
    data = run_story(client)
    assert set(data) == PROCESS_KEYS  # a raw object, not wrapped in {status, data}
    assert fraction(data["confidence"])
    assert data["recommendation"] in {"APPROVED", "REJECTED", "NEEDS_REVIEW"}
    assert data["memory_status"] in {"ok", "unavailable"}
    assert data["evidence_level"] in {"VERIFIED_MATCH", "VERIFIED_REJECT", "CONFLICT", "NO_EVIDENCE", "NOT_REQUIRED"}
    assert isinstance(data["reflection"], str)
    exc = data["exception_detected"]
    assert set(exc) == {"type", "severity", "expected_value", "actual_value", "variance_percent", "reason"}
    assert isinstance(exc["variance_percent"], float) and exc["variance_percent"] == 10.0
    assert data["exceptions"] == [exc]
    [memory] = data["hindsight_memories"]
    assert MEMORY_KEYS <= set(memory)
    assert isinstance(memory["po_price"], float) and isinstance(memory["invoice_price"], float)
    assert iso(memory["created_at"]).tzinfo is not None


def test_clean_invoice_shape(client):
    data = client.post("/api/v1/invoice/process", json=body("INV005", vendor="XYZ Pharma", invoice_price=500, quantity=50)).json()
    assert (data["exception_detected"], data["exceptions"], data["reflection"]) == (None, [], None)
    assert fraction(data["confidence"])


def test_store_decision_shape(client):
    client.post("/api/v1/invoice/process", json=body())
    data = client.post("/api/v1/invoice/store-decision",
                       json={"invoice_id": "INV001", "human_decision": "APPROVED", "human_reason": REASON}).json()
    assert {"success", "retained", "memory_id"} <= set(data)
    assert isinstance(data["success"], bool) and isinstance(data["retained"], bool) and isinstance(data["memory_id"], str)


def test_dashboard_shapes(client):
    run_story(client)
    board = client.get("/api/v1/dashboard").json()
    assert set(board) == {"total_processed", "total_exceptions", "approval_rate", "active_vendors",
                          "recent_memories", "exception_breakdown"}
    assert fraction(board["approval_rate"]) and isinstance(board["total_processed"], int)
    assert all(set(e) == {"type", "count"} and isinstance(e["count"], int) for e in board["exception_breakdown"])
    for memory in board["recent_memories"]:
        iso(memory["created_at"])
    stats = client.get("/api/v1/dashboard/stats").json()
    assert fraction(stats["approval_rate"]) and all(isinstance(v, (int, float)) for v in stats.values())


def test_vendor_shapes(client):
    run_story(client)
    vendors = client.get("/api/v1/vendors").json()
    assert isinstance(vendors, list)
    for vendor in vendors:
        assert set(vendor) == {"name", "payment_terms", "historical_prices", "total_decisions", "approval_rate",
                               "status", "recent_exceptions"}
        assert fraction(vendor["approval_rate"]) and vendor["status"] in {"reliable", "inconsistent", "new"}
        assert all(isinstance(p, float) for p in vendor["historical_prices"])
        for exc in vendor["recent_exceptions"]:
            assert isinstance(exc["variance_percent"], float)
            iso(exc["created_at"])
    abc = client.get("/api/v1/vendor/ABC%20Pharma").json()
    assert abc["name"] == "ABC Pharma" and fraction(abc["approval_rate"])
    for event in client.get("/api/v1/vendor/ABC%20Pharma/timeline").json():
        iso(event["timestamp"])
        assert event["event"] in {"processed", "decided"}


def test_error_shapes(client):
    for response in (client.post("/api/v1/invoice/process", json={}),
                     client.post("/api/v1/invoice/process", json=body(vendor="Nobody")),
                     client.get("/api/v1/vendor/Nobody")):
        error = response.json()["error"]
        assert set(error) == {"code", "message"} and all(isinstance(v, str) and v for v in error.values())
