"""Exact-one-run acceptance for every required WMS run-bearing table."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.describe import describe_wms
from operational_variance_toolkit.wms.application.reports import available_reports, run_wms_report
from operational_variance_toolkit.wms.storage.repositories import (
    WMS_TABLES,
    WmsFoundationRepository,
)

RUN_TABLES = tuple(name for name in WMS_TABLES if name != "schema_metadata")


@pytest.fixture
def identity_database(console_wms_path, tmp_path):
    path = tmp_path / "identity.sqlite3"
    with closing(sqlite3.connect(console_wms_path)) as source:
        with closing(sqlite3.connect(path)) as destination:
            source.backup(destination)
    return path


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_metadata_requires_exactly_one_run(count):
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute(
            """CREATE TABLE simulation_run (
                run_id TEXT, seed INTEGER, schema_version TEXT, generator_version TEXT,
                config_hash TEXT, facility_timezone TEXT, simulation_start_utc TEXT,
                simulation_end_utc TEXT, generated_at_utc TEXT
            )"""
        )
        connection.executemany(
            "INSERT INTO simulation_run VALUES (?, 1, '3.0.0', '1', 'hash', 'UTC', 'a', 'b', 'c')",
            ((f"run-{index}",) for index in range(count)),
        )
        repository = WmsFoundationRepository(connection)
        if count == 1:
            assert repository.run_metadata().run_id == "run-0"
        else:
            with pytest.raises(sqlite3.DatabaseError, match="Expected exactly one"):
                repository.run_metadata()


@pytest.mark.parametrize("table_name", RUN_TABLES)
@pytest.mark.parametrize("conflicting_id", ["another-run", None])
def test_every_required_run_table_rejects_conflicts_without_relying_on_foreign_keys(
    table_name, conflicting_id
):
    with closing(sqlite3.connect(":memory:")) as connection:
        for name in RUN_TABLES:
            connection.execute(f'CREATE TABLE "{name}" (run_id TEXT)')
            connection.execute(f'INSERT INTO "{name}" VALUES (?)', ("accepted-run",))
        repository = WmsFoundationRepository(connection)
        assert repository.conflicting_run_tables("accepted-run") == ()
        connection.execute(f'INSERT INTO "{table_name}" VALUES (?)', (conflicting_id,))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert repository.conflicting_run_tables("accepted-run") == (table_name,)


def test_empty_required_run_tables_do_not_invent_a_conflict():
    with closing(sqlite3.connect(":memory:")) as connection:
        for name in RUN_TABLES:
            connection.execute(f'CREATE TABLE "{name}" (run_id TEXT)')
        assert WmsFoundationRepository(connection).conflicting_run_tables("accepted-run") == ()


@pytest.mark.parametrize(
    ("column_type", "accepted_id", "stored_id"),
    [
        ("TEXT COLLATE NOCASE", "accepted-run", "ACCEPTED-RUN"),
        ("TEXT COLLATE RTRIM", "accepted-run", "accepted-run "),
        ("INTEGER", "1", 1),
        ("BLOB", "accepted-run", b"accepted-run"),
    ],
)
def test_declared_collation_or_affinity_cannot_hide_a_conflicting_identity(
    column_type, accepted_id, stored_id
):
    with closing(sqlite3.connect(":memory:")) as connection:
        for name in RUN_TABLES:
            declaration = column_type if name == "item_master" else "TEXT"
            connection.execute(f'CREATE TABLE "{name}" (run_id {declaration})')
        connection.execute('INSERT INTO "item_master" VALUES (?)', (stored_id,))
        assert WmsFoundationRepository(connection).conflicting_run_tables(accepted_id) == (
            "item_master",
        )


@pytest.mark.parametrize("user_version", [3, 4])
@pytest.mark.parametrize("run_count", [0, 1, 2])
def test_wms_and_sandbox_core_accept_only_one_run(identity_database, user_version, run_count):
    with closing(sqlite3.connect(identity_database)) as connection:
        connection.execute(f"PRAGMA user_version = {user_version}")
        if run_count == 0:
            connection.execute("DELETE FROM simulation_run")
        elif run_count == 2:
            connection.execute(
                """INSERT INTO simulation_run
                SELECT 'another-run', seed, schema_version, generator_version, config_hash,
                    facility_timezone, simulation_start_utc, simulation_end_utc, generated_at_utc
                FROM simulation_run"""
            )
            # A second valid parent violates the one-run contract even without
            # any foreign-key violations.
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        validation = validate_wms_dataset(connection, allow_sandbox=user_version == 4)
        assert validation.passed is (run_count == 1)
        if run_count != 1:
            assert validation.hard_failures[0].category == "metadata"
            assert "exactly one" in validation.hard_failures[0].message
        connection.commit()
    if user_version == 3 and run_count != 1:
        with pytest.raises(DataValidationError):
            describe_wms(identity_database)
        report = next(spec for spec in available_reports() if not spec.required_parameters)
        with pytest.raises(DataValidationError):
            run_wms_report(identity_database, report.code)


@pytest.mark.parametrize("run_id", ["", b"unexpected-blob"])
def test_run_metadata_identity_must_be_a_nonempty_string(identity_database, run_id):
    with closing(sqlite3.connect(identity_database)) as connection:
        connection.execute("UPDATE simulation_run SET run_id = ?", (run_id,))
        validation = validate_wms_dataset(connection)
    assert not validation.passed
    assert validation.hard_failures[0].category == "metadata"
    assert "nonempty string" in validation.hard_failures[0].message


def test_conflicting_required_table_is_reported_before_result_reads(identity_database):
    with closing(sqlite3.connect(identity_database)) as connection:
        connection.execute("UPDATE item_master SET run_id = 'another-run'")
        validation = validate_wms_dataset(connection)
    assert not validation.passed
    assert any(
        issue.category == "metadata" and "item_master" in issue.message
        for issue in validation.hard_failures
    )


def test_foreign_key_orphan_remains_nonpass(identity_database):
    with closing(sqlite3.connect(identity_database)) as connection:
        connection.execute(
            """UPDATE inventory_master SET item_id = 'missing-item'
            WHERE location_id = (
                SELECT location_id FROM inventory_master WHERE item_id IS NOT NULL LIMIT 1
            )"""
        )
        validation = validate_wms_dataset(connection)
    assert not validation.passed
    assert any(issue.category == "foreign_keys" for issue in validation.hard_failures)


def test_missing_run_column_is_controlled_schema_failure(identity_database):
    with closing(sqlite3.connect(identity_database)) as connection:
        connection.execute("ALTER TABLE operator RENAME COLUMN run_id TO former_run_id")
        validation = validate_wms_dataset(connection)
    assert not validation.passed
    assert any(
        issue.category == "schema" and "operator" in issue.message and "run_id" in issue.message
        for issue in validation.hard_failures
    )
