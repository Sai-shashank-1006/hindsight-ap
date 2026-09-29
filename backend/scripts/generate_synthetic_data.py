"""Generate a synthetic accounts-payable dataset: Indian vendors, purchase orders and invoices,
with the exception patterns an AP team really sees.

Everything here is made up: vendor names are invented, contacts use the reserved .example domain,
and every invoice says so in source_ref. The generator is deterministic: the same --seed always
writes the same files.

Each vendor follows one or more patterns:
- steady            bills exactly what the PO says.
- contract_revision a price change takes effect on a date, but the buyer's price master is updated
                    late, so POs keep the old price for a while and the same PRICE_MISMATCH repeats.
                    A reviewer approves the first one with the reason; Hindsight recalls it for the
                    next ones. This is the learning loop at scale.
- recurring_overbill bills an unagreed rate, and bills the same wrong rate again later
                    (the first rejection becomes a verified rejection).
- one_off_overbill  now and then bills 11-19% over the PO price, a different amount each time.
- carton_rounding   ships full cartons only, so it invoices a little less than ordered, and the same
                    shortfall repeats for the standard order sizes (QUANTITY_MISMATCH).
- price_rounding    paise-level differences from the PO price (INFO).
- extra_trip        a carrier bills one trip more than the PO (QUANTITY_MISMATCH).

labels.json records, per invoice, which pattern produced it and the decision a careful reviewer
would make, so the data can be used to evaluate the agent. The app never reads it.

    python -m scripts.generate_synthetic_data                        # writes data/synthetic/
    python -m scripts.generate_synthetic_data --invoices 1000 --seed 11 --force
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from app.agent.rules import RuleEngine, variance_percent
from app.config import ROOT
from app.models import Invoice, PurchaseOrder, Vendor, format_money, normalize_vendor
from app.storage.reference import ReferenceData

DEFAULT_OUTPUT = ROOT / "data" / "synthetic"
SOURCE = "Synthetic (generate_synthetic_data.py, seed {seed})"


@dataclass(frozen=True)
class Item:
    name: str
    price: float  # ₹ per unit at the start of the period
    order_sizes: Tuple[int, ...]  # the buyer's standard order quantities
    carton: int = 1  # units per carton, for carton_rounding
    wrong_price: Optional[float] = None  # the unagreed rate, for recurring_overbill


@dataclass(frozen=True)
class Revision:
    effective: date
    factor: float  # new price = old price × factor
    reason: str
    master_lag_days: int = 45  # how long the buyer's POs keep the old price


@dataclass(frozen=True)
class Profile:
    name: str
    city: str
    payment_terms: str
    weight: int  # relative invoice volume
    items: Tuple[Item, ...]
    patterns: Tuple[str, ...]
    revision: Optional[Revision] = None

    @property
    def contact(self) -> str:
        return f"accounts@{normalize_vendor(self.name).split()[0]}.example"


PROFILES: Tuple[Profile, ...] = (
    Profile("Deccanvale Lifesciences", "Hyderabad", "Net 45", 14, (
        Item("Paracetamol 650mg tablets, strip of 15", 30.00, (2000, 5000, 10000)),
        Item("Amoxicillin 500mg capsules, strip of 10", 72.00, (1000, 2000, 5000)),
        Item("Metformin 500mg tablets, strip of 20", 28.50, (2000, 5000)),
    ), ("contract_revision", "price_rounding"),
        Revision(date(2026, 4, 1), 1.10, "API cost increase: 10% price revision effective 1 April 2026")),
    Profile("Godavara Generics", "Rajahmundry", "Net 30", 10, (
        Item("Azithromycin 500mg tablets, strip of 3", 68.00, (1000, 2000)),
        Item("Cetirizine 10mg tablets, strip of 10", 14.00, (5000, 10000)),
        Item("Pantoprazole 40mg tablets, strip of 15", 95.00, (1000, 2000)),
    ), ("steady",)),
    Profile("Kakatiya Labcraft", "Warangal", "Net 30", 9, (
        Item("Nitrile examination gloves, box of 100", 385.00, (100, 250, 500), carton=24),
        Item("Micropipette tips 200µl, rack of 96", 450.00, (50, 100, 200), carton=12),
        Item("Petri dishes 90mm, pack of 20", 320.00, (100, 200), carton=30),
    ), ("carton_rounding",)),
    Profile("Charminar Cartons & Co.", "Hyderabad", "Net 60", 10, (
        Item("Printed mono carton, 10-strip pack", 4.20, (20000, 50000)),
        Item("Corrugated shipper box, 5-ply", 42.00, (2000, 5000)),
        Item("Blister foil roll, 250mm x 1000m", 3850.00, (20, 50)),
    ), ("price_rounding",)),
    Profile("Musirex Chemicals", "Hyderabad", "Net 30", 8, (
        Item("Isopropyl alcohol 70%, 5L can", 1150.00, (40, 80, 120), wrong_price=1320.00),
        Item("Sodium hypochlorite 5%, 20L can", 980.00, (20, 50), wrong_price=1090.00),
        Item("Ethanol 99.9% AR grade, 2.5L", 1650.00, (10, 24), wrong_price=1780.00),
    ), ("recurring_overbill",)),
    Profile("Banjara Deskline Office Supplies", "Hyderabad", "Net 15", 7, (
        Item("A4 copier paper 75gsm, ream of 500", 285.00, (100, 200, 500)),
        Item("Toner cartridge 12A compatible", 2450.00, (10, 20)),
        Item("Box files, pack of 10", 650.00, (20, 50)),
    ), ("steady",)),
    Profile("Hitecvale IT Services", "Hyderabad", "Net 30", 5, (
        Item("Laptop, 14-inch, Core i5, 16GB RAM", 58500.00, (5, 10, 20)),
        Item("Monitor, 27-inch IPS", 17800.00, (5, 10)),
        Item("Barcode scanner, 2D wireless", 4950.00, (10, 20)),
    ), ("contract_revision",),
        Revision(date(2026, 6, 1), 0.96, "Q2 price protection: prices cut 4% from 1 June 2026")),
    Profile("Coromandel Frostline Coldchain", "Chennai", "Net 30", 6, (
        Item("Vaccine carrier, 1.7L", 1250.00, (50, 100), carton=8),
        Item("Ice pack, 0.4L", 65.00, (500, 1000), carton=48),
        Item("Temperature data logger, USB", 3900.00, (10, 25)),
    ), ("carton_rounding", "price_rounding")),
    Profile("Sahyadri Suturecare", "Pune", "Net 45", 6, (
        Item("Absorbable suture 2-0, box of 12", 1840.00, (20, 50)),
        Item("Surgical gauze 10cm x 10cm, pack of 100", 340.00, (100, 200)),
        Item("Disposable syringe 5ml, box of 100", 560.00, (50, 100)),
    ), ("one_off_overbill",)),
    Profile("Narmada Polyform", "Vadodara", "Net 60", 7, (
        Item("HDPE bottle 100ml with CRC cap", 6.80, (20000, 50000)),
        Item("HDPE bottle 500ml with cap", 14.50, (10000, 20000)),
        Item("PP measuring cup 30ml", 1.20, (20000, 50000)),
    ), ("contract_revision",),
        Revision(date(2026, 5, 15), 1.06, "Polymer price revision: 6% increase effective 15 May 2026")),
    Profile("Krishnaveni Reagents", "Vijayawada", "Net 30", 6, (
        Item("Glucose reagent kit, 500 tests", 2150.00, (10, 20)),
        Item("Hemoglobin reagent, 1L", 1480.00, (10, 20)),
        Item("Urine test strips, bottle of 100", 720.00, (20, 50)),
    ), ("steady",)),
    Profile("Vindhyachal Freightways", "Nagpur", "Net 15", 6, (
        Item("Reefer truck trip, Hyderabad to Vijayawada", 18500.00, (4, 8)),
        Item("Full truck load, Hyderabad to Nagpur, 20ft", 32000.00, (2, 4)),
    ), ("contract_revision", "extra_trip"),
        Revision(date(2026, 7, 1), 1.08, "Diesel surcharge: 8% rate revision effective 1 July 2026")),
)

# How often each pattern changes an invoice (contract_revision and carton_rounding follow the dates
# and order sizes instead).
CHANCE = {"recurring_overbill": 0.22, "one_off_overbill": 0.15, "price_rounding": 0.18,
          "carton_rounding": 0.75, "extra_trip": 0.15}


@dataclass
class Line:
    profile: Profile
    item: Item
    po_date: date
    invoice_date: date
    po_price: float
    po_quantity: int
    invoice_price: float
    quantity: int
    scenario: str
    decision: str  # what a careful reviewer would decide
    reason: str


# ── Generate ─────────────────────────────────────────────────────────────────

def money(value: float) -> float:
    return round(value + 1e-9, 2)


def weekdays(start: date, end: date) -> List[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def price_on(item: Item, revision: Optional[Revision], day: date, lag: int = 0) -> float:
    """The item's contract price on a day. lag delays the change (the buyer's price master)."""
    if revision and day >= revision.effective + timedelta(days=lag):
        return money(item.price * revision.factor)
    return item.price


def make_line(profile: Profile, item: Item, invoice_day: date, rng: random.Random) -> Line:
    revision = profile.revision
    po_day = invoice_day - timedelta(days=rng.randint(7, 35))
    po_price = price_on(item, revision, po_day, revision.master_lag_days if revision else 0)
    po_quantity = rng.choice(item.order_sizes)
    line = Line(profile, item, po_day, invoice_day, po_price, po_quantity, po_price, po_quantity,
                "matches_po", "APPROVED", "Matches the PO price and quantity")
    patterns = profile.patterns

    billed = price_on(item, revision, invoice_day)
    if "contract_revision" in patterns and abs(billed - po_price) > 0.005:
        line.invoice_price, line.scenario, line.decision = billed, "contract_revision", "APPROVED"
        line.reason = f"{revision.reason}; the PO still carries the old price"
    elif "recurring_overbill" in patterns and item.wrong_price and rng.random() < CHANCE["recurring_overbill"]:
        line.invoice_price, line.scenario, line.decision = item.wrong_price, "recurring_overbill", "REJECTED"
        line.reason = f"{format_money(item.wrong_price)} was never agreed; the contract rate is {format_money(po_price)}"
    elif "one_off_overbill" in patterns and rng.random() < CHANCE["one_off_overbill"]:
        line.invoice_price = money(po_price * (1 + rng.randint(11, 19) / 100))
        line.scenario, line.decision = "one_off_overbill", "REJECTED"
        line.reason = f"Billed {format_money(line.invoice_price)} against the agreed {format_money(po_price)}"
    elif "price_rounding" in patterns and rng.random() < CHANCE["price_rounding"]:
        step = 0.05 if po_price < 100 else 0.5 if po_price < 1000 else 5.0
        line.invoice_price = money(po_price + step * rng.choice((1, 2, -1)))
        line.scenario, line.decision = "price_rounding", "APPROVED"
        line.reason = (f"Rounding difference of {format_money(abs(line.invoice_price - po_price))}/unit "
                       f"({variance_percent(po_price, line.invoice_price):g}%); accepted")

    if "carton_rounding" in patterns and item.carton > 1 and po_quantity % item.carton \
            and rng.random() < CHANCE["carton_rounding"]:
        line.quantity = po_quantity // item.carton * item.carton
        add(line, "carton_rounding", "APPROVED", f"Ships full cartons of {item.carton}: {line.quantity} of "
                                                 f"{po_quantity} delivered; pay for what was delivered")
    elif "extra_trip" in patterns and rng.random() < CHANCE["extra_trip"]:
        line.quantity = po_quantity + 1
        add(line, "extra_trip", "REJECTED", f"Billed {line.quantity} trips; the PO covers {po_quantity}")
    return line


def add(line: Line, scenario: str, decision: str, reason: str) -> None:
    """A quantity pattern on top of whatever the price did. Any rejection wins."""
    if line.scenario == "matches_po":
        line.scenario, line.decision, line.reason = scenario, decision, reason
        return
    line.scenario = f"{line.scenario}+{scenario}"
    line.decision = "REJECTED" if "REJECTED" in (line.decision, decision) else "APPROVED"
    line.reason = f"{line.reason}. {reason}"


def generate(invoices: int, seed: int, start: date, end: date) -> List[Line]:
    rng = random.Random(seed)
    days = weekdays(start, end)
    total_weight = sum(p.weight for p in PROFILES)
    lines = []
    for profile in PROFILES:
        count = max(1, round(invoices * profile.weight / total_weight))
        for day in sorted(rng.choice(days) for _ in range(count)):
            lines.append(make_line(profile, rng.choice(profile.items), day, rng))
    return sorted(lines, key=lambda l: (l.invoice_date, l.profile.name, l.item.name))


def build_dataset(lines: Sequence[Line], seed: int) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    """(invoices, purchase_orders, vendors, labels). Invoice and PO numbers follow date order."""
    source = SOURCE.format(seed=seed)
    po_numbers = {id(l): n for n, l in enumerate(sorted(lines, key=lambda l: (l.po_date, l.invoice_date)), 1)}
    invoices, pos, labels, billed = [], [], [], defaultdict(set)
    for number, line in enumerate(lines, 1):
        invoice_id, po_id = f"INV-2026-{number:04d}", f"PO-2026-{po_numbers[id(line)]:04d}"
        pos.append({"po_id": po_id, "vendor": line.profile.name, "expected_price": line.po_price,
                    "expected_quantity": line.po_quantity, "po_date": line.po_date.isoformat(),
                    "item": line.item.name})
        invoices.append({"invoice_id": invoice_id, "po_id": po_id, "vendor": line.profile.name,
                         "po_price": line.po_price, "invoice_price": line.invoice_price, "quantity": line.quantity,
                         "invoice_date": line.invoice_date.isoformat(), "item": line.item.name,
                         "invoice_total": money(line.invoice_price * line.quantity),
                         "source_ref": f"{source}: {line.scenario.replace('_', ' ')}"})
        labels.append({"invoice_id": invoice_id, "vendor": line.profile.name, "scenario": line.scenario,
                       "expected_decision": line.decision, "reason": line.reason})
        billed[line.profile.name].add(line.invoice_price)
    vendors = [{"name": p.name, "payment_terms": p.payment_terms, "contact": p.contact,
                "historical_prices": sorted(billed[p.name])} for p in PROFILES if billed[p.name]]
    return invoices, sorted(pos, key=lambda p: p["po_id"]), vendors, labels


def validate(invoices: List[dict], pos: List[dict], vendors: List[dict]) -> ReferenceData:
    """Everything parses as the app's models, and every invoice resolves to its own PO."""
    reference = ReferenceData({normalize_vendor(v["name"]): Vendor.model_validate(v) for v in vendors},
                              [PurchaseOrder.model_validate(p) for p in pos],
                              [Invoice.model_validate(i) for i in invoices])
    ids = Counter(i.invoice_id for i in reference.invoices)
    if any(n > 1 for n in ids.values()):
        raise ValueError("duplicate invoice IDs")
    for invoice in reference.invoices:
        po = reference.po_for(invoice)
        if po is None or po.expected_price != invoice.po_price:
            raise ValueError(f"{invoice.invoice_id} does not resolve to a PO with its po_price")
    return reference


