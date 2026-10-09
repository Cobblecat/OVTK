from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import DatabaseError, OutputExistsError
from operational_variance_toolkit.storage.database import connect_database, initialize_database
from operational_variance_toolkit.storage.repositories import PHASE2_ONLY_TABLES


@pytest.fixture()
def sample_config(baseline_config_path: Path):
    return load_project_config(baseline_config_path)


def test_schema_creates_database_and_metadata(tmp_path: Path, sample_config) -> None:
    output_path = tmp_path / "phase1.sqlite3"

    initialize_database(
        output_path,
        sample_config,
        schema_version="1.0.0",
        generated_at_utc=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
    )

    assert output_path.exists()

    with connect_database(output_path) as connection:
        connection.row_factory = sqlite3.Row
        schema_version = connection.execute("SELECT schema_version FROM schema_metadata").fetchone()
        run_row = connection.execute(
            "SELECT run_id, scenario_name, scenario_version, seed FROM simulation_run"
        ).fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert schema_version is not None
    assert schema_version["schema_version"] == "1.0.0"
    assert run_row is not None
    assert run_row["scenario_name"] == "baseline"
    assert run_row["scenario_version"] == "0.1.0"
    assert run_row["seed"] == 20260801
    assert foreign_keys == 1
    assert user_version == 1


def test_phase2_schema_creates_transaction_tables(tmp_path: Path, sample_config) -> None:
    output_path = tmp_path / "phase2.sqlite3"

    initialize_database(
        output_path,
        sample_config,
        schema_version="2.0.0",
        generated_at_utc=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
    )

    with connect_database(output_path) as connection:
        connection.row_factory = sqlite3.Row
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        schema_version = connection.execute("SELECT schema_version FROM schema_metadata").fetchone()

    assert user_version == 2
    assert schema_version["schema_version"] == "2.0.0"
    assert set(PHASE2_ONLY_TABLES).issubset(table_names)


def test_invalid_parent_reference_fails(tmp_path: Path, sample_config) -> None:
    output_path = tmp_path / "phase1.sqlite3"
    initialize_database(output_path, sample_config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO zone(run_id, zone_id, facility_id, zone_code, active_flag) "
                "VALUES (?, ?, ?, ?, ?)",
                ("RUN-TEST", "ZONE-0001", "FAC-999", "FROZEN", 1),
            )
            connection.commit()


def test_duplicate_location_and_assignment_constraints_fail(tmp_path: Path, sample_config) -> None:
    output_path = tmp_path / "phase1.sqlite3"
    initialize_database(output_path, sample_config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        connection.execute(
            "INSERT INTO facility(run_id, facility_id, facility_name, timezone) "
            "VALUES (?, ?, ?, ?)",
            (run_id, "FAC-002", "Synthetic", "America/New_York"),
        )
        connection.execute(
            "INSERT INTO zone(run_id, zone_id, facility_id, zone_code, active_flag) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, "ZONE-FRZ", "FAC-002", "FROZEN", 1),
        )
        connection.execute(
            "INSERT INTO location(run_id, location_id, zone_id, location_type, "
            "aisle_code, bay_number, level_number, position_number, pickable_flag, "
            "active_flag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "LOC-001", "ZONE-FRZ", "PICK", "A", 1, 1, 1, 1, 1),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO location(run_id, location_id, zone_id, location_type, "
                "aisle_code, bay_number, level_number, position_number, pickable_flag, "
                "active_flag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "LOC-001", "ZONE-FRZ", "PICK", "A", 1, 1, 1, 1, 1),
            )
            connection.commit()


def test_negative_inventory_fails(tmp_path: Path, sample_config) -> None:
    output_path = tmp_path / "phase1.sqlite3"
    initialize_database(output_path, sample_config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        connection.execute(
            "INSERT INTO facility(run_id, facility_id, facility_name, timezone) "
            "VALUES (?, ?, ?, ?)",
            (run_id, "FAC-002", "Synthetic", "America/New_York"),
        )
        connection.execute(
            "INSERT INTO zone(run_id, zone_id, facility_id, zone_code, active_flag) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, "ZONE-FRZ", "FAC-002", "FROZEN", 1),
        )
        connection.execute(
            "INSERT INTO location(run_id, location_id, zone_id, location_type, "
            "aisle_code, bay_number, level_number, position_number, pickable_flag, "
            "active_flag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "LOC-001", "ZONE-FRZ", "PICK", "A", 1, 1, 1, 1, 1),
        )
        connection.execute(
            "INSERT INTO item(run_id, item_id, item_description, category, "
            "required_zone_code, cases_per_pallet, case_weight_lb, case_cube_ft3, "
            "fragility_score, shelf_life_days, velocity_class, expected_cases_per_day, "
            "active_flag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                "ITEM-001",
                "Test item",
                "Produce",
                "FROZEN",
                1,
                1.0,
                1.0,
                0.1,
                30,
                "A",
                10.0,
                1,
            ),
        )
        connection.execute(
            "INSERT INTO handling_unit(run_id, handling_unit_id, item_id, initial_qty_cases, "
            "status) VALUES (?, ?, ?, ?, ?)",
            (run_id, "HU-001", "ITEM-001", 5, "AVAILABLE"),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO inventory_snapshot(run_id, snapshot_id, snapshot_utc, "
                "snapshot_type, item_id, location_id, handling_unit_id, qty_cases, "
                "source_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    "SNAP-001",
                    "2026-05-04T07:00:00Z",
                    "OPENING_SYSTEM",
                    "ITEM-001",
                    "LOC-001",
                    "HU-001",
                    -1,
                    "GEN",
                ),
            )
            connection.commit()


def test_existing_output_protection(tmp_path: Path, sample_config) -> None:
    output_path = tmp_path / "phase1.sqlite3"
    initialize_database(output_path, sample_config, schema_version="1.0.0")

    with pytest.raises(OutputExistsError):
        initialize_database(output_path, sample_config, schema_version="1.0.0")


def test_failed_initialization_removes_incomplete_database(
    tmp_path: Path, sample_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "phase1.sqlite3"

    def fail_connect(*args: Any, **kwargs: Any) -> Any:
        raise sqlite3.DatabaseError("boom")

    monkeypatch.setattr(
        "operational_variance_toolkit.storage.database.sqlite3.connect", fail_connect
    )

    with pytest.raises(DatabaseError):
        initialize_database(output_path, sample_config, schema_version="1.0.0")

    assert not output_path.exists()
