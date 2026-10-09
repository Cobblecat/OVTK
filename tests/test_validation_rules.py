from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from operational_variance_toolkit.application.phase1 import (
    initialize_phase1_database,
    validate_phase1_database,
)


def test_validation_reports_unsupported_schema_version(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "unsupported.sqlite3"
    initialize_phase1_database(write_phase1_config(database_path))

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 999")
        connection.commit()

    result = validate_phase1_database(database_path)

    assert not result.validation.passed
    assert any(issue.category == "schema" for issue in result.validation.hard_failures)


def test_validation_reports_opening_capacity_failure(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "capacity.sqlite3"
    initialize_phase1_database(write_phase1_config(database_path))

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE inventory_snapshot
            SET qty_cases = (
                SELECT capacity_cases + 1
                FROM location
                WHERE location.run_id = inventory_snapshot.run_id
                    AND location.location_id = inventory_snapshot.location_id
            )
            WHERE snapshot_id = 'SNAP-0001'
            """
        )
        connection.commit()

    result = validate_phase1_database(database_path)

    assert not result.validation.passed
    assert any(
        "capacity" in issue.message
        for issue in result.validation.hard_failures
        if issue.category == "opening_inventory"
    )
