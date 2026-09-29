"""Rule engine: pure and deterministic. PO record: ABC Pharma, ₹500 × 100."""

import pytest
from pydantic import ValidationError

from app.models import ExceptionType, PurchaseOrder, Severity
from app.rule_engine import RuleEngine, price_severity, quantity_severity, variance_percent
from tests.conftest import invoice, po

RULES = RuleEngine()
PRICE, QTY = ExceptionType.PRICE_MISMATCH, ExceptionType.QUANTITY_MISMATCH


def detect(price=500, quantity=100, **extra):
    return RULES.detect_exceptions(invoice(invoice_price=price, quantity=quantity, **extra), po())


def test_matching_invoice_has_no_exceptions():
    assert detect() == []
    assert RULES.validate_invoice(invoice(invoice_price=500), po())


def test_price_mismatch():
    [exc] = detect(550)
    assert (exc.type, exc.expected_value, exc.actual_value, exc.variance_percent) == (PRICE, 500, 550, 10.0)
    assert "above" in exc.reason
    assert not RULES.validate_invoice(invoice(invoice_price=550), po())


@pytest.mark.parametrize("price, severity", [
    (525, Severity.INFO), (526, Severity.WARNING), (550, Severity.WARNING), (551, Severity.CRITICAL),
])
def test_price_severity_bands(price, severity):
    [exc] = detect(price)
    assert exc.severity == severity


def test_under_billing_is_a_mismatch_with_absolute_variance():
    [exc] = detect(450)
    assert (exc.type, exc.variance_percent, exc.severity) == (PRICE, 10.0, Severity.WARNING)
    assert "below" in exc.reason


def test_regression_quoted_po_price_cannot_hide_a_mismatch():
    """LabTech: invoice quotes po_price 300 and bills 315 against a ₹300 PO. Used to pass as clean."""
    [exc] = RULES.detect_exceptions(invoice(vendor="LabTech", po_price=300, invoice_price=315, quantity=75),
                                    po("LabTech", 300, 75))
    assert (exc.type, exc.actual_value) == (PRICE, 315)


def test_po_record_wins_over_the_requests_po_price():
    [exc] = detect(550, po_price=550)  # the request claims the PO says 550; the record says 500
    assert (exc.expected_value, exc.actual_value) == (500, 550)


def test_paise_noise_is_not_a_mismatch():
    assert RULES.detect_exceptions(invoice(invoice_price=550.004), po(price=550.00)) == []


@pytest.mark.parametrize("quantity, severity", [(110, Severity.WARNING), (111, Severity.CRITICAL), (90, Severity.WARNING)])
def test_quantity_mismatch(quantity, severity):
    [exc] = detect(quantity=quantity)
    assert (exc.type, exc.severity, exc.expected_value, exc.actual_value) == (QTY, severity, 100, quantity)
    assert ("more" if quantity > 100 else "fewer") in exc.reason


def test_both_mismatches_are_returned_most_severe_first():
    found = detect(510, 120)  # price +2% INFO, quantity +20% CRITICAL
    assert [(e.type, e.severity) for e in found] == [(QTY, Severity.CRITICAL), (PRICE, Severity.INFO)]


def test_zero_po_values_are_rejected_by_the_model():
    with pytest.raises(ValidationError):
        PurchaseOrder(po_id="P", vendor="ABC Pharma", expected_price=0, expected_quantity=100, po_date="2026-09-01")
    with pytest.raises(ValidationError):
        PurchaseOrder(po_id="P", vendor="ABC Pharma", expected_price=500, expected_quantity=0, po_date="2026-09-01")


def test_zero_po_values_never_divide_by_zero():
    """A PO that slipped past validation (model_construct) is handled, not a ZeroDivisionError."""
    broken = PurchaseOrder.model_construct(po_id="P", vendor="ABC Pharma", expected_price=0,
                                           expected_quantity=0, po_date="2026-09-01")
    found = RULES.detect_exceptions(invoice(), broken)
    assert {(e.type, e.variance_percent, e.severity) for e in found} == {
        (PRICE, 100.0, Severity.CRITICAL), (QTY, 100.0, Severity.CRITICAL)}


def test_severity_helpers():
    assert variance_percent(500, 500) == 0
    assert (price_severity(5), price_severity(5.01), price_severity(10), price_severity(10.01)) == (
        Severity.INFO, Severity.WARNING, Severity.WARNING, Severity.CRITICAL)
    assert (quantity_severity(10), quantity_severity(10.01)) == (Severity.WARNING, Severity.CRITICAL)
