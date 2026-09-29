"""The real data/ folders (not the test fixtures) and the script that builds data/real/."""

import json
import random
import re

import pytest

from app.config import ROOT, load_settings
from app.models import Invoice, PurchaseOrder, Vendor
from app.storage.reference import ReferenceData, load_invoices
from scripts import download_real_data as real

DATASETS = [
    (ROOT / "data", "demo_scenario.json"),
    (ROOT / "data", "test_invoices.json"),
    (ROOT / "data" / "real", "invoices.json"),
    (ROOT / "data" / "synthetic", "invoices.json"),
]
IDS = ["demo_scenario", "test_invoices", "real", "synthetic"]


def raw(path):
    return json.loads(path.read_text(encoding="utf-8"))


def no_nulls(record: dict) -> bool:
    return all(value is not None for value in record.values())


@pytest.mark.parametrize("folder, invoices_file", DATASETS, ids=IDS)
def test_every_record_validates_with_no_nulls(folder, invoices_file):
    for name, model in (("vendors.json", Vendor), ("purchase_orders.json", PurchaseOrder), (invoices_file, Invoice)):
        records = raw(folder / name)
        assert records, f"{folder / name} is empty"
        for record in records:
            assert no_nulls(record), record
            model.model_validate(record)  # positive numbers, ISO dates


@pytest.mark.parametrize("folder, invoices_file", DATASETS, ids=IDS)
def test_every_invoice_resolves_to_its_po_and_quotes_its_price(folder, invoices_file):
    reference = ReferenceData.load(folder, folder / invoices_file)
    for invoice in reference.invoices:
        po = reference.po_for(invoice)
        assert po is not None, f"no PO for {invoice.invoice_id} ({invoice.vendor})"
        assert invoice.po_price is None or invoice.po_price == po.expected_price, invoice.invoice_id


@pytest.mark.parametrize("folder, invoices_file", DATASETS, ids=IDS)
def test_po_lookup_survives_shuffling(folder, invoices_file):
    reference = ReferenceData.load(folder, folder / invoices_file)
    expected = {i.invoice_id: reference.po_for(i).po_id for i in reference.invoices}
    rng = random.Random(7)
    vendors, pos = list(reference.vendors.items()), list(reference.purchase_orders)
    rng.shuffle(vendors)
    rng.shuffle(pos)
    shuffled = ReferenceData(dict(vendors), pos, reference.invoices)
    assert {i.invoice_id: shuffled.po_for(i).po_id for i in reference.invoices} == expected


def test_the_app_loads_the_real_data_dir(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "data")
    settings = load_settings()
    assert settings.queue_file() == ROOT / "data" / "demo_scenario.json"
    assert len(ReferenceData.load(settings.data_dir, settings.queue_file()).invoices) == 4


def test_demo_scenario_is_exactly_the_story():
    reference = ReferenceData.load(ROOT / "data", ROOT / "data" / "demo_scenario.json")
    story = [(i.invoice_id, i.vendor, i.invoice_price) for i in reference.invoices]
    assert story == [("INV001", "ABC Pharma", 550), ("INV002", "ABC Pharma", 550),
                     ("INV003", "XYZ Pharma", 550), ("INV004", "ABC Pharma", 600)]
    for invoice in reference.invoices:
        po = reference.po_for(invoice)
        assert (po.expected_price, po.expected_quantity) == ((500, 100) if invoice.vendor == "ABC Pharma" else (500, 50))
        assert invoice.quantity == po.expected_quantity  # only the price differs from the PO


def test_sources_lists_each_external_dataset():
    sources = (ROOT / "data" / "SOURCES.md").read_text(encoding="utf-8")
    for heading in re.findall(r"^### (.+)$", sources, flags=re.MULTILINE):
        section = sources.split(f"### {heading}", 1)[1].split("\n### ", 1)[0]
        assert "**Name:**" in section and "**License:**" in section and "https://" in section, heading
    for mirror in real.KAGGLE_SLUGS[:2] + ["jrcinco/supply-chain-shipment-price-data"]:
        assert mirror in sources


# ── download_real_data.py ────────────────────────────────────────────────────

SCMS_SAMPLE = """\
ID,PO / SO #,PO Sent to Vendor Date,Vendor,Item Description,Pack Price,Line Item Quantity,Line Item Value,Delivered to Client Date,Manufacturing Site
1,SCMS-1,2-Dec-14,HETERO LABS LIMITED,Drug A 30 Tabs,10.00,100,1000,2-Jan-15,Hetero Unit III Hyderabad IN
2,SCMS-2,Date Not Captured,HETERO LABS LIMITED,Drug A 30 Tabs,10.00,50,500,9-Feb-15,Hetero Unit III Hyderabad IN
3,SCMS-3,1-Feb-15,HETERO LABS LIMITED,Drug A 30 Tabs,11.00,20,220,3-Mar-15,Hetero Unit III Hyderabad IN
4,SCMS-4,1-Feb-15,SCMS from RDC,Drug A 30 Tabs,10.00,10,100,3-Mar-15,Hetero Unit III Hyderabad IN
5,SCMS-5,1-Feb-15,"Orgenics, Ltd",Test kit,29.00,10,290,4-Mar-15,Inverness Japan
6,SCMS-6,1-Feb-15,CIPLA LIMITED,Drug B,0,10,0,5-Mar-15,"Cipla, Goa, India"
7,SCMS-7,1-Feb-15,CIPLA LIMITED,Drug B,5.00,10,50,Date Not Captured,"Cipla, Goa, India"
8,SCMS-8,1-Feb-15,CIPLA LIMITED,Drug B,5.00,10,80,6-Mar-15,"Cipla, Goa, India"
"""


