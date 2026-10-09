"""SQLite-backed repositories for Phase 1 master and opening inventory data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from operational_variance_toolkit.domain.operations import (
    InventoryAdjustmentRecord,
    InventorySnapshotRecord,
    PickEventRecord,
    QaEventRecord,
    ReplenishmentTaskRecord,
    SystemEventRecord,
    TripRecord,
)
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.storage.schema import PHASE2_SCHEMA_VERSION, SCHEMA_VERSION

PHASE1_TABLES: tuple[str, ...] = (
    "schema_metadata",
    "simulation_run",
    "facility",
    "zone",
    "location",
    "item",
    "operator",
    "shift",
    "slot_assignment",
    "work_assignment",
    "handling_unit",
    "inventory_snapshot",
)

PHASE2_ONLY_TABLES: tuple[str, ...] = (
    "event_sequence_registry",
    "trip",
    "pick_event",
    "replenishment_task",
    "qa_event",
    "inventory_adjustment",
    "system_event",
)

PHASE2_TABLES: tuple[str, ...] = (*PHASE1_TABLES, *PHASE2_ONLY_TABLES)


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    scenario_name: str
    scenario_version: str
    seed: int
    schema_version: str
    generator_version: str
    config_hash: str
    facility_timezone: str
    simulation_start_utc: str
    simulation_end_utc: str
    generated_at_utc: str


class OpeningInventoryRepository:
    """Persist and read opening inventory records without embedding SQL in generation logic."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_items(self, run_id: str) -> list[tuple[str, str, str, int]]:
        rows = self._connection.execute(
            "SELECT item_id, required_zone_code, velocity_class, cases_per_pallet "
            "FROM item WHERE run_id = ? ORDER BY item_id",
            (run_id,),
        ).fetchall()
        return [(row[0], row[1], row[2], int(row[3])) for row in rows]

    def get_forward_location_for_item(self, run_id: str, item_id: str) -> str | None:
        row = self._connection.execute(
            "SELECT l.location_id "
            "FROM location AS l "
            "JOIN slot_assignment AS sa "
            "ON sa.run_id = l.run_id AND sa.pick_location_id = l.location_id "
            "WHERE l.run_id = ? AND sa.item_id = ? "
            "ORDER BY l.location_id LIMIT 1",
            (run_id, item_id),
        ).fetchone()
        return row[0] if row else None

    def list_reserve_locations_for_zone(self, run_id: str, required_zone_code: str) -> list[str]:
        rows = self._connection.execute(
            "SELECT l.location_id "
            "FROM location AS l "
            "JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id "
            "WHERE l.run_id = ? AND l.location_type = 'RESERVE' AND z.zone_code = ? "
            "ORDER BY l.location_id",
            (run_id, required_zone_code),
        ).fetchall()
        return [row[0] for row in rows]

    def get_location_details(
        self, run_id: str, location_id: str
    ) -> tuple[str, int, int | None] | None:
        row = self._connection.execute(
            "SELECT location_type, pickable_flag, capacity_cases "
            "FROM location WHERE run_id = ? AND location_id = ?",
            (run_id, location_id),
        ).fetchone()
        if row is None:
            return None
        return row[0], int(row[1]), row[2]

    def get_item_details(self, run_id: str, item_id: str) -> tuple[str, str] | None:
        row = self._connection.execute(
            "SELECT required_zone_code, velocity_class FROM item WHERE run_id = ? AND item_id = ?",
            (run_id, item_id),
        ).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def item_is_valid_at_location(self, run_id: str, item_id: str, location_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT
                i.required_zone_code,
                z.zone_code,
                l.location_type,
                sa.assignment_id
            FROM item AS i
            JOIN location AS l ON l.run_id = i.run_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            LEFT JOIN slot_assignment AS sa
                ON sa.run_id = i.run_id
                AND sa.item_id = i.item_id
                AND sa.pick_location_id = l.location_id
                AND sa.effective_end_utc IS NULL
            WHERE i.run_id = ? AND i.item_id = ? AND l.location_id = ?
            """,
            (run_id, item_id, location_id),
        ).fetchone()
        if row is None:
            return False

        required_zone_code, location_zone_code, location_type, assignment_id = row
        if required_zone_code != location_zone_code:
            return False
        if location_type == "PICK":
            return assignment_id is not None
        return location_type == "RESERVE"

    def insert_handling_unit(
        self,
        run_id: str,
        handling_unit_id: str,
        item_id: str,
        quantity: int,
    ) -> None:
        if (
            self._connection.execute(
                "SELECT 1 FROM handling_unit WHERE run_id = ? AND handling_unit_id = ?",
                (run_id, handling_unit_id),
            ).fetchone()
            is not None
        ):
            raise DataValidationError("Duplicate handling-unit identifier")

        self._connection.execute(
            """
            INSERT INTO handling_unit(
                run_id,
                handling_unit_id,
                item_id,
                lot_code,
                expiration_date,
                initial_qty_cases,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, handling_unit_id, item_id, None, None, quantity, "AVAILABLE"),
        )

    def insert_snapshot(
        self,
        run_id: str,
        snapshot_id: str,
        snapshot_utc: str,
        snapshot_type: str,
        item_id: str,
        location_id: str,
        handling_unit_id: str,
        qty_cases: int,
        source_code: str,
    ) -> None:
        if (
            self._connection.execute(
                "SELECT 1 FROM inventory_snapshot WHERE run_id = ? AND snapshot_id = ?",
                (run_id, snapshot_id),
            ).fetchone()
            is not None
        ):
            raise DataValidationError("Duplicate inventory snapshot identifier")

        self._connection.execute(
            """
            INSERT INTO inventory_snapshot(
                run_id,
                snapshot_id,
                snapshot_utc,
                snapshot_type,
                item_id,
                location_id,
                handling_unit_id,
                qty_cases,
                source_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                snapshot_id,
                snapshot_utc,
                snapshot_type,
                item_id,
                location_id,
                handling_unit_id,
                qty_cases,
                source_code,
            ),
        )


class OperationsRepository:
    """Persist completed Phase 2 operational records and provide generation reads."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def opening_system_state(self, run_id: str) -> dict[tuple[str, str], int]:
        rows = self._connection.execute(
            """
            SELECT item_id, location_id, SUM(qty_cases) AS qty_cases
            FROM inventory_snapshot
            WHERE run_id = ? AND snapshot_type = 'OPENING_SYSTEM' AND location_id IS NOT NULL
            GROUP BY item_id, location_id
            ORDER BY item_id, location_id
            """,
            (run_id,),
        ).fetchall()
        return {
            (str(row["item_id"]), str(row["location_id"])): int(row["qty_cases"]) for row in rows
        }

    def trip_inputs(self, run_id: str) -> dict[str, list[sqlite3.Row]]:
        return {
            "shifts": self._connection.execute(
                "SELECT * FROM shift WHERE run_id = ? ORDER BY shift_id", (run_id,)
            ).fetchall(),
            "selectors": self._connection.execute(
                """
                SELECT * FROM operator
                WHERE run_id = ? AND role = 'SELECTOR'
                ORDER BY operator_id
                """,
                (run_id,),
            ).fetchall(),
            "zones": self._connection.execute(
                "SELECT * FROM zone WHERE run_id = ? ORDER BY zone_id", (run_id,)
            ).fetchall(),
            "replenishers": self._connection.execute(
                """
                SELECT * FROM operator
                WHERE run_id = ? AND role = 'REPLENISHMENT'
                ORDER BY operator_id
                """,
                (run_id,),
            ).fetchall(),
            "qa_operators": self._connection.execute(
                "SELECT * FROM operator WHERE run_id = ? AND role = 'QA' ORDER BY operator_id",
                (run_id,),
            ).fetchall(),
            "inventory_control": self._connection.execute(
                """
                SELECT * FROM operator
                WHERE run_id = ? AND role = 'INVENTORY_CONTROL'
                ORDER BY operator_id
                """,
                (run_id,),
            ).fetchall(),
            "slots": self._connection.execute(
                """
                SELECT
                    sa.item_id,
                    sa.pick_location_id,
                    sa.reorder_trigger_cases,
                    sa.target_cases,
                    sa.maximum_cases,
                    i.velocity_class,
                    i.fragility_score,
                    z.zone_id,
                    z.zone_code
                FROM slot_assignment AS sa
                JOIN item AS i ON i.run_id = sa.run_id AND i.item_id = sa.item_id
                JOIN location AS l
                    ON l.run_id = sa.run_id AND l.location_id = sa.pick_location_id
                JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
                WHERE sa.run_id = ? AND sa.effective_end_utc IS NULL
                ORDER BY i.velocity_class, sa.item_id
                """,
                (run_id,),
            ).fetchall(),
            "reserve_locations": self._connection.execute(
                """
                SELECT z.zone_code, l.location_id
                FROM location AS l
                JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
                WHERE l.run_id = ? AND l.location_type = 'RESERVE'
                ORDER BY z.zone_code, l.location_id
                """,
                (run_id,),
            ).fetchall(),
        }

    def insert_trip(self, record: TripRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO trip(
                run_id, trip_id, shift_id, selector_id, assigned_zone_id, start_utc, end_utc,
                continuation_flag, planned_pick_lines, planned_cases
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.trip_id,
                record.shift_id,
                record.selector_id,
                record.assigned_zone_id,
                record.start_utc,
                record.end_utc,
                record.continuation_flag,
                record.planned_pick_lines,
                record.planned_cases,
            ),
        )

    def insert_pick_event(self, record: PickEventRecord) -> None:
        self._insert_event_sequence(
            record.run_id,
            record.event_sequence,
            "PICK",
            "pick_event",
            record.pick_event_id,
            record.event_utc,
        )
        self._connection.execute(
            """
            INSERT INTO pick_event(
                run_id, pick_event_id, event_sequence, trip_id, selector_id, item_id,
                pick_location_id, event_utc, recorded_utc, requested_qty_cases,
                picked_qty_cases, short_qty_cases, short_reason_code,
                system_qty_before_cases, system_qty_after_cases, eligible_pick_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.pick_event_id,
                record.event_sequence,
                record.trip_id,
                record.selector_id,
                record.item_id,
                record.pick_location_id,
                record.event_utc,
                record.recorded_utc,
                record.requested_qty_cases,
                record.picked_qty_cases,
                record.short_qty_cases,
                record.short_reason_code,
                record.system_qty_before_cases,
                record.system_qty_after_cases,
                record.eligible_pick_flag,
            ),
        )

    def insert_replenishment_task(self, record: ReplenishmentTaskRecord) -> None:
        event_utc = record.confirmed_utc or record.created_utc
        self._insert_event_sequence(
            record.run_id,
            record.event_sequence,
            "REPLENISHMENT",
            "replenishment_task",
            record.replenishment_task_id,
            event_utc,
        )
        self._connection.execute(
            """
            INSERT INTO replenishment_task(
                run_id, replenishment_task_id, event_sequence, item_id, source_location_id,
                destination_location_id, operator_id, created_utc, started_utc, confirmed_utc,
                recorded_utc, requested_qty_cases, confirmed_qty_cases, status,
                delay_reason_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.replenishment_task_id,
                record.event_sequence,
                record.item_id,
                record.source_location_id,
                record.destination_location_id,
                record.operator_id,
                record.created_utc,
                record.started_utc,
                record.confirmed_utc,
                record.recorded_utc,
                record.requested_qty_cases,
                record.confirmed_qty_cases,
                record.status,
                record.delay_reason_code,
            ),
        )

    def insert_qa_event(self, record: QaEventRecord) -> None:
        self._insert_event_sequence(
            record.run_id,
            record.event_sequence,
            "QA",
            "qa_event",
            record.qa_event_id,
            record.occurred_utc,
        )
        self._connection.execute(
            """
            INSERT INTO qa_event(
                run_id, qa_event_id, event_sequence, item_id, location_id, handling_unit_id,
                operator_id, event_type, occurred_utc, recorded_utc, qty_affected_cases,
                reason_code, disposition_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.qa_event_id,
                record.event_sequence,
                record.item_id,
                record.location_id,
                record.handling_unit_id,
                record.operator_id,
                record.event_type,
                record.occurred_utc,
                record.recorded_utc,
                record.qty_affected_cases,
                record.reason_code,
                record.disposition_code,
            ),
        )

    def insert_inventory_adjustment(self, record: InventoryAdjustmentRecord) -> None:
        self._insert_event_sequence(
            record.run_id,
            record.event_sequence,
            "ADJUSTMENT",
            "inventory_adjustment",
            record.adjustment_id,
            record.effective_utc,
        )
        self._connection.execute(
            """
            INSERT INTO inventory_adjustment(
                run_id, adjustment_id, event_sequence, item_id, location_id, operator_id,
                effective_utc, recorded_utc, qty_delta_cases, reason_code, reference_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.adjustment_id,
                record.event_sequence,
                record.item_id,
                record.location_id,
                record.operator_id,
                record.effective_utc,
                record.recorded_utc,
                record.qty_delta_cases,
                record.reason_code,
                record.reference_code,
            ),
        )

    def insert_system_event(self, record: SystemEventRecord) -> None:
        self._insert_event_sequence(
            record.run_id,
            record.event_sequence,
            "SYSTEM_EVENT",
            "system_event",
            record.system_event_id,
            record.start_utc,
        )
        self._connection.execute(
            """
            INSERT INTO system_event(
                run_id, system_event_id, event_sequence, event_type, zone_id, location_id,
                equipment_area, start_utc, end_utc, severity_code, recorded_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.system_event_id,
                record.event_sequence,
                record.event_type,
                record.zone_id,
                record.location_id,
                record.equipment_area,
                record.start_utc,
                record.end_utc,
                record.severity_code,
                record.recorded_utc,
            ),
        )

    def insert_inventory_snapshot(self, record: InventorySnapshotRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO inventory_snapshot(
                run_id, snapshot_id, snapshot_utc, snapshot_type, item_id, location_id,
                handling_unit_id, qty_cases, source_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.snapshot_id,
                record.snapshot_utc,
                record.snapshot_type,
                record.item_id,
                record.location_id,
                record.handling_unit_id,
                record.qty_cases,
                record.source_code,
            ),
        )

    def _insert_event_sequence(
        self,
        run_id: str,
        event_sequence: int,
        event_type: str,
        source_table: str,
        source_id: str,
        event_utc: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO event_sequence_registry(
                run_id, event_sequence, event_type, source_table, source_id, event_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, event_sequence, event_type, source_table, source_id, event_utc),
        )


class Phase1DatasetRepository:
    """Read Phase 1 dataset state for validation and factual summaries."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def user_version(self) -> int:
        return int(self._connection.execute("PRAGMA user_version").fetchone()[0])

    def table_names(self) -> set[str]:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {str(row["name"]) for row in rows}

    def table_columns(self, table_name: str) -> set[str]:
        rows = self._connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def schema_versions(self) -> list[str]:
        if "schema_metadata" not in self.table_names():
            return []
        rows = self._connection.execute(
            "SELECT schema_version FROM schema_metadata ORDER BY schema_version"
        ).fetchall()
        return [str(row["schema_version"]) for row in rows]

    def run_metadata_rows(self) -> list[RunMetadata]:
        if "simulation_run" not in self.table_names():
            return []
        rows = self._connection.execute(
            """
            SELECT
                run_id,
                scenario_name,
                scenario_version,
                seed,
                schema_version,
                generator_version,
                config_hash,
                facility_timezone,
                simulation_start_utc,
                simulation_end_utc,
                generated_at_utc
            FROM simulation_run
            ORDER BY run_id
            """
        ).fetchall()
        return [
            RunMetadata(
                run_id=str(row["run_id"]),
                scenario_name=str(row["scenario_name"]),
                scenario_version=str(row["scenario_version"]),
                seed=int(row["seed"]),
                schema_version=str(row["schema_version"]),
                generator_version=str(row["generator_version"]),
                config_hash=str(row["config_hash"]),
                facility_timezone=str(row["facility_timezone"]),
                simulation_start_utc=str(row["simulation_start_utc"]),
                simulation_end_utc=str(row["simulation_end_utc"]),
                generated_at_utc=str(row["generated_at_utc"]),
            )
            for row in rows
        ]

    def first_run_id(self) -> str | None:
        rows = self.run_metadata_rows()
        return rows[0].run_id if len(rows) == 1 else None

    def table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        table_names = self.table_names()
        for table_name in self.supported_tables():
            if table_name in table_names:
                row = self._connection.execute(
                    f"SELECT COUNT(*) AS count FROM {table_name}"
                ).fetchone()
                counts[table_name] = int(row["count"])
        return counts

    def foreign_key_violations(self) -> list[dict[str, Any]]:
        rows = self._connection.execute("PRAGMA foreign_key_check").fetchall()
        return [dict(row) for row in rows]

    def null_violations(self) -> list[tuple[str, str, int]]:
        required_columns = {
            "simulation_run": (
                "run_id",
                "scenario_name",
                "scenario_version",
                "seed",
                "schema_version",
                "generator_version",
                "config_hash",
                "facility_timezone",
                "simulation_start_utc",
                "simulation_end_utc",
                "generated_at_utc",
            ),
            "facility": ("run_id", "facility_id", "facility_name", "timezone"),
            "zone": ("run_id", "zone_id", "facility_id", "zone_code", "active_flag"),
            "location": ("run_id", "location_id", "zone_id", "location_type", "active_flag"),
            "item": (
                "run_id",
                "item_id",
                "item_description",
                "category",
                "required_zone_code",
                "cases_per_pallet",
                "case_weight_lb",
                "case_cube_ft3",
                "fragility_score",
                "velocity_class",
                "expected_cases_per_day",
                "active_flag",
            ),
            "operator": ("run_id", "operator_id", "role", "shift_code", "active_flag"),
            "shift": ("run_id", "shift_id", "facility_id", "start_utc", "end_utc"),
            "slot_assignment": (
                "run_id",
                "assignment_id",
                "item_id",
                "pick_location_id",
                "effective_start_utc",
                "target_cases",
                "maximum_cases",
            ),
            "work_assignment": ("run_id", "work_assignment_id", "operator_id", "shift_id", "role"),
            "handling_unit": (
                "run_id",
                "handling_unit_id",
                "item_id",
                "initial_qty_cases",
                "status",
            ),
            "inventory_snapshot": (
                "run_id",
                "snapshot_id",
                "snapshot_utc",
                "snapshot_type",
                "item_id",
                "qty_cases",
                "source_code",
            ),
        }
        violations: list[tuple[str, str, int]] = []
        table_names = self.table_names()
        for table_name, column_names in required_columns.items():
            if table_name not in table_names:
                continue
            for column_name in column_names:
                row = self._connection.execute(
                    f"SELECT COUNT(*) AS count FROM {table_name} WHERE {column_name} IS NULL"
                ).fetchone()
                count = int(row["count"])
                if count:
                    violations.append((table_name, column_name, count))
        return violations

    def master_data_violations(self) -> list[tuple[str, int]]:
        checks = {
            "dataset must contain exactly one facility": """
                SELECT CASE WHEN COUNT(*) = 1 THEN 0 ELSE COUNT(*) END AS count FROM facility
            """,
            "every zone belongs to the run facility": """
                SELECT COUNT(*) AS count
                FROM zone AS z
                LEFT JOIN facility AS f ON f.run_id = z.run_id AND f.facility_id = z.facility_id
                WHERE f.facility_id IS NULL
            """,
            "locations must have positive case capacity when present": """
                SELECT COUNT(*) AS count
                FROM location
                WHERE capacity_cases IS NOT NULL AND capacity_cases <= 0
            """,
            "pick locations must be active and pickable": """
                SELECT COUNT(*) AS count
                FROM location
                WHERE location_type = 'PICK' AND (pickable_flag != 1 OR active_flag != 1)
            """,
            "non-pick locations cannot be pickable": """
                SELECT COUNT(*) AS count
                FROM location
                WHERE location_type != 'PICK' AND pickable_flag != 0
            """,
            "items must have matching zone codes": """
                SELECT COUNT(*) AS count
                FROM item AS i
                LEFT JOIN zone AS z ON z.run_id = i.run_id AND z.zone_code = i.required_zone_code
                WHERE z.zone_id IS NULL
            """,
            "each item must have one active slot assignment": """
                SELECT COUNT(*) AS count
                FROM item AS i
                WHERE (
                    SELECT COUNT(*)
                    FROM slot_assignment AS sa
                    WHERE sa.run_id = i.run_id
                        AND sa.item_id = i.item_id
                        AND sa.effective_end_utc IS NULL
                ) != 1
            """,
            "active pick slots cannot overlap": """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT run_id, pick_location_id
                    FROM slot_assignment
                    WHERE effective_end_utc IS NULL
                    GROUP BY run_id, pick_location_id
                    HAVING COUNT(*) > 1
                )
            """,
            "slot assignments must use pick locations in the item required zone": """
                SELECT COUNT(*) AS count
                FROM slot_assignment AS sa
                JOIN item AS i ON i.run_id = sa.run_id AND i.item_id = sa.item_id
                JOIN location AS l
                    ON l.run_id = sa.run_id AND l.location_id = sa.pick_location_id
                JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
                WHERE l.location_type != 'PICK'
                    OR l.pickable_flag != 1
                    OR i.required_zone_code != z.zone_code
            """,
            "slot quantity rules must be ordered and fit location capacity": """
                SELECT COUNT(*) AS count
                FROM slot_assignment AS sa
                JOIN location AS l
                    ON l.run_id = sa.run_id AND l.location_id = sa.pick_location_id
                WHERE sa.minimum_cases > sa.reorder_trigger_cases
                    OR sa.reorder_trigger_cases >= sa.target_cases
                    OR sa.target_cases > sa.maximum_cases
                    OR sa.maximum_cases > l.capacity_cases
            """,
            "work assignment roles must match operator roles": """
                SELECT COUNT(*) AS count
                FROM work_assignment AS wa
                JOIN operator AS o ON o.run_id = wa.run_id AND o.operator_id = wa.operator_id
                WHERE wa.role != o.role
            """,
            "shifts must stay within run boundaries and have ordered times": """
                SELECT COUNT(*) AS count
                FROM shift AS s
                JOIN simulation_run AS r ON r.run_id = s.run_id
                WHERE s.start_utc >= s.end_utc
                    OR s.start_utc < r.simulation_start_utc
                    OR s.end_utc > r.simulation_end_utc
            """,
        }
        violations: list[tuple[str, int]] = []
        for message, query in checks.items():
            row = self._connection.execute(query).fetchone()
            count = int(row["count"])
            if count:
                violations.append((message, count))
        return violations

    def opening_inventory_violations(self) -> list[tuple[str, int]]:
        checks = {
            "opening snapshots must use valid item/location zone relationships": """
                SELECT COUNT(*) AS count
                FROM inventory_snapshot AS s
                JOIN item AS i ON i.run_id = s.run_id AND i.item_id = s.item_id
                JOIN location AS l ON l.run_id = s.run_id AND l.location_id = s.location_id
                JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
                LEFT JOIN slot_assignment AS sa
                    ON sa.run_id = s.run_id
                    AND sa.item_id = s.item_id
                    AND sa.pick_location_id = s.location_id
                    AND sa.effective_end_utc IS NULL
                WHERE s.snapshot_type = 'OPENING_SYSTEM'
                    AND (
                        i.required_zone_code != z.zone_code
                        OR (l.location_type = 'PICK' AND sa.assignment_id IS NULL)
                        OR l.location_type NOT IN ('PICK', 'RESERVE')
                    )
            """,
            "opening snapshots must have locations and nonnegative quantities": """
                SELECT COUNT(*) AS count
                FROM inventory_snapshot
                WHERE snapshot_type = 'OPENING_SYSTEM'
                    AND (location_id IS NULL OR qty_cases < 0)
            """,
            "opening snapshots must occur at run start": """
                SELECT COUNT(*) AS count
                FROM inventory_snapshot AS s
                JOIN simulation_run AS r ON r.run_id = s.run_id
                WHERE s.snapshot_type = 'OPENING_SYSTEM'
                    AND s.snapshot_utc != r.simulation_start_utc
            """,
            "opening location totals must not exceed capacity": """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT s.run_id, s.location_id, SUM(s.qty_cases) AS qty, l.capacity_cases
                    FROM inventory_snapshot AS s
                    JOIN location AS l ON l.run_id = s.run_id AND l.location_id = s.location_id
                    WHERE s.snapshot_type = 'OPENING_SYSTEM'
                    GROUP BY s.run_id, s.location_id, l.capacity_cases
                    HAVING l.capacity_cases IS NOT NULL AND qty > l.capacity_cases
                )
            """,
            "handling units must reconcile to opening snapshots": """
                SELECT COUNT(*) AS count
                FROM handling_unit AS hu
                LEFT JOIN (
                    SELECT run_id, handling_unit_id, SUM(qty_cases) AS snapshot_qty
                    FROM inventory_snapshot
                    WHERE snapshot_type = 'OPENING_SYSTEM'
                    GROUP BY run_id, handling_unit_id
                ) AS s
                    ON s.run_id = hu.run_id AND s.handling_unit_id = hu.handling_unit_id
                WHERE COALESCE(s.snapshot_qty, 0) != hu.initial_qty_cases
            """,
            "opening snapshots must reference existing handling units": """
                SELECT COUNT(*) AS count
                FROM inventory_snapshot AS s
                LEFT JOIN handling_unit AS hu
                    ON hu.run_id = s.run_id AND hu.handling_unit_id = s.handling_unit_id
                WHERE s.snapshot_type = 'OPENING_SYSTEM'
                    AND (s.handling_unit_id IS NULL OR hu.handling_unit_id IS NULL)
            """,
            "handling units cannot span opening locations": """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT run_id, handling_unit_id
                    FROM inventory_snapshot
                    WHERE snapshot_type = 'OPENING_SYSTEM'
                    GROUP BY run_id, handling_unit_id
                    HAVING COUNT(DISTINCT location_id) > 1
                )
            """,
            "each item must have opening snapshot quantity": """
                SELECT COUNT(*) AS count
                FROM item AS i
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM inventory_snapshot AS s
                    WHERE s.run_id = i.run_id
                        AND s.item_id = i.item_id
                        AND s.snapshot_type = 'OPENING_SYSTEM'
                )
            """,
        }
        violations: list[tuple[str, int]] = []
        for message, query in checks.items():
            row = self._connection.execute(query).fetchone()
            count = int(row["count"])
            if count:
                violations.append((message, count))
        return violations

    def opening_totals_by_zone(self) -> list[tuple[str, int]]:
        rows = self._connection.execute(
            """
            SELECT z.zone_code, SUM(s.qty_cases) AS qty_cases
            FROM inventory_snapshot AS s
            JOIN location AS l ON l.run_id = s.run_id AND l.location_id = s.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE s.snapshot_type = 'OPENING_SYSTEM'
            GROUP BY z.zone_code
            ORDER BY z.zone_code
            """
        ).fetchall()
        return [(str(row["zone_code"]), int(row["qty_cases"])) for row in rows]

    def canonical_table_rows(self) -> dict[str, list[tuple[Any, ...]]]:
        rows_by_table: dict[str, list[tuple[Any, ...]]] = {}
        for table_name in self.supported_tables():
            if table_name not in self.table_names():
                continue
            column_names = [
                column
                for column in sorted(self.table_columns(table_name))
                if column not in _excluded_canonical_columns(table_name)
            ]
            selected = ", ".join(column_names)
            order_by = ", ".join(column_names)
            rows = self._connection.execute(
                f"SELECT {selected} FROM {table_name} ORDER BY {order_by}"
            ).fetchall()
            rows_by_table[table_name] = [
                tuple(row[column] for column in column_names) for row in rows
            ]
        return rows_by_table

    def supported_schema(self) -> bool:
        return self.user_version() == 1 and self.schema_versions() == [SCHEMA_VERSION]

    def supported_tables(self) -> tuple[str, ...]:
        if self.user_version() == 2:
            return PHASE2_TABLES
        return PHASE1_TABLES

    def phase2_schema_supported(self) -> bool:
        return self.user_version() == 2 and self.schema_versions() == [PHASE2_SCHEMA_VERSION]

    def phase2_transaction_violations(self) -> list[tuple[str, int]]:
        checks = {
            "transaction event sequences must be globally registered": """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT run_id, event_sequence FROM pick_event
                    UNION ALL
                    SELECT run_id, event_sequence FROM replenishment_task
                    UNION ALL
                    SELECT run_id, event_sequence FROM qa_event
                    UNION ALL
                    SELECT run_id, event_sequence FROM inventory_adjustment
                    UNION ALL
                    SELECT run_id, event_sequence FROM system_event
                ) AS e
                LEFT JOIN event_sequence_registry AS r
                    ON r.run_id = e.run_id AND r.event_sequence = e.event_sequence
                WHERE r.event_sequence IS NULL
            """,
            "event sequences must be contiguous within the run": """
                SELECT COUNT(*) AS count
                FROM event_sequence_registry AS r
                WHERE r.event_sequence < 1
                    OR r.event_sequence > (
                        SELECT COUNT(*) FROM event_sequence_registry AS c
                        WHERE c.run_id = r.run_id
                    )
            """,
            "event sequence must not move backward in event time": """
                SELECT COUNT(*) AS count
                FROM event_sequence_registry AS later
                JOIN event_sequence_registry AS earlier
                    ON earlier.run_id = later.run_id
                    AND earlier.event_sequence < later.event_sequence
                WHERE earlier.event_utc > later.event_utc
            """,
            "trip selectors must have SELECTOR role": """
                SELECT COUNT(*) AS count
                FROM trip AS t
                JOIN operator AS o ON o.run_id = t.run_id AND o.operator_id = t.selector_id
                WHERE o.role != 'SELECTOR'
            """,
            "pick selectors must match trip selectors": """
                SELECT COUNT(*) AS count
                FROM pick_event AS p
                JOIN trip AS t ON t.run_id = p.run_id AND t.trip_id = p.trip_id
                WHERE p.selector_id != t.selector_id
            """,
            "picks must occur inside parent trip": """
                SELECT COUNT(*) AS count
                FROM pick_event AS p
                JOIN trip AS t ON t.run_id = p.run_id AND t.trip_id = p.trip_id
                WHERE p.event_utc < t.start_utc OR p.event_utc > t.end_utc
            """,
            "pick locations must be active assignments for item": """
                SELECT COUNT(*) AS count
                FROM pick_event AS p
                LEFT JOIN slot_assignment AS sa
                    ON sa.run_id = p.run_id
                    AND sa.item_id = p.item_id
                    AND sa.pick_location_id = p.pick_location_id
                    AND sa.effective_end_utc IS NULL
                WHERE sa.assignment_id IS NULL
            """,
            "replenishment source and destination location types must be valid": """
                SELECT COUNT(*) AS count
                FROM replenishment_task AS rt
                JOIN location AS source
                    ON source.run_id = rt.run_id
                    AND source.location_id = rt.source_location_id
                JOIN location AS dest
                    ON dest.run_id = rt.run_id
                    AND dest.location_id = rt.destination_location_id
                WHERE source.location_type NOT IN ('RESERVE', 'STAGING')
                    OR dest.location_type != 'PICK'
            """,
            "operator roles must match transaction type": """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT p.run_id, p.selector_id AS operator_id, 'SELECTOR' AS expected_role
                    FROM pick_event AS p
                    UNION ALL
                    SELECT rt.run_id, rt.operator_id, 'REPLENISHMENT'
                    FROM replenishment_task AS rt
                    WHERE rt.operator_id IS NOT NULL
                    UNION ALL
                    SELECT q.run_id, q.operator_id, 'QA'
                    FROM qa_event AS q
                    WHERE q.operator_id IS NOT NULL
                ) AS expected
                JOIN operator AS o
                    ON o.run_id = expected.run_id AND o.operator_id = expected.operator_id
                WHERE o.role != expected.expected_role
            """,
            "adjustment operators must have allowed roles": """
                SELECT COUNT(*) AS count
                FROM inventory_adjustment AS ia
                JOIN operator AS o ON o.run_id = ia.run_id AND o.operator_id = ia.operator_id
                WHERE ia.operator_id IS NOT NULL
                    AND o.role NOT IN ('QA', 'INVENTORY_CONTROL', 'SYSTEM')
            """,
            "closing snapshots must reconcile to opening and signed system transactions": """
                WITH opening AS (
                    SELECT run_id, item_id, location_id, SUM(qty_cases) AS qty
                    FROM inventory_snapshot
                    WHERE snapshot_type = 'OPENING_SYSTEM'
                    GROUP BY run_id, item_id, location_id
                ),
                pick_delta AS (
                    SELECT run_id, item_id, pick_location_id AS location_id,
                        -SUM(picked_qty_cases) AS qty
                    FROM pick_event
                    GROUP BY run_id, item_id, pick_location_id
                ),
                replen_source AS (
                    SELECT run_id, item_id, source_location_id AS location_id,
                        -SUM(confirmed_qty_cases) AS qty
                    FROM replenishment_task
                    WHERE status = 'CONFIRMED'
                    GROUP BY run_id, item_id, source_location_id
                ),
                replen_dest AS (
                    SELECT run_id, item_id, destination_location_id AS location_id,
                        SUM(confirmed_qty_cases) AS qty
                    FROM replenishment_task
                    WHERE status = 'CONFIRMED'
                    GROUP BY run_id, item_id, destination_location_id
                ),
                adjustment_delta AS (
                    SELECT run_id, item_id, location_id, SUM(qty_delta_cases) AS qty
                    FROM inventory_adjustment
                    GROUP BY run_id, item_id, location_id
                ),
                expected AS (
                    SELECT run_id, item_id, location_id, SUM(qty) AS qty
                    FROM (
                        SELECT * FROM opening
                        UNION ALL SELECT * FROM pick_delta
                        UNION ALL SELECT * FROM replen_source
                        UNION ALL SELECT * FROM replen_dest
                        UNION ALL SELECT * FROM adjustment_delta
                    )
                    GROUP BY run_id, item_id, location_id
                ),
                closing AS (
                    SELECT run_id, item_id, location_id, SUM(qty_cases) AS qty
                    FROM inventory_snapshot
                    WHERE snapshot_type = 'CLOSING_SYSTEM'
                    GROUP BY run_id, item_id, location_id
                )
                SELECT COUNT(*) AS count
                FROM (
                    SELECT
                        COALESCE(e.run_id, c.run_id) AS run_id,
                        COALESCE(e.item_id, c.item_id) AS item_id,
                        COALESCE(e.location_id, c.location_id) AS location_id,
                        COALESCE(e.qty, 0) AS expected_qty,
                        COALESCE(c.qty, 0) AS closing_qty
                    FROM expected AS e
                    LEFT JOIN closing AS c
                        ON c.run_id = e.run_id
                        AND c.item_id = e.item_id
                        AND c.location_id = e.location_id
                    UNION
                    SELECT
                        COALESCE(e.run_id, c.run_id),
                        COALESCE(e.item_id, c.item_id),
                        COALESCE(e.location_id, c.location_id),
                        COALESCE(e.qty, 0),
                        COALESCE(c.qty, 0)
                    FROM closing AS c
                    LEFT JOIN expected AS e
                        ON c.run_id = e.run_id
                        AND c.item_id = e.item_id
                        AND c.location_id = e.location_id
                )
                WHERE expected_qty != closing_qty OR expected_qty < 0 OR closing_qty < 0
            """,
        }
        return self._violations_from_checks(checks)

    def phase2_count_warnings(self) -> list[tuple[str, int]]:
        checks = {
            f"{table_name} should contain records": f"""
                SELECT CASE WHEN COUNT(*) > 0 THEN 0 ELSE 1 END AS count
                FROM {table_name}
            """
            for table_name in PHASE2_ONLY_TABLES
            if table_name != "event_sequence_registry"
        }
        return self._violations_from_checks(checks)

    def closing_totals_by_zone(self) -> list[tuple[str, int]]:
        rows = self._connection.execute(
            """
            SELECT z.zone_code, SUM(s.qty_cases) AS qty_cases
            FROM inventory_snapshot AS s
            JOIN location AS l ON l.run_id = s.run_id AND l.location_id = s.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE s.snapshot_type = 'CLOSING_SYSTEM'
            GROUP BY z.zone_code
            ORDER BY z.zone_code
            """
        ).fetchall()
        return [(str(row["zone_code"]), int(row["qty_cases"])) for row in rows]

    def _violations_from_checks(self, checks: dict[str, str]) -> list[tuple[str, int]]:
        violations: list[tuple[str, int]] = []
        for message, query in checks.items():
            row = self._connection.execute(query).fetchone()
            count = int(row["count"])
            if count:
                violations.append((message, count))
        return violations


def _excluded_canonical_columns(table_name: str) -> set[str]:
    if table_name == "simulation_run":
        return {"generated_at_utc"}
    if table_name == "schema_metadata":
        return {"created_at_utc"}
    return set()