# ── Report ───────────────────────────────────────────────────────────────────

def print_summary(reference: ReferenceData, labels: List[dict], output_dir: Path) -> None:
    engine = RuleEngine()
    found = {i.invoice_id: engine.detect_exceptions(i, reference.po_for(i)) for i in reference.invoices}
    with_exceptions = [i for i in reference.invoices if found[i.invoice_id]]
    kinds = Counter(f"{e.type.value} {e.severity.value}" for excs in found.values() for e in excs)
    dates = sorted(i.invoice_date for i in reference.invoices)
    print("\nSummary")
    print(f"- Invoices: {len(reference.invoices)}, each with its own PO; {len(reference.vendors)} vendors")
    print(f"- Date range: {dates[0]} to {dates[-1]}")
    print(f"- Exceptions: {len(with_exceptions)} invoices ({len(with_exceptions) / len(reference.invoices):.0%}): "
          + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
    print("- Scenarios: " + ", ".join(f"{s} {n}" for s, n in Counter(l["scenario"] for l in labels).most_common()))

    # The same vendor, exception type and invoiced amount more than once: the guardrail's evidence key.
    repeats = defaultdict(list)
    for invoice in with_exceptions:
        for exc in found[invoice.invoice_id]:
            repeats[(invoice.vendor, exc.type.value, exc.actual_value)].append(invoice.invoice_id)
    loops = sorted(((k, ids) for k, ids in repeats.items() if len(ids) > 1), key=lambda kv: -len(kv[1]))
    print(f"- Learning-loop chains: {len(loops)} (same vendor, exception and amount, seen more than once)")
    for (vendor, kind, amount), ids in loops[:4]:
        shown = format_money(amount) if kind == "PRICE_MISMATCH" else f"{amount:g} units"
        print(f"    {vendor} · {kind} at {shown}: {ids[0]}, {ids[1]}" + (f" (+{len(ids) - 2} more)" if len(ids) > 2 else ""))
    print(f"\nUse it:  DATA_DIR={output_dir.relative_to(ROOT).as_posix() if output_dir.is_relative_to(ROOT) else output_dir}"
          "  (or load it into MySQL: python -m scripts.db import synthetic)")


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate PaySage's synthetic AP dataset (Indian vendors).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--invoices", type=int, default=480, help="about how many invoices (default 480)")
    parser.add_argument("--seed", type=int, default=7, help="random seed (default 7)")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 5))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 25))
    parser.add_argument("--force", action="store_true", help="overwrite an existing dataset")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    if args.invoices < len(PROFILES) or args.end <= args.start:
        print(f"✗ Need at least {len(PROFILES)} invoices and --end after --start")
        return 1
    if (args.output_dir / "invoices.json").exists() and not args.force:
        print(f"✓ {args.output_dir / 'invoices.json'} already exists. Nothing to do; use --force to rebuild it.")
        return 0

    invoices, pos, vendors, labels = build_dataset(generate(args.invoices, args.seed, args.start, args.end), args.seed)
    try:
        reference = validate(invoices, pos, vendors)
    except ValueError as exc:
        print(f"✗ Validation failed: {exc}")
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in (("invoices.json", invoices), ("purchase_orders.json", pos),
                          ("vendors.json", vendors), ("labels.json", labels)):
        (args.output_dir / name).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Saved {len(invoices)} invoices, {len(pos)} POs, {len(vendors)} vendors and their labels to {args.output_dir}")
    print_summary(reference, labels, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
