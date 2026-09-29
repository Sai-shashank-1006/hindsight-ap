"""Optional SQL storage (MySQL in practice): the AP master data (vendors, purchase orders, the invoice
queue) and the decision log, so they survive restarts and can be browsed in any MySQL client.

Hindsight stays the agent's memory. The decision log stored here is the same local log as before
(the dashboard's source); recommendations never read it.

Several datasets live side by side (demo, real, synthetic), keyed by name. The decision log is
kept per dataset and Hindsight bank, so a fresh bank starts with a fresh dashboard.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Union

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import URL, Engine, make_url

from app.models import Invoice, PurchaseOrder, Vendor, normalize_vendor
from app.storage.reference import ReferenceData

log = logging.getLogger("paysage")

MYSQL_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


class DatabaseUnavailable(RuntimeError):
    """The database could not be reached or used. The message says where, never with a password."""


# ── Schema ───────────────────────────────────────────────────────────────────

LongText = sa.Text().with_variant(mysql.LONGTEXT(), "mysql")
Price = sa.Numeric(16, 4, asdecimal=False)
Money = sa.Numeric(18, 2, asdecimal=False)

metadata = sa.MetaData()

datasets = sa.Table(
    "datasets", metadata,
    sa.Column("name", sa.String(32), primary_key=True),
    sa.Column("source", sa.String(500), nullable=False),
    sa.Column("invoices", sa.Integer, nullable=False),
    sa.Column("imported_at", sa.String(40), nullable=False),
    **MYSQL_OPTIONS,
)

vendors = sa.Table(
    "vendors", metadata,
    sa.Column("dataset", sa.String(32), primary_key=True),
    sa.Column("name_key", sa.String(191), primary_key=True),  # normalize_vendor(name)
    sa.Column("name", sa.String(191), nullable=False),
    sa.Column("payment_terms", sa.String(100), nullable=False),
    sa.Column("contact", sa.String(191)),
    sa.Column("historical_prices", sa.Text, nullable=False),  # a JSON list
    **MYSQL_OPTIONS,
)

purchase_orders = sa.Table(
    "purchase_orders", metadata,
    sa.Column("dataset", sa.String(32), primary_key=True),
    sa.Column("po_id", sa.String(64), primary_key=True),
    sa.Column("position", sa.Integer, nullable=False),  # file order
    sa.Column("vendor", sa.String(191), nullable=False),
    sa.Column("expected_price", Price, nullable=False),
    sa.Column("expected_quantity", sa.Integer, nullable=False),
    sa.Column("po_date", sa.Date, nullable=False),
    sa.Column("item", sa.String(500)),
    **MYSQL_OPTIONS,
)

invoices = sa.Table(
    "invoices", metadata,
    sa.Column("dataset", sa.String(32), primary_key=True),
    sa.Column("invoice_id", sa.String(64), primary_key=True),
    sa.Column("position", sa.Integer, nullable=False),  # queue order
    sa.Column("po_id", sa.String(64)),
    sa.Column("vendor", sa.String(191), nullable=False),
    sa.Column("invoice_price", Price, nullable=False),
    sa.Column("quantity", sa.Integer, nullable=False),
    sa.Column("invoice_date", sa.Date, nullable=False),
    sa.Column("po_price", Price),
    sa.Column("invoice_total", Money),
    sa.Column("item", sa.String(500)),
    sa.Column("source_ref", sa.String(300)),
    sa.Index("ix_invoices_queue", "dataset", "position"),
    **MYSQL_OPTIONS,
)

decision_events = sa.Table(
    "decision_events", metadata,
    sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
    sa.Column("scope", sa.String(191), nullable=False),  # "<dataset>|<hindsight bank>"
    sa.Column("kind", sa.String(16), nullable=False),  # processed | decided
    sa.Column("invoice_id", sa.String(64), nullable=False),
    sa.Column("at", sa.String(40), nullable=False),
    sa.Column("payload", LongText, nullable=False),  # the event, as JSON
    sa.Index("ix_decision_events_scope", "scope", "id"),
    **MYSQL_OPTIONS,
)


# ── Connecting ───────────────────────────────────────────────────────────────

def describe(url: Union[str, URL]) -> str:
    """Where a URL points, for messages: dialect, host, port and database. Never the password."""
    url = make_url(url)
    if url.get_backend_name() == "sqlite":
        return f"SQLite {url.database or ':memory:'}"
    return f"{url.get_backend_name()} at {url.host or 'localhost'}:{url.port or 3306}/{url.database or ''}"


def error_code(exc: BaseException) -> Optional[int]:
    """The server's error number (1045, 2003, ...) behind a SQLAlchemy error, if any."""
    original = getattr(exc, "orig", None) or exc
    args = getattr(original, "args", ())
    return args[0] if args and isinstance(args[0], int) else None


