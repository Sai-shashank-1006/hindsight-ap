"""Download real purchase data and convert it to PaySage's invoice schema.

Source: USAID's SCMS Delivery History dataset: 10,324 real purchase lines for HIV/AIDS medicines
and test kits, 2006-2015. Many come straight from Indian manufacturers such as Aurobindo Pharma and
Hetero Labs (both Hyderabad), Cipla, Mylan (Nashik) and Strides. Tried in order: Kaggle (this public
dataset needs no account), then a GitHub mirror. There is no HuggingFace copy.

What is real and what is derived:
- vendor, item, invoice_price (price per pack), quantity (packs) and invoice_date (delivery date)
  are real values from each purchase line.
- po_price is derived. The data has one price per line, not a PO price and an invoice price, so the
  PO price is the vendor's contract price for that item that year: the price it billed most often
  in that calendar year. Lines billed at any other price become price mismatches. (Per year, because
  prices drift over the nine years; one price for the whole period would flag old lines wrongly.)
- Prices are converted from USD to INR at one fixed rate (--usd-inr).

Writes a complete dataset folder, data/real/: invoices.json, purchase_orders.json (one PO per
invoice, at the contract price) and vendors.json. Serve it with DATASET=real in .env.

    python -m scripts.download_real_data                 # writes data/real/
    python -m scripts.download_real_data --limit 150 --force    # only the most recent 150 lines
    python cli.py --invoices data/real/invoices.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

import requests

from app.agent.rules import PRICE_TOLERANCE, price_severity, variance_percent
from app.config import ROOT
from app.models import Invoice, PurchaseOrder, Vendor, format_money, normalize_vendor
from app.storage.reference import ReferenceData

KAGGLE_SLUGS = [
    "apoorvwatsky/supply-chain-shipment-pricing-data",
    "divyeshardeshana/supply-chain-shipment-pricing-data",
    "sawandikirby/supply-chain-shipment-pricing-data",
]
GITHUB_CSV = ("https://raw.githubusercontent.com/jrcinco/supply-chain-shipment-price-data/"
              "master/SCMS_Delivery_History_Dataset.csv")
CACHE_DIR = Path.home() / ".cache" / "hindsight-ap"
DATASET_NAME = "USAID SCMS Delivery History"

# First matching column wins. Names are compared lowercased with non-letters removed,
# so "PO / SO #" becomes "poso" and "Line Item Quantity" becomes "lineitemquantity".
COLUMN_SYNONYMS = {
    "vendor": ["vendor", "vendorname", "supplier", "suppliername", "seller"],
    "price": ["packprice", "invoiceprice", "unitprice", "price", "rate"],
    "quantity": ["lineitemquantity", "quantity", "qty", "units"],
    "date": ["deliveredtoclientdate", "invoicedate", "deliverydate", "date", "orderdate"],
    "item": ["itemdescription", "item", "product", "productname", "description", "stockcode"],
    "value": ["lineitemvalue", "invoicetotal", "amount", "linetotal", "total"],
    "site": ["manufacturingsite", "origin", "country"],
    "id": ["id", "invoiceid", "invoiceno", "invoicenumber"],
    "po": ["poso", "ponumber", "po", "poid"],
    "po_date": ["posenttovendordate", "podate"],
}
REQUIRED = ("vendor", "price", "quantity", "date")
DATE_FORMATS = ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y")

# Indian manufacturing sites: city/country names, or the "IN" country code as a whole word.
INDIAN_PLACE = re.compile(
    r"\b(india|hyderabad|nashik|goa|verna|bangalore|bengaluru|pune|hinjwadi|mumbai|hosur|ahmedabad|"
    r"chennai|baddi|jadcherla|patalganga|kurkumbh|paonta)\b", re.IGNORECASE)
INDIA_CODE = re.compile(r"\bIN\b")
# Words too common in company names to identify one.
GENERIC_WORDS = {"limited", "private", "pharma", "pharmaceutical", "pharmaceuticals", "laboratories",
                 "labs", "industries", "formerly", "corporation", "company", "medical", "south", "africa"}
LEGAL_SUFFIX = re.compile(r"[\s,.]+(limited|ltd|pvt|private|inc|plc|llc|co|corp)\.?$", re.IGNORECASE)
# Misspellings in the source data, after cleaning.
VENDOR_ALIASES = {"Aurobindo Pharam": "Aurobindo Pharma"}


@dataclass
class PurchaseLine:
    """One cleaned source row. Prices are in the source currency (USD)."""

    source_id: str
    po_number: str
    vendor: str
    item: str
    price: float
    quantity: int
    day: date
    value: Optional[float]
    indian: bool
    po_day: Optional[date] = None  # when the PO was sent, if recorded


# ── Download ─────────────────────────────────────────────────────────────────

def fetch_dataset() -> Optional[Tuple[Path, str]]:
    """Returns (csv path, source label), trying Kaggle first, then GitHub."""
    found = fetch_from_kaggle() or fetch_from_github()
    if not found:
        print_setup_help()
    return found


def kaggle_credentials() -> Optional[str]:
    token = Path(os.getenv("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle")) / "kaggle.json"
    if token.exists():
        return str(token)
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return "KAGGLE_USERNAME / KAGGLE_KEY"
    return None


def fetch_from_kaggle() -> Optional[Tuple[Path, str]]:
    try:
        import kagglehub
    except ImportError:
        print("✗ kagglehub is not installed (pip install kagglehub). Skipping Kaggle.")
        return None
    credentials = kaggle_credentials()
    if credentials:
        print(f"✓ Found Kaggle credentials: {credentials}")
    else:
        print("• No kaggle.json found. Trying anonymous download: public datasets don't need an account.")
    for slug in KAGGLE_SLUGS:
        print(f"• Kaggle: downloading {slug}")
        try:
            folder = Path(kagglehub.dataset_download(slug))
        except Exception as exc:  # network, auth, dataset removed
            print(f"  ✗ {type(exc).__name__}: {str(exc)[:160]}")
            continue
        csv_files = sorted(folder.rglob("*.csv"))
        if csv_files:
            print(f"✓ Downloaded: {slug} ({csv_files[0].name})")
            return csv_files[0], f"Kaggle {slug}"
        print(f"  ✗ No CSV file in {folder}")
    return None


def fetch_from_github() -> Optional[Tuple[Path, str]]:
    target = CACHE_DIR / "SCMS_Delivery_History_Dataset.csv"
    if target.exists():
        print(f"✓ Using cached GitHub copy: {target}")
        return target, "GitHub jrcinco/supply-chain-shipment-price-data"
    print("• GitHub: downloading jrcinco/supply-chain-shipment-price-data")
    try:
        response = requests.get(GITHUB_CSV, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ✗ {exc}")
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    print(f"✓ Downloaded: GitHub mirror ({len(response.content) // 1024} KB)")
    return target, "GitHub jrcinco/supply-chain-shipment-price-data"


def print_setup_help() -> None:
    print("""
