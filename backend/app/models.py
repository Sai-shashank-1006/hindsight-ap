"""Pydantic schemas: master data, the API contract, and what flows between pipeline steps."""

from __future__ import annotations

import datetime as dt
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ExceptionType(str, Enum):
    PRICE_MISMATCH = "PRICE_MISMATCH"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


class Decision(str, Enum):
    """Both the agent's recommendation and the human's decision."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


DECISION_ALIASES = {
    "APPROVE": Decision.APPROVED, "APPROVED": Decision.APPROVED,
    "REJECT": Decision.REJECTED, "REJECTED": Decision.REJECTED,
    "NEEDS_REVIEW": Decision.NEEDS_REVIEW, "NEEDS REVIEW": Decision.NEEDS_REVIEW, "REVIEW": Decision.NEEDS_REVIEW,
}


def parse_decision(value: object) -> Optional[Decision]:
    """'approve', 'Approved', 'APPROVE' → APPROVED. None for anything unrecognised."""
    if isinstance(value, Decision):
        return value
    key = re.sub(r"[\s\-]+", " ", str(value)).strip().upper().replace(" ", "_")
    return DECISION_ALIASES.get(key) or DECISION_ALIASES.get(key.replace("_", " "))


class EvidenceLevel(str, Enum):
    VERIFIED_MATCH = "VERIFIED_MATCH"
    VERIFIED_REJECT = "VERIFIED_REJECT"
    CONFLICT = "CONFLICT"
    NO_EVIDENCE = "NO_EVIDENCE"
    NOT_REQUIRED = "NOT_REQUIRED"  # clean invoice: nothing to find evidence for


EVIDENCE_MEANING = {
    EvidenceLevel.VERIFIED_MATCH: "a human reviewer APPROVED this same vendor, exception type and invoiced amount before",
    EvidenceLevel.VERIFIED_REJECT: "a human reviewer REJECTED this same vendor, exception type and invoiced amount before",
    EvidenceLevel.CONFLICT: "reviewers both approved and rejected this same vendor, exception type and amount",
    EvidenceLevel.NO_EVIDENCE: "no human decision on file for this vendor, exception type and invoiced amount",
    EvidenceLevel.NOT_REQUIRED: "the invoice matches its purchase order",
}


class MemoryStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


def format_money(amount: float) -> str:
    """₹550 for whole rupees, ₹550.50 otherwise."""
    return f"₹{amount:,.0f}" if float(amount).is_integer() else f"₹{amount:,.2f}"


def normalize_vendor(name: str) -> str:
    """Vendor identity for matching: case and whitespace only."""
    return " ".join(str(name).split()).casefold()


def _iso_date(value: object) -> str:
    """YYYY-MM-DD and nothing else: no slashes, times or timestamps."""
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value.isoformat()
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("must be an ISO date, YYYY-MM-DD")
    dt.date.fromisoformat(value)  # rejects 2026-02-30
    return value


def _non_blank(value: str) -> str:
    stripped = " ".join(value.split())
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


# ── Master data and input ────────────────────────────────────────────────────

class Invoice(BaseModel):
    """An invoice as submitted. po_price is informational only: checks use the PO record."""

    invoice_id: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    invoice_price: float = Field(gt=0, allow_inf_nan=False)
    quantity: int = Field(gt=0)
    invoice_date: str
    po_price: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    po_id: Optional[str] = None
    invoice_total: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    item: Optional[str] = None

    _check_date = field_validator("invoice_date", mode="before")(_iso_date)
    _check_text = field_validator("invoice_id", "vendor")(_non_blank)


class PurchaseOrder(BaseModel):
    po_id: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    expected_price: float = Field(gt=0, allow_inf_nan=False)
    expected_quantity: int = Field(gt=0)
    po_date: str
    item: Optional[str] = None

    _check_date = field_validator("po_date", mode="before")(_iso_date)


class Vendor(BaseModel):
    name: str = Field(min_length=1)
    payment_terms: str
    historical_prices: List[float] = []
    contact: Optional[str] = None


# ── Pipeline ─────────────────────────────────────────────────────────────────

class InvoiceException(BaseModel):
    """A mismatch found by the rule engine. Not named Exception: that would shadow the builtin."""

    type: ExceptionType
    severity: Severity
    expected_value: float
    actual_value: float
    variance_percent: float  # absolute
    reason: str


class RecalledMemory(BaseModel):
    """One vendor-matched decision from a Hindsight recall. text is what Hindsight returned;
    the structured fields come from the record we retained with it."""

    text: str
    vendor: str
    invoice_id: Optional[str] = None
    exception_type: str
    po_price: Optional[float] = None  # price exceptions: the PO and invoiced unit prices
    invoice_price: Optional[float] = None
    expected_value: Optional[float] = None  # the compared values, for any exception type
    actual_value: Optional[float] = None
    decision: Decision
    human_reason: str
    created_at: Optional[str] = None  # ISO 8601


# ── API contract ─────────────────────────────────────────────────────────────

class ProcessResponse(BaseModel):
    invoice_id: str
    vendor: str
    exception_detected: Optional[InvoiceException] = None  # the most severe one
    exceptions: List[InvoiceException] = []
    hindsight_memories: List[RecalledMemory] = []
    reflection: Optional[str] = None
    memory_status: MemoryStatus = MemoryStatus.OK
    evidence_level: EvidenceLevel
    recommendation: Decision
    confidence: float = Field(ge=0, le=1)
    explanation: str


class StoreDecisionRequest(BaseModel):
    invoice_id: str = Field(min_length=1)
    human_decision: Decision
    human_reason: str

    @field_validator("human_decision", mode="before")
    @classmethod
    def _decision(cls, value: object) -> Decision:
        decision = parse_decision(value)
        if decision is None:
            raise ValueError("must be APPROVED, REJECTED or NEEDS_REVIEW")
        return decision

    @field_validator("human_reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a reason is required: it is what Hindsight will remember")
        return value.strip()


class StoreDecisionResponse(BaseModel):
    success: bool
    retained: bool
    memory_id: Optional[str] = None
    message: str


class ExceptionCount(BaseModel):
    type: str
    count: int


class MemorySummary(BaseModel):
    memory_id: str
    invoice_id: str
    vendor: str
    exception_types: List[str]
    decision: Decision
    human_reason: str
    created_at: str


class DashboardResponse(BaseModel):
    total_processed: int
    total_exceptions: int
    approval_rate: float = Field(ge=0, le=1)
    active_vendors: int
    recent_memories: List[MemorySummary]
    exception_breakdown: List[ExceptionCount]


class DashboardStats(BaseModel):
    total_processed: int
    total_exceptions: int
    total_decisions: int
    memories_retained: int
    pending_decisions: int
    approval_rate: float = Field(ge=0, le=1)
    active_vendors: int


class VendorException(BaseModel):
    invoice_id: str
    type: ExceptionType
    severity: Severity
    variance_percent: float
    created_at: str


class VendorSummary(BaseModel):
    name: str
    payment_terms: str
    historical_prices: List[float]
    total_decisions: int
    approval_rate: float = Field(ge=0, le=1)
    status: str  # reliable | inconsistent | new
    recent_exceptions: List[VendorException]


class TimelineEvent(BaseModel):
    timestamp: str
    event: str  # processed | decided
    invoice_id: str
    detail: str
    recommendation: Optional[Decision] = None
    decision: Optional[Decision] = None
    retained: Optional[bool] = None


class QueuedInvoice(Invoice):
    status: str  # pending | processed | decided


class QueueSummary(BaseModel):
    total: int
    pending: int
    processed: int  # run through the agent, no human decision yet
    decided: int
    first_open: Optional[int] = None  # position of the first invoice without a decision


class HealthResponse(BaseModel):
    groq: str  # configured | missing
    hindsight: str  # reachable | unreachable | missing
    bank_id: Optional[str]
    groq_model: str
    data_source: str = "files"  # files | mysql (or another database's kind)
    dataset: Optional[str] = None
    database: Optional[str] = None  # connected | unreachable; None without a database
