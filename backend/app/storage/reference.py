"""Master data (vendors, purchase orders) and the invoice queue, read from DATA_DIR.
Lookups go by key, never by position in a file."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.models import Invoice, PurchaseOrder, Vendor, normalize_vendor


def _read(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def load_invoices(path: Path) -> List[Invoice]:
    return [Invoice.model_validate(item) for item in _read(path)]


@dataclass
class ReferenceData:
    vendors: Dict[str, Vendor] = field(default_factory=dict)  # by normalized name
    purchase_orders: List[PurchaseOrder] = field(default_factory=list)
    invoices: List[Invoice] = field(default_factory=list)  # the queue served by /invoice/next

    @classmethod
    def load(cls, data_dir: Path, queue_file: Optional[Path] = None) -> ReferenceData:
        vendors = [Vendor.model_validate(v) for v in _read(data_dir / "vendors.json")]
        pos = [PurchaseOrder.model_validate(p) for p in _read(data_dir / "purchase_orders.json")]
        invoices = load_invoices(queue_file) if queue_file else []
        return cls({normalize_vendor(v.name): v for v in vendors}, pos, invoices)

    def vendor(self, name: str) -> Optional[Vendor]:
        return self.vendors.get(normalize_vendor(name))

    def po_for(self, invoice: Invoice) -> Optional[PurchaseOrder]:
        """The PO named by po_id (it must belong to the invoice's vendor), else the vendor's latest PO."""
        vendor = normalize_vendor(invoice.vendor)
        if invoice.po_id:
            match = next((po for po in self.purchase_orders if po.po_id == invoice.po_id), None)
            return match if match and normalize_vendor(match.vendor) == vendor else None
        candidates = [po for po in self.purchase_orders if normalize_vendor(po.vendor) == vendor]
        return max(candidates, key=lambda po: po.po_date, default=None)