def explain(exc: BaseException, url: Union[str, URL]) -> str:
    reasons = {1044: "that user may not use (or create) this database",
               1045: "access denied: check MYSQL_USER and MYSQL_PASSWORD in .env",
               1049: "that database doesn't exist",
               2003: "nothing answered there: is the MySQL service running, and is MYSQL_PORT right?"}
    original = getattr(exc, "orig", None) or exc
    return f"Can't use {describe(url)}: " + reasons.get(error_code(exc), type(original).__name__)


def make_engine(url: Union[str, URL]) -> Engine:
    """No connection is made until the engine is first used."""
    url = make_url(url)
    if url.get_backend_name() == "sqlite":
        in_memory = url.database in (None, "", ":memory:")  # one shared connection, or each would see its own DB
        return sa.create_engine(url, connect_args={"check_same_thread": False},
                                **({"poolclass": sa.pool.StaticPool} if in_memory else {}))
    return sa.create_engine(url, pool_pre_ping=True, pool_recycle=3600, connect_args={"connect_timeout": 5})


def ensure_database(engine: Engine) -> None:
    """Creates the MySQL database if it doesn't exist yet (needs the CREATE privilege)."""
    url = engine.url
    if url.get_backend_name() != "mysql" or not url.database:
        return
    try:
        with engine.connect():
            return
    except sa.exc.OperationalError as exc:
        if error_code(exc) != 1049:  # anything but "unknown database" is the caller's problem
            raise
    if not re.fullmatch(r"[A-Za-z0-9_$]+", url.database):
        raise DatabaseUnavailable(f"{describe(url)} doesn't exist, and PaySage only creates databases "
                                  "named with letters, digits, _ and $")
    server_url = URL.create(url.drivername, username=url.username, password=url.password, host=url.host,
                            port=url.port, query=url.query)  # no database (url.set ignores None)
    server = sa.create_engine(server_url, connect_args={"connect_timeout": 5})
    try:
        with server.begin() as conn:
            conn.execute(sa.text(f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                                 "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
    finally:
        server.dispose()
    log.info("database: created %s", describe(url))


def create_schema(engine: Engine) -> None:
    metadata.create_all(engine)


# ── Datasets ─────────────────────────────────────────────────────────────────

def _day(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


@dataclass
class ImportResult:
    name: str
    vendors: int
    purchase_orders: int
    invoices: int


def import_dataset(engine: Engine, name: str, data_dir: Path, queue_file: Path, source: str) -> ImportResult:
    """Replaces dataset `name` with the JSON files, in one transaction. The files are validated first."""
    reference = ReferenceData.load(data_dir, queue_file)
    raw_queue = json.loads(queue_file.read_text(encoding="utf-8")) if queue_file.exists() else []
    source_refs = {r.get("invoice_id"): r.get("source_ref") for r in raw_queue if isinstance(r, dict)}
    vendor_rows = [{"dataset": name, "name_key": key, "name": v.name, "payment_terms": v.payment_terms,
                    "contact": v.contact, "historical_prices": json.dumps(v.historical_prices)}
                   for key, v in reference.vendors.items()]
    po_rows = [{"dataset": name, "po_id": p.po_id, "position": n, "vendor": p.vendor,
                "expected_price": p.expected_price, "expected_quantity": p.expected_quantity,
                "po_date": _day(p.po_date), "item": p.item}
               for n, p in enumerate(reference.purchase_orders)]
    invoice_rows = [{"dataset": name, "invoice_id": i.invoice_id, "position": n, "po_id": i.po_id, "vendor": i.vendor,
                     "invoice_price": i.invoice_price, "quantity": i.quantity, "invoice_date": _day(i.invoice_date),
                     "po_price": i.po_price, "invoice_total": i.invoice_total, "item": i.item,
                     "source_ref": source_refs.get(i.invoice_id)}
                    for n, i in enumerate(reference.invoices)]
    with engine.begin() as conn:
        for table in (vendors, purchase_orders, invoices):
            conn.execute(table.delete().where(table.c.dataset == name))
        conn.execute(datasets.delete().where(datasets.c.name == name))
        for table, rows in ((vendors, vendor_rows), (purchase_orders, po_rows), (invoices, invoice_rows)):
            if rows:
                conn.execute(table.insert(), rows)
        conn.execute(datasets.insert(), [{"name": name, "source": source[:500], "invoices": len(invoice_rows),
                                          "imported_at": dt.datetime.now(dt.timezone.utc).isoformat()}])
    return ImportResult(name, len(vendor_rows), len(po_rows), len(invoice_rows))


def dataset_counts(engine: Engine) -> Dict[str, dict]:
    with engine.connect() as conn:
        return {row.name: {"source": row.source, "invoices": row.invoices, "imported_at": row.imported_at}
                for row in conn.execute(sa.select(datasets).order_by(datasets.c.name))}


def has_dataset(engine: Engine, name: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(sa.select(datasets.c.name).where(datasets.c.name == name)).first() is not None


def load_reference(engine: Engine, name: str) -> ReferenceData:
    with engine.connect() as conn:
        vendor_rows = conn.execute(sa.select(vendors).where(vendors.c.dataset == name)).mappings().all()
        po_rows = conn.execute(sa.select(purchase_orders).where(purchase_orders.c.dataset == name)
                               .order_by(purchase_orders.c.position)).mappings().all()
        invoice_rows = conn.execute(sa.select(invoices).where(invoices.c.dataset == name)
                                    .order_by(invoices.c.position)).mappings().all()
    found = [Vendor(name=r["name"], payment_terms=r["payment_terms"], contact=r["contact"],
                    historical_prices=json.loads(r["historical_prices"])) for r in vendor_rows]
    pos = [PurchaseOrder(po_id=r["po_id"], vendor=r["vendor"], expected_price=r["expected_price"],
                         expected_quantity=r["expected_quantity"], po_date=r["po_date"].isoformat(), item=r["item"])
           for r in po_rows]
    queue = [Invoice(invoice_id=r["invoice_id"], vendor=r["vendor"], invoice_price=r["invoice_price"],
                     quantity=r["quantity"], invoice_date=r["invoice_date"].isoformat(), po_price=r["po_price"],
                     po_id=r["po_id"], invoice_total=r["invoice_total"], item=r["item"]) for r in invoice_rows]
    return ReferenceData({normalize_vendor(v.name): v for v in found}, pos, queue)


# ── The decision log's events ────────────────────────────────────────────────

class SqlEventStore:
    """Where DecisionLog keeps its events: one row per event, in order, per scope."""

    def __init__(self, engine: Engine, scope: str):
        self.engine = engine
        self.scope = scope[:191]

    def load(self) -> Iterator[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(decision_events.c.payload).where(decision_events.c.scope == self.scope)
                                .order_by(decision_events.c.id)).all()
        for (payload,) in rows:
            yield json.loads(payload)

    def append(self, event: dict) -> None:
        invoice_id = event.get("invoice_id") or event.get("invoice", {}).get("invoice_id", "")
        with self.engine.begin() as conn:
            conn.execute(decision_events.insert().values(
                scope=self.scope, kind=event["kind"], invoice_id=str(invoice_id)[:64], at=event.get("at", ""),
                payload=json.dumps(event, ensure_ascii=False)))

    def clear(self) -> int:
        with self.engine.begin() as conn:
            return conn.execute(decision_events.delete().where(decision_events.c.scope == self.scope)).rowcount


def scopes(engine: Engine) -> List[tuple]:
    """(scope, events) for every decision log in the database."""
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(
            sa.select(decision_events.c.scope, sa.func.count()).group_by(decision_events.c.scope)
            .order_by(decision_events.c.scope))]

