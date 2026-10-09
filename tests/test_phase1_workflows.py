from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from operational_variance_toolkit.application.phase1 import (
    describe_phase1_database,
    initialize_phase1_database,
    validate_phase1_database,
)
from operational_variance_toolkit.errors import (
    DatabaseError,
    DataValidationError,
    OutputExistsError,
)
from operational_variance_toolkit.storage.repositories import PHASE1_TABLES


def test_initialize_database_workflow_creates_valid_phase1_database(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "phase1.sqlite3"
    config_path = write_phase1_config(database_path)

    result = initialize_phase1_database(config_path)

    assert result.database_path == database_path
    assert result.run_metadata.run_id.startswith("RUN-")
    assert result.run_metadata.scenario_name == "baseline"
    assert result.run_metadata.scenario_version == "0.1.0"
    assert result.run_metadata.seed == 20260801
    assert result.run_metadata.config_hash == result.config_hash
    assert result.validation.passed
    assert result.counts["simulation_run"] == 1
    assert result.counts["zone"] == 3
    assert result.counts["item"] == 96
    assert result.counts["slot_assignment"] == 96
    assert result.counts["handling_unit"] == 192
    assert result.counts["inventory_snapshot"] == 192
    assert database_path.exists()


def test_initialize_database_workflow_refuses_existing_output(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "existing.sqlite3"
    database_path.write_bytes(b"already here")
    config_path = write_phase1_config(database_path)

    with pytest.raises(OutputExistsError):
        initialize_phase1_database(config_path)

    assert database_path.read_bytes() == b"already here"


def test_initialize_database_workflow_cleans_up_after_generation_failure(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "cleanup.sqlite3"
    config_path = write_phase1_config(database_path)

    def fail_generation(*args, **kwargs) -> None:
        raise DataValidationError("planned failure")

    monkeypatch.setattr(
        "operational_variance_toolkit.application.phase1.generate_opening_inventory",
        fail_generation,
    )

    with pytest.raises(DataValidationError, match="planned failure"):
        initialize_phase1_database(config_path)

    assert not database_path.exists()
    assert not database_path.with_name(f"{database_path.name}-wal").exists()
    assert not database_path.with_name(f"{database_path.name}-shm").exists()


def test_validate_database_workflow_reports_clean_dataset(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "valid.sqlite3"
    initialize_phase1_database(write_phase1_config(database_path))

    result = validate_phase1_database(database_path)

    assert result.validation.passed
    assert result.validation.hard_failures == ()
    assert result.validation.warnings == ()


def test_validate_database_workflow_reports_hard_failures_for_corrupted_database(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "corrupt.sqlite3"
    initialize_phase1_database(write_phase1_config(database_path))

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DELETE FROM handling_unit WHERE handling_unit_id = 'HU-0001'")
        connection.commit()

    result = validate_phase1_database(database_path)

    assert not result.validation.passed
    assert any(issue.category == "foreign_keys" for issue in result.validation.hard_failures)
    assert any(issue.category == "opening_inventory" for issue in result.validation.hard_failures)


def test_validate_database_workflow_rejects_missing_or_malformed_database(tmp_path: Path) -> None:
    with pytest.raises(DatabaseError, match="does not exist"):
        validate_phase1_database(tmp_path / "missing.sqlite3")

    malformed_path = tmp_path / "malformed.sqlite3"
    malformed_path.write_text("not sqlite", encoding="utf-8")

    with pytest.raises(DatabaseError, match="Unable to validate database"):
        validate_phase1_database(malformed_path)


def test_describe_database_workflow_returns_factual_fields(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "describe.sqlite3"
    init_result = initialize_phase1_database(write_phase1_config(database_path))

    result = describe_phase1_database(database_path)

    assert result.run_metadata == init_result.run_metadata
    assert result.table_counts["item"] == 96
    assert result.table_counts["handling_unit"] == 192
    assert {zone for zone, _ in result.opening_totals_by_zone} == {"AMBIENT", "CHILLED", "FROZEN"}
    assert all(qty_cases > 0 for _, qty_cases in result.opening_totals_by_zone)
    assert result.validation.passed


def test_initialized_database_contains_only_phase1_tables(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "scope.sqlite3"
    initialize_phase1_database(write_phase1_config(database_path))

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert table_names == set(PHASE1_TABLES)
