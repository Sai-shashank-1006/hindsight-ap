"""PaySage's MySQL storage: create it, load datasets into it, see what's there.

Uses MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE (or DATABASE_URL) from .env.
The database and its tables are created if missing.

    python -m scripts.db status                      what is stored
    python -m scripts.db import all                  load demo, real and synthetic (replacing them)
    python -m scripts.db import synthetic
    python -m scripts.db import mydata --dir some/folder    vendors.json, purchase_orders.json and a queue
    python -m scripts.db clear-log --yes             empty the dashboard for the configured dataset and bank

The API imports the dataset it serves on its first start. Use this to reload one after regenerating
it, then restart the API.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app import storage
from app.config import DATASETS, INVOICE_FILE_NAMES, ROOT, Settings, load_settings
from app.storage import database

NOT_CONFIGURED = """MySQL is not configured. Add to .env (the database is created if it doesn't exist):

    MYSQL_HOST=127.0.0.1
    MYSQL_PORT=3306
    MYSQL_USER=root
    MYSQL_PASSWORD=your MySQL password
    MYSQL_DATABASE=paysage"""


def _queue_in(folder: Path) -> Path:
    return next((folder / name for name in INVOICE_FILE_NAMES if (folder / name).exists()), folder / "invoices.json")


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def cmd_status(engine: Engine, settings: Settings) -> int:
    loaded = database.dataset_counts(engine)
    print(f"Datasets ({len(loaded)}):" if loaded else "No datasets yet: python -m scripts.db import all")
    for name, info in loaded.items():
        serving = "  ← the app serves this one (DATASET)" if name == settings.dataset else ""
        print(f"  {name:<12} {info['invoices']:>6} invoices  from {info['source']}, "
              f"imported {info['imported_at'][:16].replace('T', ' ')} UTC{serving}")
    logs = database.scopes(engine)
    print(f"Decision logs ({len(logs)}):" if logs else "Decision logs: none yet")
    for scope, events in logs:
        mine = "  ← this configuration" if scope == settings.log_scope else ""
        print(f"  {scope:<40} {events:>6} events{mine}")
    return 0


def cmd_import(engine: Engine, name: str, folder: Optional[Path]) -> int:
    if folder:
        jobs = [(name, folder, _queue_in(folder))]
    elif name == "all":
        jobs = [(n, ROOT / f, ROOT / f / q) for n, (f, q) in DATASETS.items()]
    elif name in DATASETS:
        f, q = DATASETS[name]
        jobs = [(name, ROOT / f, ROOT / f / q)]
    else:
        print(f"Unknown dataset {name!r}. Use {', '.join(DATASETS)} or all, or give --dir for your own folder.")
        return 2
    for job_name, data_dir, queue in jobs:
        if not queue.exists():
            print(f"✗ {job_name}: {_shown(queue)} not found" + (
                " (python -m scripts.generate_synthetic_data)" if job_name == "synthetic" else
                " (python -m scripts.download_real_data)" if job_name == "real" else ""))
            return 1
        result = database.import_dataset(engine, job_name, data_dir, queue, _shown(queue))
        print(f"✓ {job_name}: {result.invoices} invoices, {result.purchase_orders} purchase orders, "
              f"{result.vendors} vendors (from {_shown(queue)})")
    print("Restart the API to serve the new data.")
    return 0


def cmd_clear_log(engine: Engine, settings: Settings, yes: bool) -> int:
    if not yes:
        print(f"This deletes the decision log '{settings.log_scope}' (the dashboard's history; Hindsight memory "
              "is not touched). Run again with --yes to do it.")
        return 2
    removed = database.SqlEventStore(engine, settings.log_scope).clear()
    print(f"✓ Removed {removed} events from '{settings.log_scope}'. Restart the API to see an empty dashboard.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="what is stored")
    load = commands.add_parser("import", help="load a dataset from its JSON files, replacing it")
    load.add_argument("name", help="demo, real, synthetic, all, or a name for --dir")
    load.add_argument("--dir", type=Path, help="a folder with vendors.json, purchase_orders.json and invoices")
    clear = commands.add_parser("clear-log", help="empty the decision log for DATASET and HINDSIGHT_BANK_ID")
    clear.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.database_url:
        print(NOT_CONFIGURED)
        return 2
    print(f"Database: {database.describe(settings.database_url)}")
    try:
        engine = storage.engine_for(settings.database_url)
        database.ensure_database(engine)
        database.create_schema(engine)
        if args.command == "status":
            return cmd_status(engine, settings)
        if args.command == "import":
            return cmd_import(engine, args.name, args.dir)
        return cmd_clear_log(engine, settings, args.yes)
    except SQLAlchemyError as exc:
        print(f"✗ {database.explain(exc, settings.database_url)}")
        return 1
    except database.DatabaseUnavailable as exc:
        print(f"✗ {exc}")
        return 1
    finally:
        storage.dispose_engines()


if __name__ == "__main__":
    sys.exit(main())
