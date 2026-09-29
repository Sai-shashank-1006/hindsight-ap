"""The local decision log survives a restart when DECISION_LOG_PATH is set."""

from app.models import StoreDecisionRequest
from app.storage.decision_log import DecisionLog
from tests.conftest import invoice


async def test_log_replays_after_restart(tmp_path, processor):
    path = tmp_path / "decisions.jsonl"
    processor.decisions = DecisionLog(path)
    await processor.process(invoice())
    await processor.store_decision(StoreDecisionRequest(invoice_id="INV001", human_decision="APPROVED", human_reason="ok"))
    await processor.store_decision(StoreDecisionRequest(invoice_id="INV001", human_decision="REJECTED", human_reason="no"))

    restarted = DecisionLog(path)
    assert restarted.dashboard() == processor.decisions.dashboard()
    assert restarted.status("INV001") == "decided"
    assert restarted.decided["INV001"].decision.value == "REJECTED"  # the later decision replaced the earlier one
    assert restarted.get_processed("INV001").response.recommendation.value == "NEEDS_REVIEW"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3  # an append-only log


def test_empty_log():
    log = DecisionLog()
    assert (log.dashboard().approval_rate, log.stats().pending_decisions, log.timeline("ABC Pharma")) == (0.0, 0, [])
