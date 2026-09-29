"""Deterministic invoice-vs-PO checks. Compares the invoice with the PO RECORD; the po_price an
invoice quotes is never trusted. No LLM here: exceptions must be reproducible."""

from __future__ import annotations

from typing import List

from app.models import (
    SEVERITY_RANK,
    ExceptionType,
    Invoice,
    InvoiceException,
    PurchaseOrder,
    Severity,
    format_money,
)

# Half a paisa: absorbs float noise, never a real price difference.
PRICE_TOLERANCE = 0.005


def variance_percent(expected: float, actual: float) -> float:
    """Absolute percentage difference. A zero expected value (a PO that slipped past validation)
    counts as a 100% difference instead of dividing by zero."""
    if expected == 0:
        return 100.0
    return round(abs(actual - expected) * 100 / expected, 2)


def price_severity(pct: float) -> Severity:
    """CRITICAL above 10%, WARNING above 5%, otherwise INFO."""
    if pct > 10:
        return Severity.CRITICAL
    if pct > 5:
        return Severity.WARNING
    return Severity.INFO


def quantity_severity(pct: float) -> Severity:
    """Any quantity difference is at least a WARNING; CRITICAL above 10%."""
    return Severity.CRITICAL if pct > 10 else Severity.WARNING


class RuleEngine:
    def detect_exceptions(self, invoice: Invoice, po: PurchaseOrder) -> List[InvoiceException]:
        """Every mismatch, most severe first."""
        exceptions = []

        if abs(invoice.invoice_price - po.expected_price) > PRICE_TOLERANCE:
            pct = variance_percent(po.expected_price, invoice.invoice_price)
            direction = "above" if invoice.invoice_price > po.expected_price else "below"
            exceptions.append(InvoiceException(
                type=ExceptionType.PRICE_MISMATCH,
                severity=price_severity(pct),
                expected_value=po.expected_price,
                actual_value=invoice.invoice_price,
                variance_percent=pct,
                reason=(f"Invoiced {format_money(invoice.invoice_price)}/unit is {pct:g}% {direction} "
                        f"the PO price of {format_money(po.expected_price)}/unit"),
            ))

        if invoice.quantity != po.expected_quantity:
            pct = variance_percent(po.expected_quantity, invoice.quantity)
            direction = "more" if invoice.quantity > po.expected_quantity else "fewer"
            exceptions.append(InvoiceException(
                type=ExceptionType.QUANTITY_MISMATCH,
                severity=quantity_severity(pct),
                expected_value=po.expected_quantity,
                actual_value=invoice.quantity,
                variance_percent=pct,
                reason=(f"Invoiced {invoice.quantity} units, {pct:g}% {direction} than the "
                        f"{po.expected_quantity} units on the PO"),
            ))

        return sorted(exceptions, key=lambda e: SEVERITY_RANK[e.severity], reverse=True)

    def validate_invoice(self, invoice: Invoice, po: PurchaseOrder) -> bool:
        return not self.detect_exceptions(invoice, po)
