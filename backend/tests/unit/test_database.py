"""SQL storage, against SQLite: the same SQLAlchemy code the app runs on MySQL (tests/integration
runs it on a real MySQL server)."""

import json

import pytest
import sqlalchemy as sa

from app import storage
from app.config import BACKEND, ROOT, load_settings
from app.models import Decision
from app.storage import database
from app.storage.database import DatabaseUnavailable, SqlEventStore
from app.storage.decision_log import Decided, DecisionLog
from app.storage.reference import ReferenceData

FIXTURES = BACKEND / "tests" / "fixtures"


@pytest.fixture
def engine():
    engine = database.make_engine("sqlite://")
    database.create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _fresh_engines():
    yield
    storage.dispose_engines()


def dumped(reference: ReferenceData):
    return ([i.model_dump() for i in reference.invoices], [p.model_dump() for p in reference.purchase_orders],
            {k: v.model_dump() for k, v in reference.vendors.items()})


@pytest.mark.parametrize("folder, queue", [(FIXTURES, "demo_scenario.json"), (ROOT / "data" / "synthetic", "invoices.json")],
                         ids=["fixtures", "synthetic"])
def test_a_dataset_comes_back_exactly_as_the_files(engine, folder, queue):
    result = database.import_dataset(engine, "t", folder, folder / queue, "test")
    files = ReferenceData.load(folder, folder / queue)
    assert (result.invoices, result.purchase_orders) == (len(files.invoices), len(files.purchase_orders))
    assert dumped(database.load_reference(engine, "t")) == dumped(files)


def test_datasets_are_separate_and_a_reimport_replaces(engine):
    database.import_dataset(engine, "a", FIXTURES, FIXTURES / "demo_scenario.json", "one")
    database.import_dataset(engine, "b", ROOT / "data", ROOT / "data" / "demo_scenario.json", "two")
    database.import_dataset(engine, "a", FIXTURES, FIXTURES / "demo_scenario.json", "again")
    counts = database.dataset_counts(engine)
    assert {name: info["invoices"] for name, info in counts.items()} == {"a": 5, "b": 4}
    assert counts["a"]["source"] == "again"
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(database.invoices)).scalar() == 9
    assert database.load_reference(engine, "missing").invoices == []


def test_source_refs_are_kept(engine):
    folder = ROOT / "data" / "synthetic"
    database.import_dataset(engine, "s", folder, folder / "invoices.json", "test")
    with engine.connect() as conn:
        ref = conn.execute(sa.select(database.invoices.c.source_ref).limit(1)).scalar()
    assert ref.startswith("Synthetic")


def decided(invoice_id="INV001", decision=Decision.APPROVED):
    return Decided(invoice_id=invoice_id, vendor="ABC Pharma", decision=decision, human_reason="Contract changed",
                   exception_types=["PRICE_MISMATCH"], retained=True, memory_id=f"ap-decision-{invoice_id}",
                   at="2026-09-28T10:00:00+00:00")


def test_the_decision_log_survives_a_restart_per_scope(engine):
    log = DecisionLog(store=SqlEventStore(engine, "demo|bank-1"))
    log.record_decision(decided())
    log.record_decision(decided(decision=Decision.REJECTED))  # a resubmission replaces
    other = DecisionLog(store=SqlEventStore(engine, "demo|bank-2"))
    other.record_decision(decided("INV009"))

    restarted = DecisionLog(store=SqlEventStore(engine, "demo|bank-1"))
    assert list(restarted.decided) == ["INV001"]
    assert restarted.decided["INV001"].decision is Decision.REJECTED
    assert database.scopes(engine) == [("demo|bank-1", 2), ("demo|bank-2", 1)]
    assert SqlEventStore(engine, "demo|bank-1").clear() == 2
    assert DecisionLog(store=SqlEventStore(engine, "demo|bank-1")).decided == {}


def test_a_failing_store_never_fails_the_request(engine, caplog):
    log = DecisionLog(store=SqlEventStore(engine, "demo|bank"))
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE decision_events"))
    log.record_decision(decided())
    assert "INV001" in log.decided  # still in memory
    assert "could not save a decided event" in caplog.text


# ── settings ─────────────────────────────────────────────────────────────────

