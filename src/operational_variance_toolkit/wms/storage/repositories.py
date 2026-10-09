"""Schema-3 WMS persistence adapters."""

from __future__ import annotations

import sqlite3
from dataclasses import astuple, dataclass

from operational_variance_toolkit.wms.domain.foundation import WmsFoundationRecords

WMS_TABLES: tuple[str, ...] = (
    "schema_metadata",
    "simulation_run",
    "facility",
    "zone",
    "item_master",
    "location_master",
    "operator",
    "shift",
    "work_assignment",
    "event_sequence_registry",
    "wms_command",
    "inventory_transaction",
    "inventory_master",
    "trip",
    "pick_event",
    "replenishment_task",
    "qa_event",
    "inventory_adjustment",
    "system_event",
    "inventory_snapshot",
)

WMS_REPORT_VIEWS: tuple[str, ...] = (
    "wms_inventory_by_location",
    "wms_inventory_by_item",
    "wms_location_profile",
    "wms_empty_locations",
    "wms_adjustment_history",
    "wms_qa_activity",
)


@dataclass(frozen=True, slots=True)
class WmsRunMetadata:
    run_id: str
    seed: int
    schema_version: str
    generator_version: str
    config_hash: str
    facility_timezone: str
    simulation_start_utc: str
    simulation_end_utc: str
    generated_at_utc: str


