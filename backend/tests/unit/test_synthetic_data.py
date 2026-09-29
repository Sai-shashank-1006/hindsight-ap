"""generate_synthetic_data.py and the data/synthetic/ it wrote."""

import json
from collections import Counter
from datetime import date

from app.agent.rules import RuleEngine
from app.config import ROOT
from app.models import Invoice
from app.storage.reference import ReferenceData
from scripts import generate_synthetic_data as synthetic

FOLDER = ROOT / "data" / "synthetic"
DEFAULTS = (480, 7, date(2026, 1, 5), date(2026, 9, 25))


def dataset(invoices=480, seed=7):
    return synthetic.build_dataset(synthetic.generate(invoices, seed, date(2026, 1, 5), date(2026, 9, 25)), seed)


def test_the_committed_files_are_exactly_what_the_generator_writes():
    invoices, pos, vendors, labels = synthetic.build_dataset(synthetic.generate(*DEFAULTS), DEFAULTS[1])
    for name, records in (("invoices.json", invoices), ("purchase_orders.json", pos), ("vendors.json", vendors),
                          ("labels.json", labels)):
        assert json.loads((FOLDER / name).read_text(encoding="utf-8")) == records, name


def test_same_seed_same_data_other_seed_other_data():
    assert dataset() == dataset()
    assert dataset()[0] != dataset(seed=8)[0]


def test_every_invoice_resolves_to_its_po_and_has_a_label():
    invoices, pos, vendors, labels = dataset()
    reference = synthetic.validate(invoices, pos, vendors)
    assert [label["invoice_id"] for label in labels] == [i.invoice_id for i in reference.invoices]
    assert all(i["source_ref"].startswith("Synthetic") for i in invoices)
    assert all(v["contact"].endswith(".example") for v in vendors)  # a reserved domain: never a real address


def test_the_exceptions_are_realistic_and_the_labels_agree_with_the_rules():
    labels = json.loads((FOLDER / "labels.json").read_text(encoding="utf-8"))
    reference = ReferenceData.load(FOLDER, FOLDER / "invoices.json")
    engine, by_id = RuleEngine(), {label["invoice_id"]: label for label in labels}
    flagged = 0
    for invoice in reference.invoices:
        found = engine.detect_exceptions(invoice, reference.po_for(invoice))
        label = by_id[invoice.invoice_id]
        assert bool(found) == (label["scenario"] != "matches_po"), label
        flagged += bool(found)
    assert 0.15 <= flagged / len(reference.invoices) <= 0.45
    scenarios = Counter(label["scenario"].split("+")[0] for label in labels)
    for pattern in ("contract_revision", "recurring_overbill", "one_off_overbill", "carton_rounding",
                    "price_rounding", "extra_trip"):
        assert scenarios[pattern] > 0, pattern
    decisions = {label["expected_decision"] for label in labels if "overbill" in label["scenario"]}
    assert decisions == {"REJECTED"}


def test_repeated_exceptions_give_hindsight_something_to_learn():
    """The guardrail's key: same vendor, exception type and invoiced amount, more than once."""
    reference, engine = ReferenceData.load(FOLDER, FOLDER / "invoices.json"), RuleEngine()
    keys = Counter((i.vendor, e.type, e.actual_value) for i in reference.invoices
                   for e in engine.detect_exceptions(i, reference.po_for(i)))
    chains = [key for key, n in keys.items() if n > 1]
    assert len(chains) >= 10
    assert any(vendor == "Deccanvale Lifesciences" for vendor, _, _ in chains)  # the contract revision repeats


def test_the_cli_writes_a_folder_and_leaves_it_alone_after(tmp_path, capsys):
    out = tmp_path / "synthetic"
    assert synthetic.main(["--output-dir", str(out), "--invoices", "60", "--seed", "3"]) == 0
    assert len([Invoice.model_validate(i) for i in json.loads((out / "invoices.json").read_text(encoding="utf-8"))]) >= 50
    assert "Learning-loop chains" in capsys.readouterr().out
    assert synthetic.main(["--output-dir", str(out)]) == 0
    assert "already exists" in capsys.readouterr().out
    assert synthetic.main(["--output-dir", str(out), "--invoices", "3"]) == 1  # fewer than one per vendor
