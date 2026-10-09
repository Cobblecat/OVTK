"""Focused Slice 1 tests for the schema-3 WMS foundation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from operational_variance_toolkit.storage.database import connect_database
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.initialize import (
    canonical_wms_foundation_content,
    initialize_wms_foundation,
)
from operational_variance_toolkit.wms.domain.inventory import (
    ItemMasterRecord,
    calculate_case_cube_ft3,
    calculate_cases_per_pallet,
    calculate_location_maximum_cases,
)


def _initialize(config_path, output_path):
    return initialize_wms_foundation(
        config_path,
        output_path,
        generated_at_utc=datetime(2026, 8, 2, tzinfo=UTC),
    )


def test_schema_3_creation_metadata_and_required_tables(baseline_config_path, tmp_path):
    result = _initialize(baseline_config_path, tmp_path / "foundation.sqlite3")
    with sqlite3.connect(result.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert (
            connection.execute("SELECT schema_version FROM schema_metadata").fetchone()[0]
            == "3.0.0"
        )
        columns = [row[1] for row in connection.execute("PRAGMA table_info(simulation_run)")]
        assert "scenario_name" not in columns
        assert "scenario_version" not in columns
        assert {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        } >= {
            "schema_metadata",
            "simulation_run",
            "item_master",
            "location_master",
            "inventory_master",
            "inventory_transaction",
            "inventory_snapshot",
        }
        assert result.validation.passed


@pytest.mark.parametrize("dimensions", [(12, 10, 8), (1, 1, 1)])
def test_item_cube_and_pallet_calculations(dimensions):
    assert calculate_case_cube_ft3(*dimensions) == round(
        dimensions[0] * dimensions[1] * dimensions[2] / 1728, 6
    )
    assert calculate_cases_per_pallet(10, 4) == 40
    assert calculate_location_maximum_cases(2, 40) == 80


@pytest.mark.parametrize(
    "call",
    [
        lambda: calculate_case_cube_ft3(0, 1, 1),
        lambda: calculate_cases_per_pallet(1, 0),
        lambda: calculate_location_maximum_cases(0, 1),
    ],
)
def test_invalid_calculations_are_rejected(call):
    with pytest.raises(ValueError):
        call()


def test_item_record_rejects_inconsistent_calculations():
    with pytest.raises(ValueError):
        ItemMasterRecord(
            run_id="run",
            item_id="item",
            item_description="Item",
            category="cat",
            required_zone_code="AMBIENT",
            case_length_in=12,
            case_width_in=10,
            case_height_in=8,
            case_cube_ft3=1,
            case_weight_lb=10,
            cases_per_layer=10,
            layers_per_pallet=4,
            cases_per_pallet=40,
            fragility_score=0.1,
            shelf_life_days=30,
            velocity_class="A",
            expected_cases_per_day=1,
        )


def test_generated_locations_have_no_prohibited_columns_and_valid_inventory(
    baseline_config_path, tmp_path
):
    result = _initialize(baseline_config_path, tmp_path / "foundation.sqlite3")
    prohibited = {
        "equipment_area",
        "capacity_cases",
        "pallet_id",
        "handling_unit_id",
        "physical_quantity",
    }
    with sqlite3.connect(result.database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(location_master)")}
        assert not columns & prohibited
        assert (
            connection.execute("SELECT COUNT(*) FROM inventory_master").fetchone()[0]
            == connection.execute("SELECT COUNT(*) FROM location_master").fetchone()[0]
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM inventory_master WHERE maximum_qty_cases > 0"
            ).fetchone()[0]
            > 0
        )
        assert (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM inventory_master AS i
                JOIN location_master AS l USING(run_id, location_id)
                JOIN item_master AS m USING(run_id, item_id)
                WHERE l.location_type = 'PICK'
                    AND i.maximum_qty_cases != l.pallet_capacity * m.cases_per_pallet
                """
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM inventory_master AS i
                JOIN inventory_snapshot AS s USING(run_id, location_id)
                WHERE s.snapshot_type = 'OPENING_SYSTEM'
                    AND (i.item_id IS NOT s.item_id
                        OR i.qty_on_hand_cases != s.qty_on_hand_cases
                        OR i.code_date IS NOT s.code_date)
                """
            ).fetchone()[0]
            == 0
        )


def test_foundation_content_is_deterministic(baseline_config_path, tmp_path):
    _initialize(baseline_config_path, tmp_path / "one.sqlite3")
    _initialize(baseline_config_path, tmp_path / "two.sqlite3")
    assert canonical_wms_foundation_content(
        tmp_path / "one.sqlite3"
    ) == canonical_wms_foundation_content(tmp_path / "two.sqlite3")


@pytest.mark.parametrize(
    "corruption",
    [
        "UPDATE item_master SET case_cube_ft3 = case_cube_ft3 + 1",
        """
        UPDATE inventory_master
        SET qty_on_hand_cases = qty_on_hand_cases + 1
        WHERE location_id = (
            SELECT location_id FROM inventory_master WHERE item_id IS NOT NULL LIMIT 1
        )
        """,
        """
        UPDATE item_master
        SET required_zone_code = CASE required_zone_code
            WHEN 'AMBIENT' THEN 'FROZEN' ELSE 'AMBIENT' END
        WHERE item_id = (
            SELECT item_id FROM inventory_master WHERE item_id IS NOT NULL LIMIT 1
        )
        """,
        """
        UPDATE inventory_master
        SET code_date = NULL
        WHERE location_id = (
            SELECT location_id
            FROM inventory_master
            WHERE qty_on_hand_cases > 0
            LIMIT 1
        )
        """,
    ],
)
def test_validation_fails_after_foundation_corruption(baseline_config_path, tmp_path, corruption):
    result = _initialize(baseline_config_path, tmp_path / "corrupt.sqlite3")
    with sqlite3.connect(result.database_path) as connection:
        connection.execute(corruption)
        validation = validate_wms_dataset(connection)
    assert not validation.passed


def test_schema_3_constraints_foreign_keys_and_indexes(baseline_config_path, tmp_path):
    result = _initialize(baseline_config_path, tmp_path / "constraints.sqlite3")
    with connect_database(result.database_path) as connection:
        run_id, location_id = connection.execute(
            "SELECT run_id, location_id FROM inventory_master LIMIT 1"
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE inventory_master
                SET item_id = 'ITEM-DOES-NOT-EXIST'
                WHERE run_id = ? AND location_id = ?
                """,
                (run_id, location_id),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE item_master
                SET cases_per_pallet = cases_per_pallet + 1
                WHERE run_id = ?
                """,
                (run_id,),
            )
        indexes = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert {
            "idx_wms_inventory_item",
            "idx_wms_transaction_sequence",
            "idx_wms_snapshot_batch",
        } <= indexes


def test_inventory_transaction_is_immutable(baseline_config_path, tmp_path):
    result = _initialize(baseline_config_path, tmp_path / "immutable.sqlite3")
    with sqlite3.connect(result.database_path) as connection:
        run_id, location_id, item_id = connection.execute(
            """
            SELECT run_id, location_id, item_id
            FROM inventory_master
            WHERE item_id IS NOT NULL
            LIMIT 1
            """
        ).fetchone()
        sequence = connection.execute(
            "SELECT COALESCE(MAX(event_sequence), 0) + 1 FROM event_sequence_registry"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO event_sequence_registry VALUES (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                sequence,
                "TEST",
                "test",
                "2026-08-02T00:00:00Z",
                "2026-08-02T00:00:00Z",
            ),
        )
        values = (
            run_id,
            "TX-TEST",
            "TG-TEST",
            "CMD-TEST",
            sequence,
            1,
            "ADJUSTMENT",
            location_id,
            item_id,
            1,
            10,
            11,
            "2026-08-02T00:00:00Z",
            "2026-08-02T00:00:00Z",
            "TEST",
            "TEST-1",
        )
        connection.execute(
            """
            INSERT INTO inventory_transaction(
                run_id, transaction_id, transaction_group_id, command_id,
                event_sequence, line_number, transaction_type, location_id, item_id,
                qty_delta_cases, balance_before_cases, balance_after_cases,
                event_utc, recorded_utc, source_record_type, source_record_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE inventory_transaction
                SET qty_delta_cases = 2
                WHERE transaction_id = 'TX-TEST'
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM inventory_transaction WHERE transaction_id = 'TX-TEST'")
