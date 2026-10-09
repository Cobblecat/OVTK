from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest

from operational_variance_toolkit.console.session import ConsoleMode, ConsoleSession
from operational_variance_toolkit.errors import DatabaseError, DataValidationError


def _session(tmp_path: Path) -> ConsoleSession:
    return ConsoleSession(tmp_path, tmp_path / "workspace")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_session_defaults_and_transitions_for_valid_schema3_database(
    console_wms_path: Path, tmp_path: Path
) -> None:
    session = _session(tmp_path)

    assert session.mode is ConsoleMode.NO_DATABASE
    assert session.prompt == "WMS[NO DB]> "
    assert session.result_limit == 25
    assert session.display_format == "vertical"
    assert session.timestamp_preference == "utc"

    session.open_database(console_wms_path)

    assert session.mode is ConsoleMode.READ_ONLY
    assert session.prompt == "WMS[RO:schema3_console]> "
    assert session.schema_version == "3.0.0"
    assert session.run_id is not None
    assert session.facility_id == "FAC-001"
    assert session.validation is not None and session.validation.passed
    assert session.close_database()
    assert session.mode is ConsoleMode.NO_DATABASE
    assert not session.close_database()


def test_active_connection_is_uri_read_only_and_query_only(
    console_wms_path: Path, tmp_path: Path
) -> None:
    session = _session(tmp_path)
    session.open_database(console_wms_path)

    assert session.connection.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
        session.connection.execute("CREATE TABLE console_write_probe(value INTEGER)")
    session.close()


def test_validation_description_and_repeated_open_preserve_source_bytes(
    console_wms_path: Path, tmp_path: Path
) -> None:
    first_path = tmp_path / "First Database.sqlite3"
    second_path = tmp_path / "Second Database.sqlite3"
    shutil.copy2(console_wms_path, first_path)
    shutil.copy2(console_wms_path, second_path)
    before = {path: _sha256(path) for path in (first_path, second_path)}
    session = _session(tmp_path)

    session.open_database(first_path)
    first_connection = session.connection
    assert session.validate_database().passed
    assert session.describe_database().validation.passed
    session.open_database(second_path)

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        first_connection.execute("SELECT 1")
    second_connection = session.connection
    session.close()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        second_connection.execute("SELECT 1")
    assert {path: _sha256(path) for path in (first_path, second_path)} == before


@pytest.mark.parametrize("user_version", [1, 2, 4])
def test_open_rejects_legacy_and_unsupported_databases(user_version: int, tmp_path: Path) -> None:
    database = tmp_path / f"schema-{user_version}.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(f"PRAGMA user_version = {user_version}")

    expected = "legacy" if user_version in {1, 2} else "unsupported"
    with pytest.raises(DataValidationError, match=expected):
        _session(tmp_path).open_database(database)


def test_open_rejects_missing_malformed_and_invalid_schema3_databases(
    console_wms_path: Path, tmp_path: Path
) -> None:
    with pytest.raises(DatabaseError, match="does not exist"):
        _session(tmp_path).open_database(tmp_path / "missing.sqlite3")

    malformed = tmp_path / "malformed.sqlite3"
    malformed.write_bytes(b"not a sqlite database")
    with pytest.raises(DatabaseError, match="Unable to open database"):
        _session(tmp_path).open_database(malformed)

    invalid = tmp_path / "invalid.sqlite3"
    shutil.copy2(console_wms_path, invalid)
    with sqlite3.connect(invalid) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DELETE FROM facility")
    with pytest.raises(DataValidationError, match="invalid schema-3 WMS"):
        _session(tmp_path).open_database(invalid)


def test_failed_replacement_open_keeps_existing_connection(
    console_wms_path: Path, tmp_path: Path
) -> None:
    session = _session(tmp_path)
    session.open_database(console_wms_path)
    existing_connection = session.connection

    with pytest.raises(DatabaseError):
        session.open_database(tmp_path / "missing.sqlite3")

    assert session.connection is existing_connection
    assert session.connection.execute("SELECT 1").fetchone()[0] == 1
    session.close()
