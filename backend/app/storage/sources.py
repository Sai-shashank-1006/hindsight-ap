"""Where PaySage reads its data and keeps its decision log: JSON files (the default), or a database
when MYSQL_USER or DATABASE_URL is set. Used by the API and the CLI alike.

With a database, the first start imports the selected dataset's JSON files into it, so
`DATASET=synthetic` plus MySQL credentials is all the setup needed.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional, Set

from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import ROOT, Settings
from app.storage import database
from app.storage.database import DatabaseUnavailable
from app.storage.decision_log import DecisionLog
from app.storage.reference import ReferenceData

log = logging.getLogger("paysage")


# The API serves requests on several threads, and a browser's first page load sends several at once:
# creating the database and tables, and importing a dataset, must happen once, not in parallel.
_lock = threading.RLock()
_engines: Dict[URL, Engine] = {}
_ready: Set[URL] = set()  # databases whose tables exist


def engine_for(url: URL) -> Engine:
    """One engine (and connection pool) per database URL."""
    with _lock:
        if url not in _engines:
            _engines[url] = database.make_engine(url)
        return _engines[url]


def dispose_engines() -> None:
    with _lock:
        _ready.clear()
        while _engines:
            _, engine = _engines.popitem()
            engine.dispose()


def _ready_engine(settings: Settings) -> Engine:
    """The engine, with its database and tables created if missing."""
    engine = engine_for(settings.database_url)
    with _lock:
        if settings.database_url not in _ready:
            database.ensure_database(engine)
            database.create_schema(engine)
            _ready.add(settings.database_url)
    return engine


def _source(settings: Settings) -> str:
    try:
        return settings.queue_file().relative_to(ROOT).as_posix()
    except ValueError:
        return str(settings.queue_file())


def open_reference(settings: Settings) -> ReferenceData:
    """Vendors, POs and the invoice queue for the selected dataset."""
    if not settings.database_url:
        return ReferenceData.load(settings.data_dir, settings.queue_file())
    try:
        engine = _ready_engine(settings)
        with _lock:
            if not database.has_dataset(engine, settings.dataset):
                if settings.queue_file().exists():
                    result = database.import_dataset(engine, settings.dataset, settings.data_dir,
                                                     settings.queue_file(), _source(settings))
                    log.info("database: imported dataset %s (%d invoices) from %s", result.name, result.invoices,
                             _source(settings))
                else:
                    log.warning("database: no dataset %s, and no files to import it from", settings.dataset)
        return database.load_reference(engine, settings.dataset)
    except SQLAlchemyError as exc:
        raise DatabaseUnavailable(database.explain(exc, settings.database_url)) from exc


def open_decision_log(settings: Settings) -> DecisionLog:
    """In the database when there is one (per dataset and Hindsight bank), else as configured."""
    if not settings.database_url:
        return DecisionLog(settings.decision_log_path)
    try:
        return DecisionLog(store=database.SqlEventStore(_ready_engine(settings), settings.log_scope))
    except SQLAlchemyError as exc:
        raise DatabaseUnavailable(database.explain(exc, settings.database_url)) from exc


def database_status(settings: Settings) -> Optional[str]:
    """connected | unreachable, or None without a database. Never raises."""
    if not settings.database_url:
        return None
    engine = engine_for(settings.database_url)
    try:
        database.ensure_database(engine)  # on a first start, before any data request created it
        with engine.connect():
            return "connected"
    except SQLAlchemyError as exc:
        log.warning("health: %s", database.explain(exc, settings.database_url))
    except DatabaseUnavailable as exc:
        log.warning("health: %s", exc)
    return "unreachable"