def test_mysql_settings_build_a_url_that_hides_the_password(monkeypatch):
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "p@ss:w/rd#TEST_SECRET")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    settings = load_settings()
    url = settings.database_url
    assert (url.drivername, url.host, url.port, url.database, url.password) == (
        "mysql+pymysql", "127.0.0.1", 3307, "paysage", "p@ss:w/rd#TEST_SECRET")
    assert settings.data_source == "mysql"
    for text in (str(url), repr(url), repr(settings), database.describe(url)):
        assert "TEST_SECRET" not in text
    assert database.describe(url) == "mysql at 127.0.0.1:3307/paysage"


def test_database_url_wins_and_placeholders_count_as_unset(monkeypatch):
    monkeypatch.setenv("MYSQL_USER", "your_mysql_user")
    assert load_settings().database_url is None
    monkeypatch.setenv("DATABASE_URL", "sqlite:///paysage.db")
    assert load_settings().data_source == "sqlite"


@pytest.mark.parametrize("env, folder, queue, dataset", [
    ({}, "backend/tests/fixtures", None, "fixtures"),  # conftest's DATA_DIR
    ({"DATA_DIR": "data"}, "data", None, "demo"),
    ({"DATA_DIR": "data/real"}, "data/real", None, "real"),
    ({"DATA_DIR": None, "DATASET": "synthetic"}, "data/synthetic", "data/synthetic/invoices.json", "synthetic"),
    ({"DATA_DIR": None, "DATASET": "real"}, "data/real", "data/real/invoices.json", "real"),
    ({"DATA_DIR": "backend/tests/fixtures", "DATASET": "real"}, "backend/tests/fixtures", None, "real"),  # DATA_DIR wins
])
def test_dataset_selection(monkeypatch, env, folder, queue, dataset):
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    settings = load_settings()
    assert settings.data_dir == ROOT / folder
    assert settings.invoices_file == (ROOT / queue if queue else None)
    assert settings.dataset == dataset
    assert settings.log_scope == f"{dataset}|hap-unit"


# ── storage: files or database ───────────────────────────────────────────────

def test_storage_imports_the_dataset_on_first_use_only(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'paysage.db').as_posix()}")
    settings = load_settings()
    first = storage.open_reference(settings)
    assert [i.invoice_id for i in first.invoices] == ["INV001", "INV002", "INV003", "INV004", "INV005"]
    engine = storage.engine_for(settings.database_url)
    imported_at = database.dataset_counts(engine)["fixtures"]["imported_at"]
    assert dumped(storage.open_reference(settings)) == dumped(first)
    assert database.dataset_counts(engine)["fixtures"]["imported_at"] == imported_at  # not imported again

    log = storage.open_decision_log(settings)
    log.record_decision(decided())
    assert "INV001" in storage.open_decision_log(settings).decided


def test_storage_without_a_database_reads_the_files(settings):
    assert settings.database_url is None
    assert dumped(storage.open_reference(settings)) == dumped(ReferenceData.load(settings.data_dir, settings.queue_file()))
    assert storage.database_status(settings) is None


def test_an_unreachable_mysql_is_explained_without_the_password(monkeypatch):
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "TEST_SECRET_pw")
    monkeypatch.setenv("MYSQL_PORT", "1")  # nothing listens on port 1
    settings = load_settings()
    with pytest.raises(DatabaseUnavailable) as caught:
        storage.open_reference(settings)
    message = str(caught.value)
    assert message.startswith("Can't use mysql at 127.0.0.1:1/paysage: nothing answered there")
    assert "TEST_SECRET" not in message
    assert storage.database_status(settings) == "unreachable"


def test_the_decision_events_hold_plain_json(engine):
    DecisionLog(store=SqlEventStore(engine, "s")).record_decision(decided())
    with engine.connect() as conn:
        row = conn.execute(sa.select(database.decision_events)).mappings().one()
    assert (row["kind"], row["invoice_id"], row["scope"]) == ("decided", "INV001", "s")
    assert json.loads(row["payload"])["human_reason"] == "Contract changed"


def test_first_requests_arriving_together_set_the_database_up_once(tmp_path, monkeypatch):
    """A page load sends several requests at once; they must not race to create tables or import."""
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'paysage.db').as_posix()}")
    settings = load_settings()

    def first_request(n):
        return (storage.open_reference if n % 2 else storage.open_decision_log)(settings)

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(first_request, range(8)))
    assert all(results)
    assert database.dataset_counts(storage.engine_for(settings.database_url))["fixtures"]["invoices"] == 5