@pytest.mark.parametrize("raw_name, clean", [
    ("MYLAN LABORATORIES LTD (FORMERLY MATRIX LABORATORIES)", "Mylan Laboratories"),
    ("Aurobindo Pharma Limited", "Aurobindo Pharma"), ("CIPLA LIMITED", "Cipla"),
    ("Premier Medical Corporation Ltd.", "Premier Medical Corporation"),
    ("Aurobindo Pharam Limited", "Aurobindo Pharma"),  # a misspelling in the source
])
def test_vendor_names_are_cleaned(raw_name, clean):
    assert real.clean_vendor_name(raw_name) == clean


@pytest.mark.parametrize("vendor, site, indian", [
    ("HETERO LABS LIMITED", "Hetero Unit III Hyderabad IN", True),
    ("S. BUYS WHOLESALER", "Aurobindo Unit III, India", False),  # distributor, not the manufacturer
    ("CHEMBIO DIAGNOSTIC SYSTEMS, INC.", "Chembio Diagnostics Sys. Inc.", False),  # "Inc." is not "IN"
])
def test_indian_manufacturer_detection(vendor, site, indian):
    assert real.is_indian_manufacturer(vendor, site) is indian


def test_contract_price_is_the_most_common_price_that_year():
    def line(price, day, year=2015):
        return real.PurchaseLine("1", "", "Hetero Labs", "Drug A", price, 1, real.date(year, 1, day), None, True)

    key = ("Hetero Labs", "Drug A", 2015)
    assert real.contract_prices([line(4.67, 1), line(4.51, 2), line(4.51, 3)]) == {key: 4.51}
    assert real.contract_prices([line(3.0, 2), line(2.5, 1)]) == {key: 2.5}  # tie: earliest
    # Prices drift over the years: each year has its own contract price.
    assert real.contract_prices([line(9.0, 1, 2008), line(9.0, 2, 2008), line(4.5, 1)]) == {
        ("Hetero Labs", "Drug A", 2008): 9.0, key: 4.5}


def test_the_real_data_keeps_every_indian_manufacturer_line():
    invoices = raw(ROOT / "data" / "real" / "invoices.json")
    assert len(invoices) > 1500
    vendors = {i["vendor"] for i in invoices}
    assert "Aurobindo Pharam" not in vendors and "Aurobindo Pharma" in vendors  # the source's typo, merged


def test_script_builds_a_consistent_dataset_folder(tmp_path, capsys):
    source, out = tmp_path / "scms.csv", tmp_path / "real"
    source.write_text(SCMS_SAMPLE, encoding="utf-8")
    assert real.main(["--csv", str(source), "--output-dir", str(out), "--usd-inr", "100"]) == 0

    reference = ReferenceData.load(out, out / "invoices.json")
    assert [i.invoice_id for i in reference.invoices] == ["INV00001", "INV00002", "INV00003"]
    assert [(i.po_price, i.invoice_price) for i in reference.invoices] == [(1000, 1000), (1000, 1000), (1000, 1100)]
    assert [reference.po_for(i).po_date for i in reference.invoices] == ["2014-12-02", "2015-02-09", "2015-02-01"]
    assert reference.vendor("Hetero Labs").historical_prices == [1000, 1100]
    out_text = capsys.readouterr().out
    for reason in ("internal warehouse transfer", "zero price", "unparseable date", "line value"):
        assert reason in out_text

    assert real.main(["--csv", str(source), "--output-dir", str(out)]) == 0  # exists: left alone
    assert "already exists" in capsys.readouterr().out


def test_script_maps_other_column_names(tmp_path):
    source, out = tmp_path / "other.csv", tmp_path / "real"
    source.write_text("Invoice No,Supplier,Product,Unit Price,Qty,Invoice Date\n"
                      "A1,Acme Traders,Widget,2.5,4,2024-01-15\nA2,Acme Traders,Widget,2.5,6,2024-02-15\n", encoding="utf-8")
    assert real.main(["--csv", str(source), "--output-dir", str(out), "--usd-inr", "1"]) == 0
    assert [(i.invoice_id, i.vendor, i.quantity) for i in load_invoices(out / "invoices.json")] == [
        ("INVA1", "Acme Traders", 4), ("INVA2", "Acme Traders", 6)]
