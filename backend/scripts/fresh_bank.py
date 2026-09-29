"""Create a new, empty Hindsight bank and print its id. Never reuses HINDSIGHT_BANK_ID.

    python -m scripts.fresh_bank --prefix hap-demo
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Optional

from app.config import load_settings
from app.memory.hindsight import MemoryUnavailable, create_fresh_bank, make_client


async def run(prefix: str) -> int:
    settings = load_settings()
    client = make_client(settings, require_bank=False)
    if client is None:
        print("HINDSIGHT_API_KEY is not set (a local server at HINDSIGHT_API_URL=http://localhost:8888 needs none)",
              file=sys.stderr)
        return 2
    try:
        bank_id = await create_fresh_bank(client, prefix, settings.hindsight_bank_id)
    except (MemoryUnavailable, ValueError) as exc:
        print(f"Could not create a bank: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.aclose()
    print(bank_id)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", default="hap-demo")
    return asyncio.run(run(parser.parse_args(argv).prefix))


if __name__ == "__main__":
    sys.exit(main())
