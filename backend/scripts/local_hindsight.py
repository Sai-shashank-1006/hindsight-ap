"""Runs Hindsight on this machine (the open-source server) with Groq as its LLM, set up for PaySage.

One-time install, in its own environment (its dependencies differ from PaySage's):

    uv tool install hindsight-api            (or: pipx install hindsight-api)

Then, in a terminal of its own:

    python -m scripts.local_hindsight

It serves http://127.0.0.1:8888, reachable only from this machine. In .env set
HINDSIGHT_API_URL=http://127.0.0.1:8888, leave HINDSIGHT_API_KEY empty (a local server needs none),
and create a bank with `python -m scripts.fresh_bank`. Memories persist between runs in Hindsight's
embedded PostgreSQL. Hindsight uses Groq (GROQ_API_KEY from .env) to extract facts and to reflect.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from app.config import load_settings

INSTALL_HELP = """hindsight-api is not installed. Install it once, in its own environment:

    uv tool install hindsight-api
    (or: pipx install hindsight-api)

then run this again."""
# PaySage's client settings, read from .env. The server must not mistake them for its own.
CLIENT_SETTINGS = ("HINDSIGHT_API_KEY", "HINDSIGHT_API_URL", "HINDSIGHT_BANK_ID", "HINDSIGHT_TIMEOUT")


def server_env(groq_api_key: str, model: str, reflect_model: str, port: int, reflect_iterations: int = 4) -> dict:
    """Sized for Groq's free tier, which limits tokens per minute per MODEL (8,000 or less):
    - reflect gets a model of its own, so a retain and the reflect after it don't share one budget
      (PaySage's own LLM calls use a third model, GROQ_MODEL);
    - reflect is an agent that re-sends its whole context every step, and may take up to 10 steps.
      PaySage asks it one narrow question (one vendor's past decisions) at budget "low", which halves
      the limit: 4 gives 2 steps, one lookup and the answer, and keeps a reflect inside a minute's budget;
    - retain extracts facts from a three-line decision: low reasoning effort does that in a few seconds,
      where the default spent over 2,000 reasoning tokens (and most of a minute's budget) on one."""
    env = {name: value for name, value in os.environ.items() if name not in CLIENT_SETTINGS}
    env.update({
        "PYTHONUTF8": "1",  # its start-up banner is Unicode; Windows consoles default to cp1252
        "PYTHONIOENCODING": "utf-8",
        "HINDSIGHT_API_LLM_PROVIDER": "groq",
        "HINDSIGHT_API_LLM_API_KEY": groq_api_key,
        "HINDSIGHT_API_LLM_MODEL": model,
        "HINDSIGHT_API_RETAIN_LLM_PROVIDER": "groq",
        "HINDSIGHT_API_RETAIN_LLM_API_KEY": groq_api_key,
        "HINDSIGHT_API_RETAIN_LLM_MODEL": model,
        "HINDSIGHT_API_RETAIN_LLM_REASONING_EFFORT": "low",
        "HINDSIGHT_API_REFLECT_LLM_PROVIDER": "groq",
        "HINDSIGHT_API_REFLECT_LLM_API_KEY": groq_api_key,
        "HINDSIGHT_API_REFLECT_LLM_MODEL": reflect_model,
        "HINDSIGHT_API_REFLECT_MAX_ITERATIONS": str(reflect_iterations),
        "HINDSIGHT_API_LLM_GROQ_SERVICE_TIER": "on_demand",  # Hindsight's default, "auto", needs a paid Groq plan
        "HINDSIGHT_API_HOST": "127.0.0.1",
        "HINDSIGHT_API_PORT": str(port),
    })
    return env


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--model", default="openai/gpt-oss-20b",
                        help="the Groq model Hindsight uses to extract facts (default openai/gpt-oss-20b)")
    parser.add_argument("--reflect-model", default="qwen/qwen3.8-27b",
                        help="the Groq model Hindsight reflects with (default qwen/qwen3.8-27b)")
    parser.add_argument("--reflect-iterations", type=int, default=4,
                        help="reflect's step limit, halved at PaySage's budget 'low' (default 4, so 2 steps; "
                             "Hindsight's own default is 10)")
    args = parser.parse_args(argv)

    executable = shutil.which("hindsight-api")
    if not executable:
        print(INSTALL_HELP)
        return 2
    settings = load_settings()
    if not settings.groq_api_key:
        print("GROQ_API_KEY is not set in .env: Hindsight needs an LLM to extract facts from decisions.")
        return 2
    print(f"Starting Hindsight on http://127.0.0.1:{args.port} (Groq: {args.model} for retain, "
          f"{args.reflect_model} for reflect). Ctrl+C stops it.")
    try:
        return subprocess.call([executable, "--host", "127.0.0.1", "--port", str(args.port)],
                               env=server_env(settings.groq_api_key, args.model, args.reflect_model, args.port,
                                              args.reflect_iterations),
                               cwd=Path.home())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
