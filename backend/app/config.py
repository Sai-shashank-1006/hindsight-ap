"""Settings, read from the environment when asked for (never at import), so tests can set env first.
.env is loaded once and never overrides variables that are already set."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

BACKEND = Path(__file__).resolve().parents[1]  # backend/: the Python code
ROOT = BACKEND.parent  # the repository: .env and data/ live here; relative paths in .env start here

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_HINDSIGHT_URL = "https://api.hindsight.vectorize.io"
DEFAULT_HINDSIGHT_TIMEOUT = 30.0
INVOICE_FILE_NAMES = ("demo_scenario.json", "invoices.json")
# A Hindsight server on this machine (self-hosted, e.g. `hindsight-api`) needs no API key.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# DATASET=<name> picks one of these folders (and its invoice queue) when DATA_DIR isn't set.
DATASETS = {
    "demo": ("data", "demo_scenario.json"),
    "real": ("data/real", "invoices.json"),
    "synthetic": ("data/synthetic", "invoices.json"),
}

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
    groq_api_key: Optional[str] = field(default=None, repr=False)
    groq_model: str = DEFAULT_GROQ_MODEL
    hindsight_api_key: Optional[str] = field(default=None, repr=False)
    hindsight_bank_id: Optional[str] = None
    hindsight_api_url: str = DEFAULT_HINDSIGHT_URL
    hindsight_timeout: float = DEFAULT_HINDSIGHT_TIMEOUT
    data_dir: Path = ROOT / "data"
    invoices_file: Optional[Path] = None  # the invoice queue; see queue_file()
    decision_log_path: Optional[Path] = None  # None keeps the decision log in memory
    dataset: str = "demo"  # the dataset's name: which rows to use when the data is in a database
    database_url: Optional[URL] = field(default=None, repr=False)  # None: JSON files, no database

    @property
    def hindsight_local(self) -> bool:
        """HINDSIGHT_API_URL points at this machine: a self-hosted server, which needs no key."""
        return urlparse(self.hindsight_api_url).hostname in LOCAL_HOSTS

    @property
    def hindsight_usable(self) -> bool:
        """There is a Hindsight to talk to: a key for Hindsight Cloud, or a local server."""
        return bool(self.hindsight_api_key) or self.hindsight_local

    @property
    def hindsight_configured(self) -> bool:
        return self.hindsight_usable and bool(self.hindsight_bank_id)

    @property
    def data_source(self) -> str:
        """files, or the database's kind (mysql; sqlite in the tests)."""
        return self.database_url.get_backend_name() if self.database_url else "files"

    @property
    def log_scope(self) -> str:
        """The decision log in a database is kept per dataset and Hindsight bank."""
        return f"{self.dataset}|{self.hindsight_bank_id or 'no-bank'}"

    def queue_file(self) -> Path:
        """INVOICES_FILE if set, else the first of demo_scenario.json / invoices.json in DATA_DIR."""
        if self.invoices_file:
            return self.invoices_file
        for name in INVOICE_FILE_NAMES:
            if (self.data_dir / name).exists():
                return self.data_dir / name
        return self.data_dir / INVOICE_FILE_NAMES[0]


def database_url() -> Optional[URL]:
    """DATABASE_URL (any SQLAlchemy URL), else MySQL from MYSQL_USER and friends, else None."""
    if env("DATABASE_URL"):
        return make_url(env("DATABASE_URL"))
    if not env("MYSQL_USER"):
        return None
    # URL.create escapes the password, so any character works in MYSQL_PASSWORD.
    return URL.create("mysql+pymysql", username=env("MYSQL_USER"), password=env("MYSQL_PASSWORD"),
                      host=env("MYSQL_HOST") or "127.0.0.1", port=int(env("MYSQL_PORT") or 3306),
                      database=env("MYSQL_DATABASE") or "paysage", query={"charset": "utf8mb4"})


def _dataset_name(data_dir: Path) -> str:
    for name, (folder, _) in DATASETS.items():
        if data_dir == ROOT / folder:
            return name
    return data_dir.name


def load_settings() -> Settings:
    dataset, data_dir_env, invoices_env = env("DATASET"), env("DATA_DIR"), env("INVOICES_FILE")
    folder, queue = DATASETS.get(dataset or "", (None, None))
    data_dir = _path(data_dir_env) if data_dir_env else ROOT / (folder or "data")
    if invoices_env:
        invoices_file = _path(invoices_env)
    else:
        invoices_file = ROOT / folder / queue if folder and not data_dir_env else None
    return Settings(
        groq_api_key=env("GROQ_API_KEY"),
        groq_model=env("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
        hindsight_api_key=env("HINDSIGHT_API_KEY"),
        hindsight_bank_id=env("HINDSIGHT_BANK_ID"),
        hindsight_api_url=env("HINDSIGHT_API_URL") or DEFAULT_HINDSIGHT_URL,
        hindsight_timeout=float(env("HINDSIGHT_TIMEOUT") or DEFAULT_HINDSIGHT_TIMEOUT),
        data_dir=data_dir,
        invoices_file=invoices_file,
        decision_log_path=_path(env("DECISION_LOG_PATH")) if env("DECISION_LOG_PATH") else None,
        dataset=dataset or _dataset_name(data_dir),
        database_url=database_url(),
    )