class WmsFoundationRepository:
    """Persist and inspect schema-3 WMS foundation records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def run_metadata(self) -> WmsRunMetadata:
        row = self._connection.execute(
            """
            SELECT
                run_id,
                seed,
                schema_version,
                generator_version,
                config_hash,
                facility_timezone,
                simulation_start_utc,
                simulation_end_utc,
                generated_at_utc
            FROM simulation_run
            """
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("Expected one schema-3 simulation_run row")
        return WmsRunMetadata(**dict(row))

    def facility_identity(self) -> tuple[str, str]:
        row = self._connection.execute("SELECT facility_id, facility_name FROM facility").fetchone()
        if row is None:
            raise sqlite3.DatabaseError("Expected one schema-3 facility row")
        return str(row["facility_id"]), str(row["facility_name"])

    def insert_foundation(self, records: WmsFoundationRecords) -> None:
        self._connection.executemany(
            """
            INSERT INTO zone(
                run_id, zone_id, facility_id, zone_code, min_temp_f, max_temp_f, active_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.zones),
        )
        self._connection.executemany(
            """
            INSERT INTO item_master(
                run_id, item_id, item_description, category, required_zone_code,
                case_length_in, case_width_in, case_height_in, case_cube_ft3,
                case_weight_lb, cases_per_layer, layers_per_pallet, cases_per_pallet,
                fragility_score, shelf_life_days, velocity_class,
                expected_cases_per_day, active_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.items),
        )
        self._connection.executemany(
            """
            INSERT INTO location_master(
                run_id, location_id, zone_id, location_type, aisle_code, bay_number,
                level_number, position_number, pallet_capacity, pickable_flag, active_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.locations),
        )
        self._connection.executemany(
            """
            INSERT INTO operator(
                run_id, operator_id, role, home_zone_id, shift_code,
                experience_months, active_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.operators),
        )
        self._connection.executemany(
            """
            INSERT INTO shift(
                run_id, shift_id, facility_id, shift_code, start_utc, end_utc,
                operating_date_local
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.shifts),
        )
        self._connection.executemany(
            """
            INSERT INTO work_assignment(
                run_id, work_assignment_id, operator_id, shift_id, role, zone_id,
                start_utc, end_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.work_assignments),
        )
        self._connection.executemany(
            """
            INSERT INTO inventory_master(
                run_id, location_id, item_id, qty_on_hand_cases, code_date,
                reorder_trigger_cases, minimum_qty_cases, target_qty_cases,
                maximum_qty_cases, last_transaction_id, last_updated_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.inventory),
        )
        self._connection.executemany(
            """
            INSERT INTO inventory_snapshot(
                run_id, snapshot_batch_id, snapshot_line_id, snapshot_utc, snapshot_type,
                location_id, item_id, qty_on_hand_cases, code_date,
                last_transaction_id, source_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (astuple(record) for record in records.opening_snapshot),
        )

    def table_names(self) -> set[str]:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {str(row["name"]) for row in rows}

    def view_names(self) -> set[str]:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view'"
        ).fetchall()
        return {str(row["name"]) for row in rows}

    def table_columns(self, table_name: str) -> set[str]:
        rows = self._connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        return {str(row["name"]) for row in rows}

    def table_counts(self) -> dict[str, int]:
        return {
            table_name: int(
                self._connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            )
            for table_name in WMS_TABLES
        }

    def user_version(self) -> int:
        return int(self._connection.execute("PRAGMA user_version").fetchone()[0])

    def schema_versions(self) -> list[str]:
        return [
            str(row["schema_version"])
            for row in self._connection.execute(
                "SELECT schema_version FROM schema_metadata ORDER BY schema_version"
            ).fetchall()
        ]

    def foreign_key_violations(self) -> list[sqlite3.Row]:
        return self._connection.execute("PRAGMA foreign_key_check").fetchall()

    def live_totals_by_zone(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (str(row["zone_code"]), int(row["qty_cases"]))
            for row in self._connection.execute(
                """
                SELECT zone.zone_code, SUM(inventory.qty_on_hand_cases) AS qty_cases
                FROM inventory_master AS inventory
                JOIN location_master AS location USING(run_id, location_id)
                JOIN zone USING(run_id, zone_id)
                GROUP BY zone.zone_code
                ORDER BY zone.zone_code
                """
            )
        )

    def snapshot_batches(self) -> tuple[tuple[str, str, str, int], ...]:
        return tuple(
            (str(row[0]), str(row[1]), str(row[2]), int(row[3]))
            for row in self._connection.execute(
                """
                SELECT snapshot_batch_id, snapshot_type, snapshot_utc, COUNT(*)
                FROM inventory_snapshot
                GROUP BY snapshot_batch_id, snapshot_type, snapshot_utc
                ORDER BY snapshot_utc, snapshot_batch_id
                """
            )
        )

    def canonical_foundation_rows(self) -> dict[str, list[tuple[object, ...]]]:
        rows_by_table: dict[str, list[tuple[object, ...]]] = {}
        for table_name in (
            "zone",
            "item_master",
            "location_master",
            "operator",
            "shift",
            "work_assignment",
            "inventory_master",
            "inventory_snapshot",
        ):
            columns = [
                str(row["name"])
                for row in self._connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            ]
            order_by = ", ".join(f'"{column}"' for column in columns)
            rows = self._connection.execute(
                f'SELECT * FROM "{table_name}" ORDER BY {order_by}'
            ).fetchall()
            rows_by_table[table_name] = [tuple(row[column] for column in columns) for row in rows]
        return rows_by_table

    def canonical_wms_rows(self) -> dict[str, list[tuple[object, ...]]]:
        """Return all deterministic WMS content excluding execution timestamps."""

        excluded = {
            "schema_metadata": {"created_at_utc"},
            "simulation_run": {"generated_at_utc"},
        }
        rows_by_table: dict[str, list[tuple[object, ...]]] = {}
        for table_name in WMS_TABLES:
            columns = [
                str(row["name"])
                for row in self._connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                if str(row["name"]) not in excluded.get(table_name, set())
            ]
            projection = ", ".join(f'"{column}"' for column in columns)
            ordering = ", ".join(f'"{column}"' for column in columns)
            rows_by_table[table_name] = [
                tuple(row[column] for column in columns)
                for row in self._connection.execute(
                    f'SELECT {projection} FROM "{table_name}" ORDER BY {ordering}'
                ).fetchall()
            ]
        return rows_by_table
