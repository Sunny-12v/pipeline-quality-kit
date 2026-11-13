from datetime import datetime

import pytest

from pqk.checks import ConfigError, build_sql
from pqk.cli import main
from pqk.engine import DuckDBEngine
from pqk.runner import run_checks

NOW = datetime(2026, 11, 13, 12, 0, 0)


@pytest.fixture
def engine():
    """A fresh in-memory database with two small tables."""
    e = DuckDBEngine()
    e.con.execute("CREATE TABLE customers (customer_id INTEGER, name VARCHAR)")
    e.con.execute("INSERT INTO customers VALUES (1, 'Asha'), (2, 'Ben')")
    e.con.execute(
        "CREATE TABLE orders (order_id INTEGER, customer_id INTEGER, "
        "status VARCHAR, amount DOUBLE, created_at TIMESTAMP)"
    )
    e.con.execute(
        "INSERT INTO orders VALUES "
        "(1, 1, 'paid', 100.0, '2026-11-13 08:00:00'),"
        "(2, 2, 'shipped', 50.0, '2026-11-13 09:00:00'),"
        "(2, 9, 'lost', -5.0, '2026-11-13 10:00:00'),"
        "(4, NULL, 'paid', 70.0, '2026-11-13 11:00:00')"
    )
    return e


def failing(engine, spec):
    return int(engine.scalar(build_sql(spec, NOW)))


def test_not_null_counts_nulls(engine):
    assert failing(engine, {"check": "not_null", "table": "orders", "column": "customer_id"}) == 1


def test_not_null_passes_on_clean_column(engine):
    assert failing(engine, {"check": "not_null", "table": "orders", "column": "order_id"}) == 0


def test_unique_counts_every_row_in_a_duplicate_group(engine):
    # order_id 2 appears twice, so 2 rows break the rule.
    assert failing(engine, {"check": "unique", "table": "orders", "column": "order_id"}) == 2


def test_accepted_values_flags_unknown_status(engine):
    spec = {"check": "accepted_values", "table": "orders", "column": "status",
            "values": ["paid", "shipped"]}
    assert failing(engine, spec) == 1  # 'lost'


def test_range_flags_values_outside_bounds(engine):
    spec = {"check": "range", "table": "orders", "column": "amount", "min": 0, "max": 1000}
    assert failing(engine, spec) == 1  # -5.0


def test_foreign_key_flags_orphans_and_ignores_nulls(engine):
    spec = {"check": "foreign_key", "table": "orders", "column": "customer_id",
            "ref_table": "customers", "ref_column": "customer_id"}
    assert failing(engine, spec) == 1  # customer 9 is missing; the NULL is not counted


def test_freshness_fails_when_data_is_stale(engine):
    spec = {"check": "freshness", "table": "orders", "column": "created_at", "max_age_hours": 0.5}
    assert failing(engine, spec) == 1  # newest row is 1 hour old


def test_freshness_passes_when_data_is_recent(engine):
    spec = {"check": "freshness", "table": "orders", "column": "created_at", "max_age_hours": 24}
    assert failing(engine, spec) == 0


def test_unknown_check_raises_config_error():
    with pytest.raises(ConfigError):
        build_sql({"check": "banana", "table": "t", "column": "c"})


def test_sql_errors_become_failed_results_not_crashes(engine):
    results = run_checks(
        [{"check": "not_null", "table": "orders", "column": "no_such_column"}], engine, NOW
    )
    assert results[0].passed is False and results[0].error


def test_cli_exit_codes(tmp_path):
    (tmp_path / "t.csv").write_text("id,v\n1,a\n2,b\n")
    good = tmp_path / "good.yml"
    good.write_text("sources: {t: t.csv}\nchecks:\n  - {check: unique, table: t, column: id}\n")
    bad = tmp_path / "bad.yml"
    bad.write_text("sources: {t: t.csv}\nchecks:\n  - {check: accepted_values, table: t, column: v, values: [a]}\n")
    assert main(["run", str(good)], engine_factory=DuckDBEngine) == 0
    assert main(["run", str(bad)], engine_factory=DuckDBEngine) == 1
    assert main(["run", str(tmp_path / "missing.yml")], engine_factory=DuckDBEngine) == 2
