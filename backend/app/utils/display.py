"""Terminal rendering for the CLI. Pipeline steps arrive through logging; this draws the rest."""

from __future__ import annotations

import os
import sys
import textwrap
from typing import List, Optional, Tuple

from app.models import (
    Decision,
    Invoice,
    ProcessResponse,
    PurchaseOrder,
    Severity,
    StoreDecisionResponse,
    format_money,
)

WIDTH = 78
INDENT = "        "
_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "blue": "34", "magenta": "35"}
SEVERITY_COLOR = {Severity.CRITICAL: "red", Severity.WARNING: "yellow", Severity.INFO: "blue"}
DECISION_COLOR = {Decision.APPROVED: "green", Decision.REJECTED: "red", Decision.NEEDS_REVIEW: "magenta"}


def style(text: str, *names: str) -> str:
    if not _COLOR or not names:
        return text
    return "".join(f"\033[{_CODES[n]}m" for n in names) + text + "\033[0m"


def wrap(text: str, indent: str, first: Optional[str] = None, *styles: str) -> None:
    for line in textwrap.wrap(text, WIDTH, initial_indent=first or indent, subsequent_indent=indent):
        print(style(line, *styles))


def banner(memory: str, reasoning: str) -> None:
    print(style("PAYSAGE", "bold") + style(" · every invoice teaches the next one", "dim"))
    print(f"  Memory:    {memory}")
    print(f"  Reasoning: {reasoning}")


def section(title: str) -> None:
    print()
    print(style(f"━━ {title} " + "━" * max(3, WIDTH - len(title) - 4), "bold", "blue"))


def error(text: str) -> None:
    wrap(text, "    ", "  ✗ ", "red")


def show_invoice(invoice: Invoice, po: Optional[PurchaseOrder]) -> None:
    section(f"Invoice {invoice.invoice_id} · {invoice.vendor}")
    if invoice.item:
        wrap(invoice.item, "           ", "  Item     ")
    if po:
        print(f"  PO       {po.po_id} · {po.expected_quantity} × {format_money(po.expected_price)} · {po.po_date}")
    print(f"  Billed   {invoice.quantity} × {format_money(invoice.invoice_price)} · {invoice.invoice_date}")


def show_response(response: ProcessResponse) -> None:
    print()
    for exc in response.exceptions:
        tag = style(f"[{exc.severity.value}]", "bold", SEVERITY_COLOR[exc.severity])
        wrap(f"{exc.type.value}: {exc.reason}", "    ", f"  {tag} ")
    for memory in response.hindsight_memories:
        wrap(f"{memory.text} ({memory.decision.value}: {memory.human_reason})", "      ", "  • memory: ")
    if response.reflection:
        wrap(response.reflection, "      ", "  • reflection: ", "dim")
    filled = round(response.confidence * 10)
    rec = style(response.recommendation.label, "bold", DECISION_COLOR[response.recommendation])
    print(f"\n  RECOMMENDATION  {rec}  {'█' * filled}{'░' * (10 - filled)} {response.confidence:.0%}"
          f"   evidence {response.evidence_level.value} · memory {response.memory_status.value}")
    wrap(response.explanation, "                  ", "  Why             ")


def show_stored(result: StoreDecisionResponse) -> None:
    color = "green" if result.retained else "yellow" if result.success else "red"
    wrap(result.message, "    ", "  ✓ " if result.retained else "  ! ", color)


Row = Tuple[ProcessResponse, Optional[Decision], Optional[StoreDecisionResponse]]


def show_summary(rows: List[Row]) -> None:
    section("Summary")
    print(style(f"  {'Invoice':<10}{'Vendor':<14}{'Evidence':<17}{'Recommendation':<19}{'Human':<14}Retained", "bold"))
    for response, decision, stored in rows:
        rec = f"{response.recommendation.label} {response.confidence:.0%}"
        human = decision.label if decision else "skipped"
        retained = "yes" if stored and stored.retained else "no" if stored else "-"
        print(f"  {response.invoice_id[:9]:<10}{response.vendor[:13]:<14}{response.evidence_level.value:<17}"
              f"{rec:<19}{human:<14}{retained}")
