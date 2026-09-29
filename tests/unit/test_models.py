"""Models and validation. API-level 422s are in tests/api/test_endpoints.py."""

import builtins
import importlib
import pkgutil

import pytest
from pydantic import ValidationError

import app
from app.config import DEFAULT_GROQ_MODEL, Settings, env, load_settings
from app.models import Decision, Invoice, StoreDecisionRequest, format_money, normalize_vendor, parse_decision
from tests.conftest import invoice

MODULES = [importlib.import_module(f"app.{m.name}") for m in pkgutil.iter_modules(app.__path__)]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_no_module_shadows_the_builtin_exception(module):
    assert getattr(module, "Exception", builtins.Exception) is builtins.Exception


@pytest.mark.parametrize("field, value", [
    ("invoice_price", -5), ("invoice_price", 0), ("invoice_price", "abc"), ("invoice_price", float("nan")),
    ("quantity", 0), ("quantity", 1.5), ("invoice_date", "28/09/2026"), ("invoice_date", "2026-02-30"),
    ("invoice_date", "2026-09-28T10:00:00"), ("invoice_date", 1790000000), ("vendor", "   "), ("vendor", ""),
])
def test_invalid_invoices_are_rejected(field, value):
    data = {"invoice_id": "INV1", "vendor": "ABC Pharma", "invoice_price": 550, "quantity": 100,
            "invoice_date": "2026-09-28", field: value}
    with pytest.raises(ValidationError):
        Invoice.model_validate(data)


def test_valid_invoice_normalizes_whitespace_and_keeps_iso_date():
    inv = invoice(vendor="  ABC   Pharma ")
    assert (inv.vendor, inv.invoice_date) == ("ABC Pharma", "2026-09-28")


@pytest.mark.parametrize("raw, parsed", [
    ("approve", Decision.APPROVED), ("Approved", Decision.APPROVED), ("APPROVE", Decision.APPROVED),
    ("rejected", Decision.REJECTED), ("needs review", Decision.NEEDS_REVIEW), ("NEEDS_REVIEW", Decision.NEEDS_REVIEW),
    (Decision.REJECTED, Decision.REJECTED), ("MAYBE", None), ("", None),
])
def test_parse_decision(raw, parsed):
    assert parse_decision(raw) == parsed


def test_store_decision_request_validation():
    ok = StoreDecisionRequest(invoice_id="INV1", human_decision="approve", human_reason="  fine  ")
    assert (ok.human_decision, ok.human_reason) == (Decision.APPROVED, "fine")
    with pytest.raises(ValidationError):
        StoreDecisionRequest(invoice_id="INV1", human_decision="MAYBE", human_reason="x")
    with pytest.raises(ValidationError):
        StoreDecisionRequest(invoice_id="INV1", human_decision="APPROVED", human_reason="   ")


def test_vendor_matching_normalizes_case_and_whitespace_only():
    assert normalize_vendor("abc pharma ") == normalize_vendor("ABC  Pharma")
    assert normalize_vendor("ABC Pharma Ltd") != normalize_vendor("ABC Pharma")


def test_format_money():
    assert (format_money(500), format_money(550.5), format_money(1234.56)) == ("₹500", "₹550.50", "₹1,234.56")


def test_settings_defaults_and_placeholders(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "your_groq_key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    settings = load_settings()
    assert settings.groq_api_key is None  # placeholders count as unset
    assert settings.groq_model == DEFAULT_GROQ_MODEL == "openai/gpt-oss-120b"
    assert settings.data_dir == tmp_path
    assert settings.queue_file() == tmp_path / "demo_scenario.json"
    (tmp_path / "invoices.json").write_text("[]")
    assert load_settings().queue_file() == tmp_path / "invoices.json"
    monkeypatch.setenv("GROQ_MODEL", "qwen/qwen3-32b")
    monkeypatch.setenv("INVOICES_FILE", str(tmp_path / "x.json"))
    monkeypatch.setenv("DECISION_LOG_PATH", str(tmp_path / "log.jsonl"))
    settings = load_settings()
    assert (settings.groq_model, settings.queue_file(), settings.decision_log_path) == (
        "qwen/qwen3-32b", tmp_path / "x.json", tmp_path / "log.jsonl")
    assert env("NOT_SET_ANYWHERE") is None
    assert not Settings().hindsight_configured
