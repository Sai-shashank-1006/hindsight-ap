"""scripts/check_setup.py and scripts/db.py, offline (the database is SQLite)."""

import pytest

from app import storage
from app.config import load_settings
from scripts import check_setup, db
from tests.unit.test_database import FIXTURES, decided


@pytest.fixture(autouse=True)
def _fresh_engines():
    yield
    storage.dispose_engines()


def test_check_setup_explains_missing_keys(monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("HINDSIGHT_API_KEY")
    assert check_setup.main([]) == 1
    out = capsys.readouterr().out
    assert "GROQ_API_KEY is not set" in out and "HINDSIGHT_API_KEY is not set" in out
    assert "JSON files, dataset fixtures" in out


def test_check_setup_explains_an_unreachable_mysql_without_the_password(monkeypatch, capsys):
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "TEST_SECRET_pw")
    monkeypatch.setenv("MYSQL_PORT", "1")
    assert check_setup.check_data(load_settings()) is False
    out = capsys.readouterr().out
    assert "nothing answered there" in out and "TEST_SECRET" not in out


def test_db_script_imports_reports_and_clears(tmp_path, monkeypatch, capsys):
    assert db.main(["status"]) == 2 and "MySQL is not configured" in capsys.readouterr().out
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'paysage.db').as_posix()}")
    monkeypatch.setenv("DATASET", "demo")
    assert db.main(["import", "demo"]) == 0
    assert "✓ demo: 4 invoices, 5 purchase orders, 5 vendors" in capsys.readouterr().out
    assert db.main(["import", "nonsense"]) == 2
    assert db.main(["import", "fixtures", "--dir", str(FIXTURES)]) == 0
    capsys.readouterr()
    assert db.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "demo" in out and "the app serves this one" in out and "fixtures" in out

    storage.open_decision_log(load_settings()).record_decision(decided())
    storage.dispose_engines()
    assert db.main(["clear-log"]) == 2  # asks for --yes
    assert db.main(["clear-log", "--yes"]) == 0
    assert "Removed 1 events from 'demo|hap-unit'" in capsys.readouterr().out
