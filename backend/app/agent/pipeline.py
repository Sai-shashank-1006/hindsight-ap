"""The pipeline, one logged step at a time:

    process():        rules -> recall -> reflect -> llm -> guardrail
    store_decision(): retain (only human decisions are ever stored)

Nothing is approved without a human, nothing crashes when Groq or Hindsight fails, and every
failure is reported as what it is ("memory offline" is not "no memory found").
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from app.agent.guardrail import assess, decide
from app.agent.llm import LLMAgent, LLMUnavailable, build_messages
from app.agent.rules import PRICE_TOLERANCE, RuleEngine
from app.memory.hindsight import HindsightMemory, MemoryUnavailable
from app.models import (
    Decision,
    EvidenceLevel,
    Invoice,
    MemoryStatus,
    ProcessResponse,
    StoreDecisionRequest,
    StoreDecisionResponse,
    format_money,
)
from app.storage.decision_log import Decided, DecisionLog
from app.storage.reference import ReferenceData

log = logging.getLogger("paysage")


class PurchaseOrderNotFound(LookupError):
    pass


class NotProcessed(LookupError):
    pass


class InvoiceProcessor:
    def __init__(self, reference: ReferenceData, memory: Optional[HindsightMemory], llm: LLMAgent,
                 decisions: DecisionLog):
        self.reference = reference
        self.memory = memory  # None when Hindsight isn't configured
        self.llm = llm
        self.decisions = decisions
        self.rules = RuleEngine()

    async def process(self, invoice: Invoice) -> ProcessResponse:
        po = self.reference.po_for(invoice)
        if po is None:
            raise PurchaseOrderNotFound(f"No purchase order on file for vendor '{invoice.vendor}'")

        exceptions = self.rules.detect_exceptions(invoice, po)
        found = ", ".join(f"{e.type.value}/{e.severity.value} ({e.variance_percent:g}%)" for e in exceptions)
        log.info("rules: %s from %s vs %s -> %s", invoice.invoice_id, invoice.vendor, po.po_id, found or "no exceptions")
        if invoice.po_price is not None and abs(invoice.po_price - po.expected_price) > PRICE_TOLERANCE:
            log.info("rules: invoice quotes PO price %s but %s says %s; the PO record wins",
                     format_money(invoice.po_price), po.po_id, format_money(po.expected_price))

        if not exceptions:
            log.info("recall: skipped (no exception); llm: skipped")
            response = ProcessResponse(
                invoice_id=invoice.invoice_id, vendor=invoice.vendor, evidence_level=EvidenceLevel.NOT_REQUIRED,
                recommendation=Decision.APPROVED, confidence=1.0,
                explanation=f"Invoice matches purchase order {po.po_id} on price and quantity. A reviewer still confirms it.",
            )
            self.decisions.record_processed(invoice, po, response)
            return response

        memories, status = [], MemoryStatus.OK
        if self.memory is None:
            status = MemoryStatus.UNAVAILABLE
            log.warning("recall: Hindsight is not configured")
        else:
            try:
                outcome = await self.memory.recall(invoice, exceptions)
            except MemoryUnavailable as exc:
                status = MemoryStatus.UNAVAILABLE
                log.warning("recall: failed, continuing without memory: %s", exc)
            else:
                memories = outcome.memories
                log.info("recall: %d facts returned; kept %d for %s; dropped %d for other vendors, %d unverifiable",
                         outcome.returned, len(memories), invoice.vendor, outcome.other_vendor, outcome.unverifiable)

        reflection = None
        if memories:
            try:
                reflection = await self.memory.reflect(invoice, exceptions)
                log.info("reflect: %s", reflection[:160])
            except MemoryUnavailable as exc:
                log.warning("reflect: failed, continuing without a reflection: %s", exc)
        else:
            log.info("reflect: skipped (no memory for %s)", invoice.vendor)

        evidence = assess(invoice.vendor, exceptions, memories)
        messages = build_messages(invoice, po, self.reference.vendor(invoice.vendor), exceptions,
                                  evidence.level, memories, reflection)
        llm_result, llm_error = None, None
        try:
            llm_result = await self.llm.recommend(messages)
            log.info("llm: %s suggests %s (%.2f)%s", self.llm.model, llm_result.decision.value,
                     llm_result.confidence, "" if llm_result.parsed else " [output unparseable]")
        except LLMUnavailable as exc:
            llm_error = str(exc)
            log.warning("llm: unavailable, using the evidence rule: %s", exc)

        decision, confidence, explanation = decide(invoice.vendor, exceptions, evidence, llm_result, llm_error)
        if status is MemoryStatus.UNAVAILABLE:
            decision, confidence = Decision.NEEDS_REVIEW, min(confidence, 0.5)
            explanation = "Memory is offline, so no history could be checked. " + explanation
        log.info("guardrail: evidence %s -> %s (%.2f)", evidence.level.value, decision.value, confidence)

        response = ProcessResponse(
            invoice_id=invoice.invoice_id, vendor=invoice.vendor, exception_detected=exceptions[0],
            exceptions=exceptions, hindsight_memories=memories, reflection=reflection, memory_status=status,
            evidence_level=evidence.level, recommendation=decision, confidence=confidence, explanation=explanation,
        )
        self.decisions.record_processed(invoice, po, response)
        return response

    async def store_decision(self, request: StoreDecisionRequest) -> StoreDecisionResponse:
        processed = self.decisions.get_processed(request.invoice_id)
        if processed is None:
            raise NotProcessed(f"Invoice {request.invoice_id} has not been processed")
        invoice, exceptions = processed.invoice, processed.response.exceptions
        decided_at = dt.datetime.now(dt.timezone.utc)
        success, retained, memory_id = True, False, None

        if not exceptions:
            message = "Decision recorded. The invoice had no exception, so there is nothing to remember."
            log.info("retain: skipped (no exception on %s)", invoice.invoice_id)
        elif self.memory is None:
            success, message = False, "Decision recorded but NOT remembered: Hindsight is not configured."
            log.warning("retain: Hindsight is not configured")
        else:
            try:
                memory_id = await self.memory.retain(invoice.vendor, invoice.invoice_id, exceptions,
                                                     request.human_decision, request.human_reason, decided_at)
            except MemoryUnavailable as exc:
                success, message = False, f"Decision recorded but NOT remembered: {exc}."
                log.warning("retain: failed: %s", exc)
            else:
                retained, message = True, f"Decision remembered in Hindsight as {memory_id}."
                log.info("retain: %s %s for %s stored as %s", request.human_decision.value,
                         invoice.invoice_id, invoice.vendor, memory_id)

        self.decisions.record_decision(Decided(
            invoice_id=invoice.invoice_id, vendor=invoice.vendor, decision=request.human_decision,
            human_reason=request.human_reason, exception_types=[e.type.value for e in exceptions],
            retained=retained, memory_id=memory_id, at=decided_at.isoformat(),
        ))
        return StoreDecisionResponse(success=success, retained=retained, memory_id=memory_id, message=message)
