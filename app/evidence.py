"""The evidence guardrail: deterministic rules on top of the LLM.

Evidence comes only from vendor-matched memories returned by this request's recall. The LLM
may explain, but it can never approve without a verified human precedent for the same vendor,
exception type and invoiced amount. That's what keeps the demo (and the ledger) safe from an
over-eager model, a prompt injection in stored text, or price drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from app.llm_agent import LLMResult, UNPARSEABLE
from app.models import (
    Decision,
    EvidenceLevel,
    ExceptionType,
    InvoiceException,
    RecalledMemory,
    format_money,
    normalize_vendor,
)

AMOUNT_TOLERANCE = 0.01
NO_MEMORY = "No relevant verified historical memory found"


@dataclass
class Evidence:
    level: EvidenceLevel
    per_exception: Dict[ExceptionType, EvidenceLevel] = field(default_factory=dict)
    approvals: List[RecalledMemory] = field(default_factory=list)  # verified matches, per exception
    rejections: List[RecalledMemory] = field(default_factory=list)


def _amount(exc: InvoiceException) -> str:
    if exc.type is ExceptionType.PRICE_MISMATCH:
        return f"{format_money(exc.actual_value)}/unit"
    return f"{exc.actual_value:g} units"


def assess(vendor: str, exceptions: Sequence[InvoiceException], memories: Sequence[RecalledMemory]) -> Evidence:
    target = normalize_vendor(vendor)
    evidence = Evidence(EvidenceLevel.NO_EVIDENCE)
    for exc in exceptions:
        same = [m for m in memories
                if normalize_vendor(m.vendor) == target and m.exception_type == exc.type.value
                and m.actual_value is not None and abs(m.actual_value - exc.actual_value) <= AMOUNT_TOLERANCE]
        approved = [m for m in same if m.decision is Decision.APPROVED]
        rejected = [m for m in same if m.decision is Decision.REJECTED]
        if approved and rejected:
            level = EvidenceLevel.CONFLICT
        elif rejected:
            level = EvidenceLevel.VERIFIED_REJECT
        elif approved:
            level = EvidenceLevel.VERIFIED_MATCH
        else:
            level = EvidenceLevel.NO_EVIDENCE
        evidence.per_exception[exc.type] = level
        evidence.approvals += approved[:1]
        evidence.rejections += rejected[:1]

    levels = set(evidence.per_exception.values())
    if EvidenceLevel.CONFLICT in levels:
        evidence.level = EvidenceLevel.CONFLICT
    elif EvidenceLevel.VERIFIED_REJECT in levels:
        evidence.level = EvidenceLevel.VERIFIED_REJECT
    elif levels == {EvidenceLevel.VERIFIED_MATCH}:
        evidence.level = EvidenceLevel.VERIFIED_MATCH
    return evidence


def _cite(memory: RecalledMemory) -> str:
    when = (memory.created_at or "")[:10] or "an earlier date"
    return (f"a reviewer {memory.decision.value} {memory.vendor}'s {memory.exception_type} on invoice "
            f"{memory.invoice_id or 'on file'} on {when}, reason: \"{memory.human_reason}\"")


def evidence_summary(vendor: str, exceptions: Sequence[InvoiceException], evidence: Evidence) -> str:
    """One deterministic sentence stating what the memory shows."""
    what = " and ".join(f"{e.type.value} at {_amount(e)}" for e in exceptions)
    if evidence.level is EvidenceLevel.VERIFIED_MATCH:
        return "Verified precedent: " + "; ".join(_cite(m) for m in evidence.approvals) + "."
    if evidence.level is EvidenceLevel.VERIFIED_REJECT:
        return "Verified rejection on file: " + "; ".join(_cite(m) for m in evidence.rejections) + "."
    if evidence.level is EvidenceLevel.CONFLICT:
        return (f"Conflicting precedents for {vendor} ({what}): reviewers both approved and rejected "
                f"this same exception, so it needs human review.")
    return f"{NO_MEMORY} for {vendor} ({what}), so this needs human review."


def decide(vendor: str, exceptions: Sequence[InvoiceException], evidence: Evidence,
           llm: Optional[LLMResult], llm_error: Optional[str]) -> Tuple[Decision, float, str]:
    """(recommendation, confidence, explanation). The LLM advises; the evidence decides what's allowed."""
    summary = evidence_summary(vendor, exceptions, evidence)
    level = evidence.level

    if llm is None or not llm.parsed:  # Groq down or unparseable: memory keeps working
        why = f"The LLM was unavailable ({llm_error})." if llm is None else UNPARSEABLE
        if level is EvidenceLevel.VERIFIED_MATCH:
            return Decision.APPROVED, 0.8, f"{summary} {why} Recommending approval on that precedent."
        if level is EvidenceLevel.VERIFIED_REJECT:
            return Decision.REJECTED, 0.8, f"{summary} {why} Recommending rejection on that precedent."
        return Decision.NEEDS_REVIEW, min(0.5, llm.confidence if llm else 0.5), f"{summary} {why}"

    decision, confidence = llm.decision, llm.confidence
    note = ""
    if decision is Decision.APPROVED and level is not EvidenceLevel.VERIFIED_MATCH:
        decision = Decision.REJECTED if level is EvidenceLevel.VERIFIED_REJECT else Decision.NEEDS_REVIEW
        confidence = min(confidence, 0.5)
        note = f" The model suggested APPROVED; overridden because evidence is {level.value}."
    return decision, confidence, f"{summary}{note} Model: {llm.explanation}"
