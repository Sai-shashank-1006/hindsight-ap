"""Settings, read from the environment when asked for (never at import), so tests can set env first.
.env is loaded once and never overrides variables that are already set."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_HINDSIGHT_URL = "https://api.hindsight.vectorize.io"
DEFAULT_HINDSIGHT_TIMEOUT = 30.0
INVOICE_FILE_NAMES = ("demo_scenario.json", "invoices.json")

load_dotenv(ROOT / ".env")


def env(name: str) -> Optional[str]:
    """An environment variable. Empty values and placeholders like "your_key" count as unset."""
    value = os.getenv(name, "").strip()
    if not value or value.lower().startswith("your_"):
        return None
    return value


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


@dataclass(frozen=True)
class Settings:
    groq_api_key: Optional[str] = None
    groq_model: str = DEFAULT_GROQ_MODEL
    hindsight_api_key: Optional[str] = None
    hindsight_bank_id: Optional[str] = None
    hindsight_api_url: str = DEFAULT_HINDSIGHT_URL
    hindsight_timeout: float = DEFAULT_HINDSIGHT_TIMEOUT
    data_dir: Path = ROOT / "data"
    invoices_file: Optional[Path] = None  # the invoice queue; see queue_file()
    decision_log_path: Optional[Path] = None  # None keeps the decision log in memory

    @property
    def hindsight_configured(self) -> bool:
        return bool(self.hindsight_api_key and self.hindsight_bank_id)

    def queue_file(self) -> Path:
        """INVOICES_FILE if set, else the first of demo_scenario.json / invoices.json in DATA_DIR."""
        if self.invoices_file:
            return self.invoices_file
        for name in INVOICE_FILE_NAMES:
            if (self.data_dir / name).exists():
                return self.data_dir / name
        return self.data_dir / INVOICE_FILE_NAMES[0]


def load_settings() -> Settings:
    return Settings(
        groq_api_key=env("GROQ_API_KEY"),
        groq_model=env("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
        hindsight_api_key=env("HINDSIGHT_API_KEY"),
        hindsight_bank_id=env("HINDSIGHT_BANK_ID"),
        hindsight_api_url=env("HINDSIGHT_API_URL") or DEFAULT_HINDSIGHT_URL,
        hindsight_timeout=float(env("HINDSIGHT_TIMEOUT") or DEFAULT_HINDSIGHT_TIMEOUT),
        data_dir=_path(env("DATA_DIR") or "data"),
        invoices_file=_path(env("INVOICES_FILE")) if env("INVOICES_FILE") else None,
        decision_log_path=_path(env("DECISION_LOG_PATH")) if env("DECISION_LOG_PATH") else None,
    )
