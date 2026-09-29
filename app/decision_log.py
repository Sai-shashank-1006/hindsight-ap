"""Local log of processed invoices and human decisions.

Feeds the dashboard, vendor pages and store-decision lookups without calling Groq or Hindsight
(the UI polls the dashboard). It is never used as memory: recommendations only ever see what
Hindsight recall returned for that request.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.models import (
    Decision,
    DashboardResponse,
    DashboardStats,
    ExceptionCount,
    ExceptionType,
    Invoice,
    MemorySummary,
    ProcessResponse,
    PurchaseOrder,
    TimelineEvent,
    Vendor,
    VendorException,
    VendorSummary,
    normalize_vendor,
)

RELIABLE_APPROVAL_RATE = 0.8


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class Processed:
    invoice: Invoice
    po: PurchaseOrder
    response: ProcessResponse
    at: str


@dataclass
class Decided:
    invoice_id: str
    vendor: str
    decision: Decision
    human_reason: str
    exception_types: List[str]
    retained: bool
    memory_id: Optional[str]
    at: str


class DecisionLog:
    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self.processed: Dict[str, Processed] = {}
        self.decided: Dict[str, Decided] = {}  # latest decision per invoice: a re-submission replaces
        if path and path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._apply(json.loads(line))

    # ── writes ──
    def record_processed(self, invoice: Invoice, po: PurchaseOrder, response: ProcessResponse) -> None:
        self._write({"kind": "processed", "at": now_iso(), "invoice": invoice.model_dump(mode="json"),
                     "po": po.model_dump(mode="json"), "response": response.model_dump(mode="json")})

    def record_decision(self, decided: Decided) -> None:
        self._write({"kind": "decided", **decided.__dict__, "decision": decided.decision.value})

    def _write(self, event: dict) -> None:
        self._apply(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _apply(self, event: dict) -> None:
        if event["kind"] == "processed":
            invoice = Invoice.model_validate(event["invoice"])
            self.processed[invoice.invoice_id] = Processed(
                invoice, PurchaseOrder.model_validate(event["po"]),
                ProcessResponse.model_validate(event["response"]), event["at"])
        else:
            fields = {k: v for k, v in event.items() if k != "kind"}
            fields["decision"] = Decision(fields["decision"])
            self.decided[fields["invoice_id"]] = Decided(**fields)

    # ── reads ──
    def get_processed(self, invoice_id: str) -> Optional[Processed]:
        return self.processed.get(invoice_id)

    def status(self, invoice_id: str) -> str:
        if invoice_id in self.decided:
            return "decided"
        return "processed" if invoice_id in self.processed else "pending"

    def _approval_rate(self, decisions: List[Decided]) -> float:
        return round(sum(d.decision is Decision.APPROVED for d in decisions) / len(decisions), 4) if decisions else 0.0

    def _memories(self, limit: int = 5) -> List[MemorySummary]:
        retained = sorted((d for d in self.decided.values() if d.retained), key=lambda d: d.at, reverse=True)
        return [MemorySummary(memory_id=d.memory_id, invoice_id=d.invoice_id, vendor=d.vendor,
                              exception_types=d.exception_types, decision=d.decision,
                              human_reason=d.human_reason, created_at=d.at) for d in retained[:limit]]

    def dashboard(self) -> DashboardResponse:
        counts = Counter(e.type.value for p in self.processed.values() for e in p.response.exceptions)
        return DashboardResponse(
            total_processed=len(self.processed),
            total_exceptions=sum(counts.values()),
            approval_rate=self._approval_rate(list(self.decided.values())),
            active_vendors=len({normalize_vendor(p.invoice.vendor) for p in self.processed.values()}),
            recent_memories=self._memories(),
            exception_breakdown=[ExceptionCount(type=t.value, count=counts.get(t.value, 0)) for t in ExceptionType],
        )

    def stats(self) -> DashboardStats:
        board = self.dashboard()
        return DashboardStats(
            total_processed=board.total_processed, total_exceptions=board.total_exceptions,
            total_decisions=len(self.decided),
            memories_retained=sum(d.retained for d in self.decided.values()),
            pending_decisions=sum(1 for i in self.processed if i not in self.decided),
            approval_rate=board.approval_rate, active_vendors=board.active_vendors,
        )

    def vendor_names(self) -> List[str]:
        names = {normalize_vendor(p.invoice.vendor): p.invoice.vendor for p in self.processed.values()}
        return list(names.values())

    def vendor_summary(self, name: str, profile: Optional[Vendor]) -> VendorSummary:
        key = normalize_vendor(name)
        decisions = [d for d in self.decided.values() if normalize_vendor(d.vendor) == key]
        processed = sorted((p for p in self.processed.values() if normalize_vendor(p.invoice.vendor) == key),
                           key=lambda p: p.at, reverse=True)
        rate = self._approval_rate(decisions)
        status = "new" if not decisions else "reliable" if rate >= RELIABLE_APPROVAL_RATE else "inconsistent"
        recent = [VendorException(invoice_id=p.invoice.invoice_id, type=e.type, severity=e.severity,
                                  variance_percent=e.variance_percent, created_at=p.at)
                  for p in processed for e in p.response.exceptions][:5]
        return VendorSummary(
            name=profile.name if profile else name,
            payment_terms=profile.payment_terms if profile else "unknown",
            historical_prices=profile.historical_prices if profile else [],
            total_decisions=len(decisions), approval_rate=rate, status=status, recent_exceptions=recent,
        )

    def knows_vendor(self, name: str) -> bool:
        return normalize_vendor(name) in {normalize_vendor(n) for n in self.vendor_names()}

    def timeline(self, name: str) -> List[TimelineEvent]:
        key = normalize_vendor(name)
        events = []
        for p in self.processed.values():
            if normalize_vendor(p.invoice.vendor) != key:
                continue
            found = ", ".join(f"{e.type.value} ({e.severity.value}, {e.variance_percent:g}%)"
                              for e in p.response.exceptions) or "no exceptions"
            events.append(TimelineEvent(timestamp=p.at, event="processed", invoice_id=p.invoice.invoice_id,
                                        detail=found, recommendation=p.response.recommendation))
        for d in self.decided.values():
            if normalize_vendor(d.vendor) == key:
                events.append(TimelineEvent(timestamp=d.at, event="decided", invoice_id=d.invoice_id,
                                            detail=d.human_reason, decision=d.decision, retained=d.retained))
        return sorted(events, key=lambda e: e.timestamp)
