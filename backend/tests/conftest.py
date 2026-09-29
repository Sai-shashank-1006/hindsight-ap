"""Offline test setup: dummy credentials, the tests/fixtures data folder, and fakes injected at the
client boundary. Nothing here reaches the network: an autouse guard fails any test that tries."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

import app.config  # noqa: F401  (loads .env first, so the real values can be kept for the live tests below)

LIVE_ENV = {k: os.environ.get(k) for k in ("GROQ_API_KEY", "GROQ_MODEL", "HINDSIGHT_API_KEY",
                                           "HINDSIGHT_BANK_ID", "HINDSIGHT_API_URL")}
TEST_ENV = {
    "GROQ_API_KEY": "gsk_TEST_SECRET_DO_NOT_LEAK",
    "HINDSIGHT_API_KEY": "hs_TEST_SECRET_DO_NOT_LEAK",
    "HINDSIGHT_BANK_ID": "hap-unit",
    "HINDSIGHT_API_URL": "http://fake-hindsight",
    "DATA_DIR": str(Path(__file__).resolve().parent / "fixtures"),
}
os.environ.update(TEST_ENV)
# The tests never use the database in .env: the ones that need a database set their own.
for name in ("GROQ_MODEL", "INVOICES_FILE", "DECISION_LOG_PATH", "HINDSIGHT_TIMEOUT", "CORS_ORIGINS", "DATASET",
             "DATABASE_URL", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
    os.environ.pop(name, None)

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from app.agent.llm import LLMAgent  # noqa: E402
from app.agent.pipeline import InvoiceProcessor  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.memory.hindsight import HindsightMemory  # noqa: E402
from app.models import Invoice, PurchaseOrder  # noqa: E402
from app.storage.decision_log import DecisionLog  # noqa: E402
from app.storage.reference import ReferenceData  # noqa: E402
from tests.fakes import FakeGroq, FakeHindsight  # noqa: E402

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def _offline(request, monkeypatch):
    """Any non-loopback connection or DNS lookup in an offline test is a failure."""
    if request.node.get_closest_marker("live"):
        return
    real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo

    def connect(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOCAL_HOSTS:
            raise RuntimeError(f"offline test tried to connect to {address}")
        return real_connect(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        if host not in LOCAL_HOSTS and host is not None:
            raise RuntimeError(f"offline test tried to resolve {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def reference(settings):
    return ReferenceData.load(settings.data_dir, settings.queue_file())


@pytest.fixture
def fake_hindsight():
    return FakeHindsight()


@pytest.fixture
def fake_groq():
    return FakeGroq()


@pytest.fixture
def decision_log():
    return DecisionLog()


@pytest.fixture
def memory(fake_hindsight, settings):
    return HindsightMemory(fake_hindsight, settings.hindsight_bank_id, timeout=5)


@pytest.fixture
def processor(reference, memory, fake_groq, decision_log, settings):
    return InvoiceProcessor(reference, memory, LLMAgent(fake_groq, settings.groq_model), decision_log)


@pytest.fixture
def client(fake_hindsight, fake_groq, decision_log):
    api.get_settings.cache_clear()
    api._reference.cache_clear()
    api.app.dependency_overrides[api.get_hindsight_client] = lambda: fake_hindsight
    api.app.dependency_overrides[api.get_groq_client] = lambda: fake_groq
    api.app.dependency_overrides[api.get_decision_log] = lambda: decision_log
    with TestClient(api.app) as test_client:
        yield test_client
    api.app.dependency_overrides.clear()


def invoice(invoice_id: str = "INV001", vendor: str = "ABC Pharma", invoice_price: float = 550,
            quantity: int = 100, **extra) -> Invoice:
    return Invoice(invoice_id=invoice_id, vendor=vendor, invoice_price=invoice_price, quantity=quantity,
                   invoice_date=extra.pop("invoice_date", "2026-09-28"), **extra)


def po(vendor: str = "ABC Pharma", price: float = 500, quantity: int = 100) -> PurchaseOrder:
    return PurchaseOrder(po_id="PO-T", vendor=vendor, expected_price=price, expected_quantity=quantity,
                         po_date="2026-09-01")


def body(invoice_id: str = "INV001", vendor: str = "ABC Pharma", invoice_price=550, quantity=100, **extra) -> dict:
    """A /process request body, as the frontend sends it."""
    return {"invoice_id": invoice_id, "vendor": vendor, "po_price": extra.pop("po_price", 500),
            "invoice_price": invoice_price, "quantity": quantity,
            "invoice_date": extra.pop("invoice_date", "2026-09-28"), **extra}
