from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from operational_variance_toolkit.errors import ReadSnapshotError
from operational_variance_toolkit.storage.database import (
    ReadIdentity,
    SQLiteReadLimits,
    accepted_read_snapshot,
)

LIMITS = SQLiteReadLimits("synthetic-contract", 1_000_000, 100, 100_000, 100, 10_000)


def _database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE evidence(run TEXT, value INTEGER)")
        connection.execute("INSERT INTO evidence VALUES ('RUN-1', 10)")
        connection.commit()


def _accept(connection: sqlite3.Connection) -> ReadIdentity:
    assert connection.in_transaction
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    run = connection.execute("SELECT run FROM evidence").fetchone()[0]
    return ReadIdentity(run, "synthetic")


def test_validation_and_result_share_stable_snapshot_and_close(tmp_path: Path) -> None:
    path = tmp_path / "source.sqlite3"
    _database(path)
    observed = []

    def validator(connection):
        observed.append(connection)
        return _accept(connection)

    with accepted_read_snapshot(path, validator=validator, limits=LIMITS) as accepted:
        connection = accepted.connection
        assert observed == [connection]
        assert accepted.identity == ReadIdentity("RUN-1", "synthetic")
        with closing(sqlite3.connect(path)) as writer:
            writer.execute("UPDATE evidence SET value=20")
            writer.commit()
        assert connection.execute("SELECT value FROM evidence").fetchone() == (10,)
        assert connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH) == LIMITS.value_bytes
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    with accepted_read_snapshot(path, validator=_accept, limits=LIMITS) as second:
        assert second.connection.execute("SELECT value FROM evidence").fetchone() == (20,)


@pytest.mark.parametrize(
    "query",
    [
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT bypass",
        "PRAGMA query_only=OFF",
        "ATTACH DATABASE ':memory:' AS bypass",
        "UPDATE evidence SET value=99",
    ],
)
def test_sql_cannot_bypass_accepted_lifetime_or_readonly(tmp_path: Path, query: str) -> None:
    path = tmp_path / "source.sqlite3"
    _database(path)
    with pytest.raises(ReadSnapshotError):
        with accepted_read_snapshot(path, validator=_accept, limits=LIMITS) as accepted:
            accepted.connection.execute(query)


def test_acceptance_failure_closes_connection_and_never_yields(tmp_path: Path) -> None:
    path = tmp_path / "source.sqlite3"
    _database(path)
    observed = []

    def reject(connection):
        observed.append(connection)
        raise ValueError("role rejected")

    with pytest.raises(ValueError, match="role rejected"):
        with accepted_read_snapshot(path, validator=reject, limits=LIMITS):
            pytest.fail("Rejected input was yielded")
    with pytest.raises(sqlite3.ProgrammingError):
        observed[0].execute("SELECT 1")


def test_missing_database_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(ReadSnapshotError):
        with accepted_read_snapshot(path, validator=_accept, limits=LIMITS):
            pytest.fail("Missing database was accepted")
    assert not path.exists()


def test_progress_budget_aborts_long_before_row_and_is_per_invocation(tmp_path: Path) -> None:
    path = tmp_path / "source.sqlite3"
    _database(path)
    small = replace(LIMITS, progress_calls=10)
    for _ in range(2):
        with pytest.raises(ReadSnapshotError, match="interrupted"):
            with accepted_read_snapshot(path, validator=_accept, limits=small) as accepted:
                accepted.connection.execute(
                    "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n "
                    "WHERE x<1000000) SELECT sum(x) FROM n"
                ).fetchone()
    with accepted_read_snapshot(path, validator=_accept, limits=LIMITS) as accepted:
        assert accepted.connection.execute("SELECT value FROM evidence").fetchone() == (10,)


def test_limits_and_identity_are_mandatory(tmp_path: Path) -> None:
    with pytest.raises(ReadSnapshotError):
        SQLiteReadLimits("", 1, 1, 1, 1, 1)
    with pytest.raises(ReadSnapshotError):
        replace(LIMITS, value_bytes=True)
    with pytest.raises(ReadSnapshotError):
        ReadIdentity("", "3.0.0")
    path = tmp_path / "source.sqlite3"
    _database(path)
    with pytest.raises(ReadSnapshotError, match="accepted identity"):
        with accepted_read_snapshot(path, validator=lambda _: None, limits=LIMITS):
            pytest.fail("Unvalidated raw path")


def test_value_and_column_limits_apply_to_result_queries(tmp_path: Path) -> None:
    path = tmp_path / "source.sqlite3"
    _database(path)
    with pytest.raises(ReadSnapshotError, match="too big"):
        with accepted_read_snapshot(
            path, validator=_accept, limits=replace(LIMITS, value_bytes=1000)
        ) as accepted:
            accepted.connection.execute("SELECT zeroblob(1001)").fetchone()


@pytest.mark.parametrize(
    "profile,query,message",
    [
        (replace(LIMITS, columns=2), "SELECT 1,2,3", "too many columns"),
        (replace(LIMITS, sql_bytes=1000), "SELECT 1 /*" + "x" * 1000 + "*/", "too large"),
    ],
)
def test_supplied_column_and_sql_limits_are_enforced(tmp_path, profile, query, message):
    path = tmp_path / "source.sqlite3"
    _database(path)
    with pytest.raises(ReadSnapshotError, match=message):
        with accepted_read_snapshot(path, validator=_accept, limits=profile) as accepted:
            accepted.connection.execute(query).fetchone()


def test_progress_accounting_is_cumulative_across_short_queries(tmp_path):
    path = tmp_path / "source.sqlite3"
    _database(path)
    with pytest.raises(ReadSnapshotError, match="interrupted"):
        with accepted_read_snapshot(
            path, validator=_accept, limits=replace(LIMITS, progress_calls=10)
        ) as accepted:
            for _ in range(10_000):
                accepted.connection.execute("SELECT value FROM evidence").fetchone()
