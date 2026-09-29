"""Checks PaySage's setup for real: the Groq key, the Hindsight key and bank, and MySQL if configured.
The calls it makes cost nothing (no completions, no retains). It never prints a key or password.

    python -m scripts.check_setup
"""

from __future__ import annotations

import asyncio
import sys
from typing import List, Optional

import groq
from sqlalchemy.exc import SQLAlchemyError

from app import storage
from app.config import Settings, load_settings
from app.memory.hindsight import FAILURES, explain_failure, make_client
from app.storage import database

OK, BAD, NOTE = "✓", "✗", "•"


async def check_groq(settings: Settings) -> bool:
    if not settings.groq_api_key:
        print(f"{BAD} Groq: GROQ_API_KEY is not set in .env. Create a key at https://console.groq.com/keys")
        return False
    client = groq.AsyncGroq(api_key=settings.groq_api_key, timeout=15, max_retries=1)
    try:
        models = {model.id for model in (await client.models.list()).data}
    except groq.AuthenticationError:
        print(f"{BAD} Groq: the key was refused. Copy it again from https://console.groq.com/keys")
        return False
    except groq.APIConnectionError:
        print(f"{BAD} Groq: couldn't reach api.groq.com. Check the internet connection")
        return False
    except groq.APIStatusError as exc:
        print(f"{BAD} Groq: HTTP {exc.status_code}")
        return False
    finally:
        await client.close()
    if settings.groq_model not in models:
        print(f"{BAD} Groq: the key works, but the model {settings.groq_model} isn't available to it. "
              "Set GROQ_MODEL to one that is, e.g. qwen/qwen3-32b")
        return False
    print(f"{OK} Groq: the key works; {settings.groq_model} is available")
    return True


async def check_hindsight(settings: Settings) -> bool:
    client = make_client(settings, require_bank=False)
    if client is None:
        print(f"{BAD} Hindsight: HINDSIGHT_API_KEY is not set in .env. Get one from Hindsight Cloud "
              "(https://ui.hindsight.vectorize.io), or run Hindsight on this machine: python -m scripts.local_hindsight")
        return False
    bank = settings.hindsight_bank_id
    try:
        await client.aget_version()
        if not bank:
            print(f"{BAD} Hindsight: reachable, but HINDSIGHT_BANK_ID is not set. Create a bank with\n"
                  "      python -m scripts.fresh_bank --prefix hap-demo\n    and put the id it prints in .env")
            return False
        await client.aget_bank_config(bank)  # needs a valid key and an existing bank
        total = (await client.alist_memories(bank, limit=1)).total
    except FAILURES as exc:
        print(f"{BAD} Hindsight: {explain_failure(exc, bank or '-', settings.hindsight_timeout)}")
        return False
    finally:
        await client.aclose()
    where = f"the local server at {settings.hindsight_api_url}" if settings.hindsight_local else "the key works"
    print(f"{OK} Hindsight: {where}; bank {bank} holds {total} memor{'y' if total == 1 else 'ies'}")
    return True


def check_data(settings: Settings) -> bool:
    if not settings.database_url:
        print(f"{NOTE} Data: JSON files, dataset {settings.dataset} ({settings.queue_file().name}). "
              "MySQL is optional: see the README")
        return True
    try:
        engine = storage.engine_for(settings.database_url)
        database.ensure_database(engine)
        database.create_schema(engine)
        loaded = database.dataset_counts(engine)
    except SQLAlchemyError as exc:
        print(f"{BAD} Data: {database.explain(exc, settings.database_url)}")
        return False
    except database.DatabaseUnavailable as exc:
        print(f"{BAD} Data: {exc}")
        return False
    finally:
        storage.dispose_engines()
    where = database.describe(settings.database_url)
    if settings.dataset in loaded:
        print(f"{OK} Data: {where}, dataset {settings.dataset} ({loaded[settings.dataset]['invoices']} invoices)")
    else:
        print(f"{OK} Data: {where}; dataset {settings.dataset} will be imported on the API's first start")
    return True


async def run() -> int:
    settings = load_settings()
    results = [await check_groq(settings), await check_hindsight(settings), check_data(settings)]
    if all(results):
        print("\nAll set. Start the API (cd backend && uvicorn api:app) and the web app (cd frontend && npm run dev).")
        return 0
    print("\nFix the ✗ lines in .env, then run this again.")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
