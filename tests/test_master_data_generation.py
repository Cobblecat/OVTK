from __future__ import annotations

import sqlite3
from pathlib import Path

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.generation.master_data import generate_master_data
from operational_variance_toolkit.storage.database import connect_database, initialize_database


def test_generate_master_data_creates_expected_master_tables(
    tmp_path: Path, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    output_path = tmp_path / "master.sqlite3"

    initialize_database(output_path, config, schema_version="1.0.0")

    with connect_database(output_path) as connection:
        run_id = connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        counts = generate_master_data(connection, config, run_id)

    assert counts["zone"] == config.dimensions.zone_count
    assert counts["item"] == config.dimensions.item_count
    assert counts["operator"] == (
        config.dimensions.selector_count
        + config.dimensions.replenisher_count
        + config.dimensions.qa_operator_count
        + 1
    )
    assert counts["shift"] == config.dimensions.shift_count
    assert counts["slot_assignment"] == config.dimensions.item_count
    assert counts["work_assignment"] == (
        config.dimensions.selector_count
        + config.dimensions.replenisher_count
        + config.dimensions.qa_operator_count
        + 1
    )

    with connect_database(output_path) as connection:
        connection.row_factory = sqlite3.Row
        zone_rows = connection.execute(
            "SELECT zone_id, zone_code FROM zone ORDER BY zone_id"
        ).fetchall()
        location_rows = connection.execute(
            "SELECT location_id, zone_id, location_type, pickable_flag FROM location"
        ).fetchall()
        slot_rows = connection.execute(
            "SELECT item_id, pick_location_id FROM slot_assignment"
        ).fetchall()
        invalid_slot_zone_rows = connection.execute(
            """
            SELECT 1
            FROM slot_assignment AS sa
            JOIN item AS i ON i.run_id = sa.run_id AND i.item_id = sa.item_id
            JOIN location AS l ON l.run_id = sa.run_id AND l.location_id = sa.pick_location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE i.required_zone_code != z.zone_code
            """
        ).fetchall()
        overlapping_slot_rows = connection.execute(
            """
            SELECT 1
            FROM slot_assignment
            WHERE effective_end_utc IS NULL
            GROUP BY run_id, pick_location_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()
        operator_rows = connection.execute(
            "SELECT operator_id, role FROM operator ORDER BY operator_id"
        ).fetchall()

    assert {row["zone_code"] for row in zone_rows} == {"FROZEN", "CHILLED", "AMBIENT"}
    assert len(zone_rows) == 3
    assert any(
        row["location_type"] == "PICK" and row["pickable_flag"] == 1 for row in location_rows
    )
    assert len(slot_rows) == config.dimensions.item_count
    assert invalid_slot_zone_rows == []
    assert overlapping_slot_rows == []
    assert any(row["role"] == "SELECTOR" for row in operator_rows)


def test_generate_master_data_is_deterministic(tmp_path: Path, baseline_config_path: Path) -> None:
    config = load_project_config(baseline_config_path)
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"

    initialize_database(first_path, config, schema_version="1.0.0")
    initialize_database(second_path, config, schema_version="1.0.0")

    with connect_database(first_path) as first_connection:
        first_run_id = first_connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(first_connection, config, first_run_id)

    with connect_database(second_path) as second_connection:
        second_run_id = second_connection.execute("SELECT run_id FROM simulation_run").fetchone()[0]
        generate_master_data(second_connection, config, second_run_id)

    with connect_database(first_path) as first_connection:
        first_connection.row_factory = sqlite3.Row
        first_rows = first_connection.execute(
            "SELECT item_id, item_description, required_zone_code, velocity_class "
            "FROM item ORDER BY item_id"
        ).fetchall()

    with connect_database(second_path) as second_connection:
        second_connection.row_factory = sqlite3.Row
        second_rows = second_connection.execute(
            "SELECT item_id, item_description, required_zone_code, velocity_class "
            "FROM item ORDER BY item_id"
        ).fetchall()

    assert [tuple(row) for row in first_rows] == [tuple(row) for row in second_rows]
