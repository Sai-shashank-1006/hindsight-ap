"""Live rehearsal against the REAL Groq and Hindsight APIs. Opt-in: it spends credits.

    bash:        RUN_LIVE=1 pytest tests/live -m live -s
    PowerShell:  $env:RUN_LIVE="1"; pytest tests/live -m live -s

Every test creates its own fresh bank, hap-test-<utc timestamp>, and refuses to run if that id
equals HINDSIGHT_BANK_ID: the demo bank is never touched. With -s it prints a transcript and
per-step latencies.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import time
import warnings

import pytest
from fastapi.testclient import TestClient

import api
from app.agent.rules import RuleEngine
from app.config import load_settings
from app.memory.hindsight import HindsightMemory, create_fresh_bank, make_client
from app.models import Decision
from app.storage.decision_log import DecisionLog
from tests.conftest import LIVE_ENV, body, invoice, po


def _real(name: str):
    value = (LIVE_ENV.get(name) or "").strip()
    return None if not value or value.lower().startswith("your_") else value


ENABLED = os.getenv("RUN_LIVE") == "1" and _real("GROQ_API_KEY") and _real("HINDSIGHT_API_KEY")
pytestmark = [pytest.mark.live,
              pytest.mark.skipif(not ENABLED, reason="set RUN_LIVE=1 and real GROQ_API_KEY and HINDSIGHT_API_KEY")]

REASON = "Contract price changed from ₹500 to ₹550 effective 2026-07-01"
WARN_AFTER, FAIL_AFTER, VISIBLE_WITHIN = 8.0, 20.0, 15.0
EXPECTED = ["NEEDS_REVIEW", "APPROVED", "NEEDS_REVIEW", "NEEDS_REVIEW"]  # steps 1, 3, 4, 5: same as offline


def _clear_caches():
    for cached in (api.get_settings, api._reference, api._hindsight, api._groq):
        cached.cache_clear()


@pytest.fixture
def live_bank(monkeypatch):
    """Real keys in the environment and a brand-new bank; everything else as in the offline story."""
    for name in ("GROQ_API_KEY", "HINDSIGHT_API_KEY", "HINDSIGHT_API_URL", "GROQ_MODEL"):
        if _real(name):
            monkeypatch.setenv(name, _real(name))
    async def create():
        client = make_client(load_settings(), require_bank=False)
        try:
            return await create_fresh_bank(client, "hap-test", protected_bank_id=_real("HINDSIGHT_BANK_ID"))
        finally:
            await client.aclose()

    bank = asyncio.run(create())
    assert bank != _real("HINDSIGHT_BANK_ID"), "refusing to run against the demo bank"
    monkeypatch.setenv("HINDSIGHT_BANK_ID", bank)
    print(f"\n[live] fresh bank {bank}")
    _clear_caches()
    yield bank
    _clear_caches()
    api.app.dependency_overrides.clear()


def _timed(label, call, timings):
    started = time.perf_counter()
    result = call()
    seconds = time.perf_counter() - started
    timings.append((label, seconds))
    if seconds > WARN_AFTER:
        warnings.warn(f"{label} took {seconds:.1f}s (demo budget {WARN_AFTER:g}s)")
    assert seconds <= FAIL_AFTER, f"{label} took {seconds:.1f}s, over the {FAIL_AFTER:g}s limit"
    return result


def test_retained_decision_becomes_recallable(live_bank):
    """Retain one ABC decision synchronously, then poll recall every second until it shows up."""
    async def run():
        settings = load_settings()
        client = make_client(settings)
        memory = HindsightMemory(client, live_bank, settings.hindsight_timeout)
        exceptions = RuleEngine().detect_exceptions(invoice(), po())
        try:
            started = time.perf_counter()
            await memory.retain("ABC Pharma", "INV001", exceptions, Decision.APPROVED, REASON,
                                dt.datetime.now(dt.timezone.utc))
            retained_at = time.perf_counter()
            while time.perf_counter() - retained_at < VISIBLE_WITHIN:
                outcome = await memory.recall(invoice("INV002"), exceptions)
                if outcome.memories:
                    return retained_at - started, time.perf_counter() - retained_at, outcome
                await asyncio.sleep(1)
            return retained_at - started, None, None
        finally:
            await client.aclose()

    retain_seconds, visible_after, outcome = asyncio.run(run())
    print(f"[live] retain took {retain_seconds:.1f}s; visible to recall after "
          f"{'never' if visible_after is None else f'{visible_after:.1f}s'}")
    assert visible_after is not None, f"retained decision not recallable within {VISIBLE_WITHIN:g}s"
    [found] = outcome.memories
    assert (found.vendor, found.decision, found.human_reason) == ("ABC Pharma", Decision.APPROVED, REASON)


@pytest.mark.parametrize("run", [1, 2, 3])
def test_story(live_bank, run):
    """The five demo steps against real Groq and Hindsight, three times, a fresh bank each time."""
    api.app.dependency_overrides[api.get_decision_log] = DecisionLog  # a new, empty log per run
    timings, steps = [], []
    with TestClient(api.app) as client:  # one event loop for the whole story
        def process(*args, **kwargs):
            data = _timed(f"process {args[0]}", lambda: client.post("/api/v1/invoice/process",
                                                                   json=body(*args, **kwargs)), timings)
            assert data.status_code == 200, data.text
            steps.append(data.json())
            result = steps[-1]
            print(f"[live run {run}] {result['invoice_id']} {result['vendor']}: {result['recommendation']} "
                  f"({result['confidence']:.0%}), evidence {result['evidence_level']}, "
                  f"{len(result['hindsight_memories'])} memories\n            why: {result['explanation']}")
            return result

        step1 = process("INV001")
        stored = _timed("store-decision INV001", lambda: client.post("/api/v1/invoice/store-decision", json={
            "invoice_id": "INV001", "human_decision": "APPROVED", "human_reason": REASON}), timings).json()
        assert stored["retained"] is True, stored
        step3 = process("INV002")
        step4 = process("INV003", vendor="XYZ Pharma", quantity=50)
        step5 = process("INV004", invoice_price=600)

    print(f"[live run {run}] latency: " + ", ".join(f"{label} {s:.1f}s" for label, s in timings))
    assert [s["recommendation"] for s in (step1, step3, step4, step5)] == EXPECTED
    assert step1["hindsight_memories"] == [] and step4["hindsight_memories"] == []
    assert any(m["vendor"] == "ABC Pharma" and m["human_reason"] == REASON for m in step3["hindsight_memories"])
    assert step3["evidence_level"] == "VERIFIED_MATCH" and step5["evidence_level"] == "NO_EVIDENCE"
    assert all(s["memory_status"] == "ok" for s in (step1, step3, step4, step5))
