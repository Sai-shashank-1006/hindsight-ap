"""Hindsight memory: retain human AP decisions, recall them for new exceptions, reflect on them.

Uses the official client (pip install hindsight-client), async methods only.

Recall returns facts Hindsight EXTRACTED, not the text we retained. So every retained decision
ends with one machine-readable [AP-RECORD ...] line per exception, and recall asks for chunks
(the original text) to read those lines back. A recalled fact whose record can't be read, or
whose record names another vendor, is dropped: vendor isolation is enforced here, never left
to semantic search.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
from urllib.parse import quote, unquote

import aiohttp
from hindsight_client import Hindsight
from hindsight_client_api.exceptions import ApiException

from app.config import Settings
from app.models import (
    Decision,
    ExceptionType,
    Invoice,
    InvoiceException,
    RecalledMemory,
    format_money,
    normalize_vendor,
    parse_decision,
)

log = logging.getLogger("paysage")

RETAIN_CONTEXT = ("Accounts-payable exception resolution: a human reviewer's verified decision "
                  "on one vendor's invoice exception")
BANK_MISSION = ("Accounts-payable memory: remember human-verified, vendor-specific invoice exceptions, "
                "decisions, reasons and effective dates. Never generalize one vendor's exception to "
                "another vendor.")
RECALL_TYPES = ["world", "experience"]  # the facts a retained decision becomes (never observations)
RECORD_LINE = re.compile(r"^\[AP-RECORD (?P<body>[^\]\n]*)\]$", re.MULTILINE)
# Characters left readable in record values. "|", "[", "]", "%" and newlines are always encoded,
# so no value can end a field, end the record, or start a new line.
_SAFE = " .,:;'()/-_+@#&*!?="
FAILURES = (ApiException, TimeoutError, OSError, aiohttp.ClientError, ValueError)


class MemoryUnavailable(RuntimeError):
    """A Hindsight call failed. The message says why in plain words."""


def explain_failure(exc: BaseException, bank_id: str, timeout: float) -> str:
    status = getattr(exc, "status", None)
    if isinstance(exc, TimeoutError):
        return f"Hindsight timed out after {timeout:g}s"
    if status == 401:
        return "invalid Hindsight API key"
    if status == 402:
        return "Hindsight credits exhausted"
    if status == 403:
        return f"Hindsight API key has no access to bank {bank_id}"
    if status == 404:
        return f"bank {bank_id} not found"
    if status in (429, 503):
        return "Hindsight is at capacity"
    if status is not None:
        return f"Hindsight error (HTTP {status})"
    return f"could not reach Hindsight ({type(exc).__name__})"


def make_client(settings: Settings, require_bank: bool = True) -> Optional[Hindsight]:
    """None when Hindsight isn't configured: no key for a remote server (a local one needs none), or
    no bank. Creating the client makes no network call."""
    if not settings.hindsight_usable or (require_bank and not settings.hindsight_bank_id):
        return None
    return Hindsight(base_url=settings.hindsight_api_url, api_key=settings.hindsight_api_key,
                     timeout=settings.hindsight_timeout, max_attempts=2)


# ── The retained text ────────────────────────────────────────────────────────

def _number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _describe(exc: InvoiceException) -> str:
    if exc.type is ExceptionType.PRICE_MISMATCH:
        return (f"{exc.type.value} (PO {format_money(exc.expected_value)}/unit, "
                f"invoiced {format_money(exc.actual_value)}/unit)")
    return f"{exc.type.value} (PO {exc.expected_value:g} units, invoiced {exc.actual_value:g} units)"


def record_line(vendor: str, invoice_id: str, exc: InvoiceException, decision: Decision,
                reason: str, decided_at: dt.datetime) -> str:
    fields = {
        "vendor": vendor, "type": exc.type.value, "po": _number(exc.expected_value),
        "invoice": _number(exc.actual_value), "decision": decision.value, "invoice_id": invoice_id,
        "at": decided_at.isoformat(), "reason": reason,
    }
    return "[AP-RECORD " + "|".join(f"{k}={quote(str(v), safe=_SAFE)}" for k, v in fields.items()) + "]"


def build_content(vendor: str, invoice_id: str, exceptions: Sequence[InvoiceException], decision: Decision,
                  reason: str, decided_at: dt.datetime) -> str:
    """Prose for Hindsight to extract facts from, then one record line per exception."""
    one_line = " ".join(reason.split())  # nothing in a reason can start a record line
    ending = "" if one_line[-1:] in (".", "!", "?") else "."
    prose = (f"AP decision for vendor {vendor}, invoice {invoice_id}: "
             f"{' and '.join(_describe(e) for e in exceptions)}. Reviewer {decision.value}. "
             f"Reason: {one_line}{ending}")
    records = [record_line(vendor, invoice_id, e, decision, reason, decided_at) for e in exceptions]
    return "\n".join([prose, *records])


def parse_records(text: str) -> List[Dict[str, str]]:
    records = []
    for match in RECORD_LINE.finditer(text):
        fields = {}
        for part in match.group("body").split("|"):
            key, sep, value = part.partition("=")
            if sep:
                fields[key.strip()] = unquote(value)
        records.append(fields)
    return records


def _float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _memory(text: str, fields: Dict[str, str], fallback_time: Optional[str]) -> Optional[RecalledMemory]:
    decision, vendor, exception_type = parse_decision(fields.get("decision")), fields.get("vendor"), fields.get("type")
    if not (decision and vendor and exception_type):
        return None
    expected, actual = _float(fields.get("po")), _float(fields.get("invoice"))
    is_price = exception_type == ExceptionType.PRICE_MISMATCH.value
    return RecalledMemory(
        text=text, vendor=vendor, invoice_id=fields.get("invoice_id"), exception_type=exception_type,
        po_price=expected if is_price else None, invoice_price=actual if is_price else None,
        expected_value=expected, actual_value=actual, decision=decision,
        human_reason=fields.get("reason", ""), created_at=fields.get("at") or fallback_time,
    )


def _amounts(exceptions: Sequence[InvoiceException]) -> str:
    parts = []
    for exc in exceptions:
        if exc.type is ExceptionType.PRICE_MISMATCH:
            parts.append(f"invoice {format_money(exc.actual_value)} vs PO {format_money(exc.expected_value)}")
        else:
            parts.append(f"invoiced {exc.actual_value:g} units vs PO {exc.expected_value:g} units")
    return ", ".join(parts)


# ── The wrapper ──────────────────────────────────────────────────────────────

@dataclass
class RecallOutcome:
    memories: List[RecalledMemory]
    returned: int  # facts Hindsight returned
    other_vendor: int  # records dropped because they name another vendor
    unverifiable: int  # facts dropped because no record could be read


class HindsightMemory:
    def __init__(self, client: Hindsight, bank_id: str, timeout: float = 30.0):
        self.client = client
        self.bank_id = bank_id
        self.timeout = timeout

    def _unavailable(self, exc: BaseException) -> MemoryUnavailable:
        return MemoryUnavailable(explain_failure(exc, self.bank_id, self.timeout))

    @staticmethod
    def memory_id(invoice_id: str) -> str:
        return f"ap-decision-{invoice_id}"

    @staticmethod
    def recall_query(invoice: Invoice, exceptions: Sequence[InvoiceException]) -> str:
        types = " and ".join(e.type.value for e in exceptions)
        return (f"Past accounts-payable decisions for vendor {invoice.vendor} on {types} exceptions, "
                f"{_amounts(exceptions)}")

    @staticmethod
    def reflect_query(invoice: Invoice, exceptions: Sequence[InvoiceException]) -> str:
        types = " and ".join(e.type.value for e in exceptions)
        return (f"Considering only decisions about vendor {invoice.vendor}: does the current {types} on "
                f"invoice {invoice.invoice_id} ({_amounts(exceptions)}) match an exception a human reviewer "
                f"previously verified for {invoice.vendor}? Use {invoice.vendor}'s own history only; "
                f"decisions about any other vendor do not apply. Answer in at most three plain sentences "
                f"(no headings, lists or tables): start with Yes or No, then name the earlier invoice and "
                f"the reviewer's reason.")

    async def recall(self, invoice: Invoice, exceptions: Sequence[InvoiceException]) -> RecallOutcome:
        try:
            response = await self.client.arecall(
                bank_id=self.bank_id, query=self.recall_query(invoice, exceptions),
                types=RECALL_TYPES, budget="mid", max_tokens=4096, include_chunks=True,
            )
        except FAILURES as exc:
            raise self._unavailable(exc) from exc

        chunks = response.chunks or {}
        target = normalize_vendor(invoice.vendor)
        kept: Dict[tuple, RecalledMemory] = {}
        other_vendor = unverifiable = 0
        for result in response.results:
            chunk = chunks.get(result.chunk_id) if result.chunk_id else None
            records = parse_records(chunk.text) if chunk else []
            if not records and result.metadata:
                meta = result.metadata
                records = [{"vendor": meta.get("vendor", ""), "type": t, "decision": meta.get("decision", ""),
                            "invoice_id": meta.get("invoice_id", "")}
                           for t in meta.get("exception_type", "").split(",") if t]
            memories = [_memory(result.text, fields, result.occurred_start or result.mentioned_at) for fields in records]
            if not any(memories):
                unverifiable += 1
                continue
            for memory in filter(None, memories):
                if normalize_vendor(memory.vendor) != target:
                    other_vendor += 1
                    continue
                kept.setdefault((memory.invoice_id, memory.exception_type), memory)
        return RecallOutcome(list(kept.values()), len(response.results), other_vendor, unverifiable)

    async def reflect(self, invoice: Invoice, exceptions: Sequence[InvoiceException]) -> str:
        try:
            response = await self.client.areflect(
                bank_id=self.bank_id, query=self.reflect_query(invoice, exceptions), budget="low",
                context=f"Accounts-payable review of one invoice exception for vendor {invoice.vendor}",
                # The same facts recall reads: the retained decisions. Without this, reflect first
                # searches mental models and observations (PaySage builds neither), spending its
                # steps and tokens there before it reaches the decisions.
                fact_types=RECALL_TYPES, exclude_mental_models=True,
            )
        except FAILURES as exc:
            raise self._unavailable(exc) from exc
        return response.text.strip()

    async def retain(self, vendor: str, invoice_id: str, exceptions: Sequence[InvoiceException],
                     decision: Decision, reason: str, decided_at: dt.datetime) -> str:
        """Stores one decision synchronously, so the very next recall can see it. Returns its memory id."""
        memory_id = self.memory_id(invoice_id)
        try:
            response = await self.client.aretain(
                bank_id=self.bank_id,
                content=build_content(vendor, invoice_id, exceptions, decision, reason, decided_at),
                context=RETAIN_CONTEXT,
                timestamp=decided_at,
                document_id=memory_id,
                metadata={"vendor": vendor, "invoice_id": invoice_id, "decision": decision.value,
                          "exception_type": ",".join(e.type.value for e in exceptions)},
                retain_async=False,
            )
        except FAILURES as exc:
            raise self._unavailable(exc) from exc
        if not response.success:
            raise MemoryUnavailable("Hindsight did not confirm the retain")
        return memory_id

    async def reachable(self) -> bool:
        try:
            await self.client.aget_version()
        except FAILURES as exc:
            log.warning("health: %s", explain_failure(exc, self.bank_id, self.timeout))
            return False
        return True


async def create_fresh_bank(client: Hindsight, prefix: str, protected_bank_id: Optional[str]) -> str:
    """A new, empty bank for tests or a clean demo. Refuses to touch the configured bank."""
    now = dt.datetime.now(dt.timezone.utc)
    bank_id = f"{prefix}-{now:%Y%m%d-%H%M%S}-{now.microsecond // 1000:03d}"
    if protected_bank_id and bank_id == protected_bank_id:
        raise ValueError(f"refusing to reuse the configured bank {protected_bank_id}")
    try:
        await client.acreate_bank(
            bank_id=bank_id, name=f"PaySage {bank_id}", mission=BANK_MISSION,
            disposition_skepticism=4, disposition_literalism=4, disposition_empathy=2,
            # PaySage recalls facts and experiences, never observations: building them would spend an
            # LLM call after every retain (Hindsight Cloud credits, or a free Groq tier's token budget).
            enable_observations=False,
        )
    except FAILURES as exc:
        raise MemoryUnavailable(explain_failure(exc, bank_id, 0)) from exc
    return bank_id
