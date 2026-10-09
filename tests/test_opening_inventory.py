from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.domain.opening_inventory import (
    HandlingUnitRecord,
    InventorySnapshotRecord,
    PhysicalInventoryState,
)
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.generation.master_data import generate_master_data
from operational_variance_toolkit.generation.opening_inventory import (
    generate_opening_inventory,
    validate_opening_inventory_state,
)
from operational_variance_toolkit.storage.database import connect_database, initialize_database


def test_generate_opening_inventory_creates_reconciling_state(
    tmp_path: Path, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    output_path = tmp_path / "opening.sqlite3"

    initialize_database(output_path, config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(connection, config, run_id)
        result = generate_opening_inventory(connection, config, run_id)

    with connect_database(output_path) as connection:
        connection.row_factory = sqlite3.Row
        snapshots = connection.execute(
            "SELECT item_id, location_id, qty_cases, handling_unit_id FROM inventory_snapshot "
            "WHERE run_id = ? AND snapshot_type = 'OPENING_SYSTEM'",
            (run_id,),
        ).fetchall()
        handling_units = connection.execute(
            "SELECT handling_unit_id, initial_qty_cases FROM handling_unit WHERE run_id = ?",
            (run_id,),
        ).fetchall()

    assert len(result.handling_units) == config.dimensions.item_count * 2
    assert len(result.inventory_snapshots) == config.dimensions.item_count * 2
    assert len(snapshots) == config.dimensions.item_count * 2

    snapshot_totals = {(row["item_id"], row["location_id"]): row["qty_cases"] for row in snapshots}
    assert result.physical_state.location_quantities == snapshot_totals

    for row in handling_units:
        matching_rows = [
            snap for snap in snapshots if snap["handling_unit_id"] == row["handling_unit_id"]
        ]
        assert sum(snap["qty_cases"] for snap in matching_rows) == row["initial_qty_cases"]
        assert len({snap["location_id"] for snap in matching_rows}) == 1


def test_opening_inventory_is_deterministic(tmp_path: Path, baseline_config_path: Path) -> None:
    config = load_project_config(baseline_config_path)
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"

    initialize_database(first_path, config, schema_version="1.0.0")
    initialize_database(second_path, config, schema_version="1.0.0")

    with connect_database(first_path) as first_connection:
        first_run_id = first_connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(first_connection, config, first_run_id)
        first_result = generate_opening_inventory(first_connection, config, first_run_id)

    with connect_database(second_path) as second_connection:
        second_run_id = second_connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(second_connection, config, second_run_id)
        second_result = generate_opening_inventory(second_connection, config, second_run_id)

    assert [item.initial_qty_cases for item in first_result.handling_units] == [
        item.initial_qty_cases for item in second_result.handling_units
    ]
    assert [snapshot.qty_cases for snapshot in first_result.inventory_snapshots] == [
        snapshot.qty_cases for snapshot in second_result.inventory_snapshots
    ]


def test_opening_inventory_respects_capacity_and_relationships(
    tmp_path: Path, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    output_path = tmp_path / "capacity.sqlite3"

    initialize_database(output_path, config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(connection, config, run_id)
        result = generate_opening_inventory(connection, config, run_id)

    with connect_database(output_path) as connection:
        connection.row_factory = sqlite3.Row
        capacities = {
            row["location_id"]: row["capacity_cases"]
            for row in connection.execute(
                "SELECT location_id, capacity_cases FROM location WHERE run_id = ?",
                (run_id,),
            )
        }

    for snapshot in result.inventory_snapshots:
        assert snapshot.qty_cases >= 0
        assert (
            capacities[snapshot.location_id] is None
            or snapshot.qty_cases <= capacities[snapshot.location_id]
        )

    for handling_unit in result.handling_units:
        assert handling_unit.initial_qty_cases > 0

    with connect_database(output_path) as connection:
        aggregate_violations = connection.execute(
            """
            SELECT 1
            FROM inventory_snapshot AS s
            JOIN location AS l ON l.run_id = s.run_id AND l.location_id = s.location_id
            WHERE s.run_id = ?
            GROUP BY s.location_id, l.capacity_cases
            HAVING SUM(s.qty_cases) > l.capacity_cases
            """,
            (run_id,),
        ).fetchall()
        invalid_pairs = connection.execute(
            """
            SELECT 1
            FROM inventory_snapshot AS s
            JOIN item AS i ON i.run_id = s.run_id AND i.item_id = s.item_id
            JOIN location AS l ON l.run_id = s.run_id AND l.location_id = s.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE s.run_id = ? AND i.required_zone_code != z.zone_code
            """,
            (run_id,),
        ).fetchall()

    assert aggregate_violations == []
    assert invalid_pairs == []


def test_validate_opening_inventory_state_rejects_negative_quantities(
    tmp_path: Path, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    output_path = tmp_path / "invalid.sqlite3"

    initialize_database(output_path, config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(connection, config, run_id)
        bad_state = PhysicalInventoryState(
            run_id=run_id,
            location_quantities={("ITEM-0001", "LOC-0001"): -1},
            item_quantities={"ITEM-0001": -1},
        )
        with pytest.raises(DataValidationError):
            validate_opening_inventory_state(connection, config, run_id, bad_state, [], [])


def test_validate_opening_inventory_state_rejects_aggregate_capacity_violation(
    tmp_path: Path, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    output_path = tmp_path / "aggregate-invalid.sqlite3"

    initialize_database(output_path, config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(connection, config, run_id)
        reserve_location_id, capacity = connection.execute(
            """
            SELECT l.location_id, l.capacity_cases
            FROM location AS l
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE l.run_id = ? AND z.zone_code = 'FROZEN' AND l.location_type = 'RESERVE'
            ORDER BY l.location_id
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        item_rows = connection.execute(
            "SELECT item_id FROM item "
            "WHERE run_id = ? AND required_zone_code = 'FROZEN' "
            "ORDER BY item_id LIMIT 2",
            (run_id,),
        ).fetchall()
        quantity = (int(capacity) // 2) + 1
        item_ids = [row[0] for row in item_rows]
        bad_state = PhysicalInventoryState(
            run_id=run_id,
            location_quantities={
                (item_ids[0], reserve_location_id): quantity,
                (item_ids[1], reserve_location_id): quantity,
            },
            item_quantities={
                item_ids[0]: quantity,
                item_ids[1]: quantity,
            },
        )
        handling_units = [
            HandlingUnitRecord(run_id, "HU-0001", item_ids[0], None, None, quantity, "AVAILABLE"),
            HandlingUnitRecord(run_id, "HU-0002", item_ids[1], None, None, quantity, "AVAILABLE"),
        ]
        snapshots = [
            InventorySnapshotRecord(
                run_id,
                "SNAP-0001",
                config.run.start_utc.isoformat(),
                "OPENING_SYSTEM",
                item_ids[0],
                reserve_location_id,
                "HU-0001",
                quantity,
                "opening_inventory",
            ),
            InventorySnapshotRecord(
                run_id,
                "SNAP-0002",
                config.run.start_utc.isoformat(),
                "OPENING_SYSTEM",
                item_ids[1],
                reserve_location_id,
                "HU-0002",
                quantity,
                "opening_inventory",
            ),
        ]

        with pytest.raises(DataValidationError, match="aggregate location capacity"):
            validate_opening_inventory_state(
                connection, config, run_id, bad_state, handling_units, snapshots
            )


def test_analyst_schema_has_no_hidden_truth_columns(
    tmp_path: Path, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    output_path = tmp_path / "schema.sqlite3"

    initialize_database(output_path, config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        columns = connection.execute("PRAGMA table_info(inventory_snapshot)").fetchall()
    names = {column[1] for column in columns}

    assert "true_quantity" not in names
    assert "physical_quantity" not in names
    assert "is_injected_anomaly" not in names
