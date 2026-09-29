"""Hindsight AP command line: the API's pipeline, with a human at the keyboard.

    python main.py                  the demo scenario in DATA_DIR (data/demo_scenario.json)
    python main.py --fresh          same, on a new, empty Hindsight bank
    python main.py --invoices data/real/invoices.json INV31324 INV29616
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from groq import AsyncGroq

from app import display
from app.config import load_settings
from app.decision_log import DecisionLog
from app.invoice_processor import InvoiceProcessor, PurchaseOrderNotFound
from app.llm_agent import LLMAgent
from app.logs import configure_logging
from app.memory import HindsightMemory, MemoryUnavailable, create_fresh_bank, make_client
from app.models import Decision, StoreDecisionRequest
from app.reference import ReferenceData

DECISION_KEYS = {"A": Decision.APPROVED, "R": Decision.REJECTED, "N": Decision.NEEDS_REVIEW}


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hindsight AP: an accounts payable agent that learns from your decisions.")
    parser.add_argument("invoice_ids", nargs="*", metavar="INVOICE_ID", help="invoices to process (default: all)")
    parser.add_argument("--invoices", type=Path, help="invoices JSON file (POs are read from the same folder)")
    parser.add_argument("--fresh", action="store_true", help="create a new, empty Hindsight bank for this run")
    parser.add_argument("--bank", help="Hindsight bank ID for this run (overrides HINDSIGHT_BANK_ID)")
    return parser.parse_args(argv)


def get_user_input() -> Tuple[Optional[Decision], Optional[str]]:
    """The human decision. (None, None) on skip or end of input."""
    try:
        while True:
            key = input(f"{display.INDENT}Decision? (A)pprove / (R)eject / (N)eeds review / (S)kip: ").strip().upper()[:1]
            if key == "S":
                return None, None
            if key in DECISION_KEYS:
                break
            print(f"{display.INDENT}Use A, R, N or S.")
        reason = ""
        while not reason:
            reason = input(f"{display.INDENT}Reason (Hindsight will remember this): ").strip()
        return DECISION_KEYS[key], reason
    except EOFError:
        print()
        return None, None


async def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    queue_file = args.invoices or settings.queue_file()
    data_dir = queue_file.parent if (queue_file.parent / "purchase_orders.json").exists() else settings.data_dir
    reference = ReferenceData.load(data_dir, queue_file)

    client = make_client(settings, require_bank=False)
    bank = args.bank or settings.hindsight_bank_id
    if client is None or not (bank or args.fresh):
        display.error("Hindsight is required: set HINDSIGHT_API_KEY and HINDSIGHT_BANK_ID in .env")
        return 2
    if args.fresh:
        try:
            bank = await create_fresh_bank(client, "hap-demo", settings.hindsight_bank_id)
        except MemoryUnavailable as exc:
            display.error(f"Could not create a fresh bank: {exc}")
            return 2
    memory = HindsightMemory(client, bank, settings.hindsight_timeout)
    groq_client = AsyncGroq(api_key=settings.groq_api_key) if settings.groq_api_key else None
    processor = InvoiceProcessor(reference, memory, LLMAgent(groq_client, settings.groq_model), DecisionLog())

    by_id = {inv.invoice_id: inv for inv in reference.invoices}
    missing = [i for i in args.invoice_ids if i not in by_id]
    if missing:
        display.error(f"Not in {queue_file.name}: {', '.join(missing)}")
        return 1
    queue = [by_id[i] for i in args.invoice_ids] or reference.invoices

    display.banner(f"Hindsight · bank '{bank}'",
                   f"Groq · {settings.groq_model}" if groq_client else "Groq not configured: evidence rule only")
    rows: List[display.Row] = []
    for number, invoice in enumerate(queue):
        if number and not _pause():
            break
        display.show_invoice(invoice, reference.po_for(invoice))
        try:
            response = await processor.process(invoice)
        except PurchaseOrderNotFound as exc:
            display.error(str(exc))
            continue
        display.show_response(response)
        decision, reason = get_user_input()
        stored = None
        if decision:
            stored = await processor.store_decision(
                StoreDecisionRequest(invoice_id=invoice.invoice_id, human_decision=decision, human_reason=reason))
            display.show_stored(stored)
        rows.append((response, decision, stored))
    if rows:
        display.show_summary(rows)
    return 0


def _pause() -> bool:
    try:
        return input("\n  Press Enter for the next invoice (q to stop)... ").strip().lower() != "q"
    except EOFError:
        return False


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # ₹ and box drawing on Windows consoles
    configure_logging(fmt=f"{display.INDENT}· %(message)s")
    try:
        return asyncio.run(run(parse_args(argv)))
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
