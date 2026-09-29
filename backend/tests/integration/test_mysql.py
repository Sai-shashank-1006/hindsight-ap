"""The storage code on a real MySQL server. Opt-in: set TEST_MYSQL_URL to a local server's URL, e.g.

    TEST_MYSQL_URL=mysql+pymysql://root:password@127.0.0.1:3306 pytest tests/integration -m mysql

Each run creates its own database (paysage_test_<time>) and drops it afterwards; it never touches
the app's database.
"""

import datetime as dt
import os

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from app import storage
from app.config import DATASETS, ROOT, Settings
from app.models import Decision
from app.storage import database
from app.storage.decision_log import Decided, DecisionLog
from app.storage.reference import ReferenceData

pytestmark = [pytest.mark.mysql,
              pytest.mark.skipif(not os.getenv("TEST_MYSQL_URL"), reason="set TEST_MYSQL_URL to run against MySQL")]


@pytest.fixture(scope="module")
def engine():
    name = f"paysage_test_{dt.datetime.now():%Y%m%d_%H%M%S}"
    url = make_url(os.environ["TEST_MYSQL_URL"]).set(database=name)
    engine = database.make_engine(url)
    database.ensure_database(engine)  # creates it
    database.create_schema(engine)
    yield engine
    with engine.begin() as conn:
        conn.execute(sa.text(f"DROP DATABASE `{name}`"))
    engine.dispose()


def dumped(reference):
    return ([i.model_dump() for i in reference.invoices], [p.model_dump() for p in reference.purchase_orders],
            {k: v.model_dump() for k, v in reference.vendors.items()})


@pytest.mark.parametrize("name", list(DATASETS))
def test_every_dataset_round_trips_exactly(engine, name):
    folder, queue = DATASETS[name]
    database.import_dataset(engine, name, ROOT / folder, ROOT / folder / queue, "integration test")
    assert dumped(database.load_reference(engine, name)) == dumped(ReferenceData.load(ROOT / folder, ROOT / folder / queue))


def test_the_database_is_utf8mb4(engine):
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT @@character_set_database")).scalar() == "utf8mb4"


def test_the_decision_log_round_trips(engine):
    decided = Decided(invoice_id="INV-2026-0001", vendor="Deccanvale Lifesciences", decision=Decision.APPROVED,
                      human_reason="Revision effective 1 April 2026: ₹72 → ₹79.20", exception_types=["PRICE_MISMATCH"],
                      retained=True, memory_id="ap-decision-INV-2026-0001", at="2026-09-29T10:00:00+00:00")
    DecisionLog(store=database.SqlEventStore(engine, "synthetic|hap-it")).record_decision(decided)
    replayed = DecisionLog(store=database.SqlEventStore(engine, "synthetic|hap-it"))
    assert replayed.decided["INV-2026-0001"] == decided


def test_health_on_a_first_start_creates_the_database_and_reports_connected():
    """/health can be the very first call, before any data request has created the database."""
    name = f"paysage_test_health_{dt.datetime.now():%Y%m%d_%H%M%S}"
    settings = Settings(database_url=make_url(os.environ["TEST_MYSQL_URL"]).set(database=name))
    try:
        assert storage.database_status(settings) == "connected"
    finally:
        with storage.engine_for(settings.database_url).begin() as conn:
            conn.execute(sa.text(f"DROP DATABASE IF EXISTS `{name}`"))
        storage.dispose_engines()


def test_first_requests_arriving_together_on_a_new_database():
    from concurrent.futures import ThreadPoolExecutor

    name = f"paysage_test_race_{dt.datetime.now():%Y%m%d_%H%M%S}"
    settings = Settings(database_url=make_url(os.environ["TEST_MYSQL_URL"]).set(database=name), dataset="demo",
                        data_dir=ROOT / "data", invoices_file=ROOT / "data" / "demo_scenario.json")
    try:
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda n: (storage.open_reference if n % 2 else storage.open_decision_log)(settings),
                                    range(8)))
        assert all(results)
    finally:
        with storage.engine_for(settings.database_url).begin() as conn:
            conn.execute(sa.text(f"DROP DATABASE IF EXISTS `{name}`"))
        storage.dispose_engines()