✗ Could not download the dataset.

  Kaggle usually works without an account. If it doesn't:
    1. Create a free account at https://www.kaggle.com/
    2. Settings → API → Create New Token. This downloads kaggle.json
    3. Save it as %USERPROFILE%\\.kaggle\\kaggle.json (Windows) or ~/.kaggle/kaggle.json
    4. Run this script again

  Or download the CSV yourself from
    https://www.kaggle.com/datasets/apoorvwatsky/supply-chain-shipment-pricing-data
  and run:  python -m scripts.download_real_data --csv path/to/file.csv""")


# ── Read and map columns ─────────────────────────────────────────────────────

def read_csv(path: Path) -> List[Dict[str, str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")  # the Kaggle copy is not valid UTF-8
    return list(csv.DictReader(io.StringIO(text, newline="")))  # newline="" handles \r, \n and \r\n files


def normalize(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def map_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    """Our field → the dataset's column name (None if the dataset has no such column)."""
    by_normal = {normalize(h): h for h in headers}
    mapping = {}
    for field, synonyms in COLUMN_SYNONYMS.items():
        mapping[field] = next((by_normal[s] for s in synonyms if s in by_normal), None)
    return mapping


# ── Clean ────────────────────────────────────────────────────────────────────

def parse_number(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.\-]", "", text or "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(text: str) -> Optional[date]:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime((text or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def is_indian_manufacturer(vendor: str, site: str) -> bool:
    """The site is in India and the vendor is the company that runs it, not a distributor."""
    if not (INDIAN_PLACE.search(site) or INDIA_CODE.search(site)):
        return False
    words = {w for w in re.findall(r"[a-z]+", vendor.lower()) if len(w) > 3 and w not in GENERIC_WORDS}
    return any(w in site.lower() for w in words)


def clean_vendor_name(name: str) -> str:
    """'MYLAN LABORATORIES LTD (FORMERLY MATRIX LABORATORIES)' → 'Mylan Laboratories'."""
    name = " ".join(re.sub(r"\(.*?\)", "", name).split()).strip(" ,.")
    previous = None
    while previous != name:
        previous, name = name, LEGAL_SUFFIX.sub("", name).strip(" ,.")
    name = name.title() if name.isupper() or name.islower() else name
    return VENDOR_ALIASES.get(name, name)


def clean_rows(rows: List[Dict[str, str]], columns: Dict[str, Optional[str]]) -> Tuple[List[PurchaseLine], Counter]:
    lines, dropped = [], Counter()
    for number, row in enumerate(rows, 1):
        get = lambda field: (row.get(columns[field]) or "").strip() if columns[field] else ""
        vendor = get("vendor")
        price, quantity, value = parse_number(get("price")), parse_number(get("quantity")), parse_number(get("value"))
        day = parse_date(get("date"))
        if not vendor or vendor.upper().startswith("SCMS FROM RDC"):
            dropped["no external vendor (internal warehouse transfer)"] += 1
        elif price is None or price <= 0:
            dropped["missing or zero price"] += 1
        elif quantity is None or quantity <= 0 or quantity != int(quantity):
            dropped["missing or fractional quantity"] += 1
        elif day is None:
            dropped["missing or unparseable date"] += 1
        elif value and abs(value - price * quantity) > 0.02 * value:
            dropped["line value ≠ quantity × price"] += 1
        else:
            lines.append(PurchaseLine(
                source_id=get("id") or str(number),
                po_number=get("po"),
                vendor=clean_vendor_name(vendor),
                item=get("item") or "(item not recorded)",
                price=price,
                quantity=int(quantity),
                day=day,
                value=value,
                indian=is_indian_manufacturer(vendor, get("site")),
                po_day=parse_date(get("po_date")),
            ))
    return drop_price_outliers(lines, dropped), dropped


def drop_price_outliers(lines: List[PurchaseLine], dropped: Counter) -> List[PurchaseLine]:
    """Prices under a fifth or over five times the vendor's usual price for the item are data errors."""
    groups = defaultdict(list)
    for line in lines:
        groups[(line.vendor, line.item)].append(line.price)
    medians = {key: median(prices) for key, prices in groups.items()}
    kept = []
    for line in lines:
        m = medians[(line.vendor, line.item)]
        if m / 5 <= line.price <= m * 5:
            kept.append(line)
        else:
            dropped["price outlier (under 1/5 or over 5× the item's median)"] += 1
    return kept


# ── Convert ──────────────────────────────────────────────────────────────────

def contract_prices(lines: List[PurchaseLine]) -> Dict[Tuple[str, str, int], float]:
    """Per vendor, item and calendar year, the price billed most often. Ties go to the earliest price billed."""
    by_group = defaultdict(list)
    for line in sorted(lines, key=lambda l: l.day):
        by_group[(line.vendor, line.item, line.day.year)].append(line.price)
    result = {}
    for key, prices in by_group.items():
        counts = Counter(prices)
        top = max(counts.values())
        result[key] = next(p for p in prices if counts[p] == top)
    return result


def build_dataset(lines: List[PurchaseLine], usd_inr: float) -> Tuple[List[dict], List[dict], List[dict]]:
    """(invoices, purchase_orders, vendors). Each line gets its own PO record: the real ordered
    quantity, at the vendor's contract price for the item. The invoice's po_price equals it."""
    reference = contract_prices(lines)
    invoices, pos, billed = [], [], defaultdict(set)
    for line in sorted(lines, key=lambda l: (l.day, l.source_id)):
        key = f"{int(line.source_id):05d}" if line.source_id.isdigit() else line.source_id
        po_price = round(reference[(line.vendor, line.item, line.day.year)] * usd_inr, 2)
        invoice_price = round(line.price * usd_inr, 2)
        pos.append({
            "po_id": f"PO{key}", "vendor": line.vendor, "expected_price": po_price,
            "expected_quantity": line.quantity, "po_date": (line.po_day or line.day).isoformat(), "item": line.item,
        })
        record = {
            "invoice_id": f"INV{key}", "po_id": f"PO{key}", "vendor": line.vendor, "po_price": po_price,
            "invoice_price": invoice_price, "quantity": line.quantity, "invoice_date": line.day.isoformat(),
            "item": line.item,
            "source_ref": f"{DATASET_NAME} row {line.source_id}" + (f", {line.po_number}" if line.po_number else ""),
        }
        if line.value:
            record["invoice_total"] = round(line.value * usd_inr, 2)
        invoices.append(record)
        billed[line.vendor].add(invoice_price)
    vendors = [{"name": name, "payment_terms": "not recorded in source data", "historical_prices": sorted(prices)}
               for name, prices in sorted(billed.items())]
    return invoices, pos, vendors


def validate(invoices: List[dict], pos: List[dict], vendors: List[dict]) -> List[Invoice]:
    """Everything must parse as the app's models, and every invoice must resolve to its own PO."""
    json.loads(json.dumps([invoices, pos, vendors]))
    ids = Counter(r["invoice_id"] for r in invoices)
    duplicates = [i for i, n in ids.items() if n > 1]
    if duplicates:
        raise ValueError(f"duplicate invoice IDs: {duplicates[:5]}")
    reference = ReferenceData({normalize_vendor(v["name"]): Vendor.model_validate(v) for v in vendors},
                              [PurchaseOrder.model_validate(p) for p in pos])
    parsed = [Invoice.model_validate(r) for r in invoices]
    for invoice in parsed:
        po = reference.po_for(invoice)
        if po is None or po.expected_price != invoice.po_price:
            raise ValueError(f"{invoice.invoice_id} does not resolve to a PO with its po_price")
    return parsed


# ── Report ───────────────────────────────────────────────────────────────────

def print_summary(invoices: List[Invoice], records: List[dict], source: str, usd_inr: float, output_dir: Path) -> None:
    vendors = Counter(i.vendor for i in invoices)
    prices = [i.invoice_price for i in invoices]
    quantities = [i.quantity for i in invoices]
    dates = sorted(i.invoice_date for i in invoices)
    off_contract = [i for i in invoices if abs(i.invoice_price - i.po_price) > PRICE_TOLERANCE]
    severities = Counter(price_severity(variance_percent(i.po_price, i.invoice_price)).value for i in off_contract)

    print("\nSummary")
    print(f"- Source: {source} ({DATASET_NAME})")
    print(f"- Invoices: {len(invoices)}, each with its own PO record")
    print(f"- Vendors: {len(vendors)} unique companies: " + ", ".join(f"{v} ({n})" for v, n in vendors.most_common()))
    print(f"- Date range: {dates[0]} to {dates[-1]}")
    print(f"- Price range: {format_money(min(prices))} - {format_money(max(prices))} per pack "
          f"(converted from USD at ₹{usd_inr:g}/USD)")
    print(f"- Quantity range: {min(quantities):,} - {max(quantities):,} packs")
    print(f"- Against contract price: {len(invoices) - len(off_contract)} match, {len(off_contract)} price mismatches"
          + (f" ({', '.join(f'{s} {n}' for s, n in sorted(severities.items()))})" if off_contract else ""))

    # Same vendor, item and off-contract price more than once: the second recalls the first.
    repeats = defaultdict(list)
    for inv in off_contract:
        repeats[(inv.vendor, inv.item, inv.po_price, inv.invoice_price)].append(inv.invoice_id)
    candidates = sorted(((k, ids) for k, ids in repeats.items() if len(ids) > 1), key=lambda kv: -len(kv[1]))
    if candidates:
        print("\nLearning-loop candidates (same vendor, item and off-contract price, billed more than once):")
        for (vendor, item, po_price, price), ids in candidates[:3]:
            more = f" (+{len(ids) - 2} more)" if len(ids) > 2 else ""
            print(f"- {vendor} · {item[:40]} · {format_money(price)} vs contract {format_money(po_price)} "
                  f"({variance_percent(po_price, price):g}%): {ids[0]}, {ids[1]}{more}")
        (_, ids) = candidates[0]
        try:
            shown = (output_dir / "invoices.json").resolve().relative_to(ROOT)  # cli.py resolves it from there
        except ValueError:
            shown = output_dir / "invoices.json"
        print(f"  Try:  python cli.py --fresh --invoices {shown.as_posix()} {ids[0]} {ids[1]}")

    print("\nSample records:")
    for record in records[:3]:
        print(json.dumps(record, ensure_ascii=False, indent=2))


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download real purchase data into PaySage's schema.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "real",
                        help="dataset folder to write: invoices.json, purchase_orders.json, vendors.json")
    parser.add_argument("--limit", type=int, default=0, help="keep only the most recent N purchase lines (default: all)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing dataset")
    parser.add_argument("--csv", type=Path, help="use a local CSV instead of downloading")
    parser.add_argument("--usd-inr", type=float, default=83.0, help="USD→INR conversion rate (default 83)")
    parser.add_argument("--all-vendors", action="store_true", help="keep non-Indian vendors too")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    target = args.output_dir / "invoices.json"

    if target.exists() and not args.force:
        try:
            count = len(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            count = "unreadable"
        print(f"✓ {target} already exists ({count} invoices). Nothing to do; use --force to rebuild it.")
        return 0

    if args.csv:
        if not args.csv.is_file():
            print(f"✗ {args.csv} not found")
            return 1
        found = (args.csv, f"local file {args.csv.name}")
    else:
        found = fetch_dataset()
    if not found:
        return 1
    csv_path, source = found

    rows = read_csv(csv_path)
    columns = map_columns(list(rows[0].keys()) if rows else [])
    missing = [f for f in REQUIRED if not columns[f]]
    if missing:
        print(f"✗ {csv_path.name} has no column for: {', '.join(missing)}. Columns found: {list(rows[0].keys()) if rows else []}")
        return 1
    print(f"✓ Processing {len(rows):,} records from {csv_path.name}")
    print("  Columns: " + ", ".join(f"{field} ← '{col}'" for field, col in columns.items() if col))

    lines, dropped = clean_rows(rows, columns)
    print(f"✓ Cleaned: kept {len(lines):,}, dropped {sum(dropped.values()):,}")
    for reason, n in dropped.most_common():
        print(f"    {n:6,}  {reason}")

    if not args.all_vendors and columns["site"]:
        lines = [line for line in lines if line.indian]
        indian = sorted({line.vendor for line in lines})
        print(f"✓ Indian manufacturers selling direct: {len(lines):,} lines from {len(indian)} companies")
    if not lines:
        print("✗ No usable records left after cleaning.")
        return 1

    selected = sorted(lines, key=lambda l: l.day)[-args.limit:] if args.limit > 0 else sorted(lines, key=lambda l: l.day)
    invoices, pos, vendors = build_dataset(selected, args.usd_inr)
    try:
        parsed = validate(invoices, pos, vendors)
    except ValueError as exc:
        print(f"✗ Validation failed: {exc}")
        return 1
    print("✓ Reformatted to schema; every invoice validates and resolves to its PO record")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in (("invoices.json", invoices), ("purchase_orders.json", pos), ("vendors.json", vendors)):
        (args.output_dir / name).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Saved {len(invoices)} invoices, {len(pos)} POs and {len(vendors)} vendors to {args.output_dir}")

    print_summary(parsed, invoices, source, args.usd_inr, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
