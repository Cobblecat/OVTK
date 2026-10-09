"""SQLite repository and unit of work for schema-3 WMS commands."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import astuple
from datetime import UTC, date, datetime

from operational_variance_toolkit.wms.domain.inventory import InventoryMasterRecord
from operational_variance_toolkit.wms.domain.records import (
    EventSequenceRecord,
    InventoryAdjustmentRecord,
    InventoryPosition,
    InventoryTransactionRecord,
    PickEventRecord,
    QaEventRecord,
    ReplenishmentTaskRecord,
    ReplenishmentTaskState,
    ShiftState,
    SnapshotLineRecord,
    SystemEventRecord,
    TripRecord,
    TripState,
)


class WmsCommandRepository:
    """Translate typed WMS records to atomic SQLite operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @contextmanager
    def unit_of_work(self) -> Iterator[None]:
        row_factory = self._connection.row_factory
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
        finally:
            self._connection.row_factory = row_factory

    def run_id(self) -> str:
        rows = self._connection.execute("SELECT run_id FROM simulation_run").fetchall()
        if len(rows) != 1:
            raise sqlite3.DatabaseError(f"Expected one simulation_run row, found {len(rows)}")
        return str(rows[0]["run_id"])

    def command_exists(self, run_id: str, command_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM wms_command WHERE run_id = ? AND command_id = ?",
            (run_id, command_id),
        ).fetchone()
        return row is not None

    def record_command(
        self,
        *,
        run_id: str,
        command_id: str,
        command_type: str,
        payload_hash: str,
        accepted_utc: datetime,
        result_record_type: str,
        result_record_id: str,
        event_sequence: int | None,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO wms_command(
                run_id, command_id, command_type, payload_hash, accepted_utc,
                result_record_type, result_record_id, event_sequence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                command_id,
                command_type,
                payload_hash,
                _iso(accepted_utc),
                result_record_type,
                result_record_id,
                event_sequence,
            ),
        )

    def next_event_sequence(self, run_id: str) -> int:
        row = self._connection.execute(
            """
            SELECT COALESCE(MAX(event_sequence), 0) + 1 AS next_sequence
            FROM event_sequence_registry
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return int(row["next_sequence"])

    def insert_event_sequence(self, record: EventSequenceRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO event_sequence_registry(
                run_id, event_sequence, event_type, source_record_id,
                event_utc, recorded_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def inventory_position(self, run_id: str, location_id: str) -> InventoryPosition | None:
        row = self._connection.execute(
            """
            SELECT
                i.run_id,
                i.location_id,
                i.item_id,
                i.qty_on_hand_cases,
                i.code_date,
                i.minimum_qty_cases,
                i.reorder_trigger_cases,
                i.target_qty_cases,
                i.maximum_qty_cases,
                i.last_transaction_id,
                i.last_updated_utc,
                l.location_type,
                z.zone_code,
                l.pallet_capacity,
                l.pickable_flag,
                l.active_flag,
                item.required_zone_code AS item_required_zone_code,
                item.cases_per_pallet
            FROM inventory_master AS i
            JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            LEFT JOIN item_master AS item
                ON item.run_id = i.run_id AND item.item_id = i.item_id
            WHERE i.run_id = ? AND i.location_id = ?
            """,
            (run_id, location_id),
        ).fetchone()
        return InventoryPosition(**dict(row)) if row is not None else None

    def item_profile(self, run_id: str, item_id: str) -> tuple[str, int] | None:
        row = self._connection.execute(
            """
            SELECT required_zone_code, cases_per_pallet
            FROM item_master
            WHERE run_id = ? AND item_id = ? AND active_flag = 1
            """,
            (run_id, item_id),
        ).fetchone()
        if row is None:
            return None
        return str(row["required_zone_code"]), int(row["cases_per_pallet"])

    def update_inventory(self, record: InventoryMasterRecord) -> None:
        self._connection.execute(
            """
            UPDATE inventory_master
            SET item_id = ?,
                qty_on_hand_cases = ?,
                code_date = ?,
                reorder_trigger_cases = ?,
                minimum_qty_cases = ?,
                target_qty_cases = ?,
                maximum_qty_cases = ?,
                last_transaction_id = ?,
                last_updated_utc = ?
            WHERE run_id = ? AND location_id = ?
            """,
            (
                record.item_id,
                record.qty_on_hand_cases,
                record.code_date,
                record.reorder_trigger_cases,
                record.minimum_qty_cases,
                record.target_qty_cases,
                record.maximum_qty_cases,
                record.last_transaction_id,
                record.last_updated_utc,
                record.run_id,
                record.location_id,
            ),
        )

    def insert_inventory_transaction(self, record: InventoryTransactionRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO inventory_transaction(
                run_id, transaction_id, transaction_group_id, command_id,
                event_sequence, line_number, transaction_type, location_id,
                related_location_id, item_id, qty_delta_cases, balance_before_cases,
                balance_after_cases, operator_id, event_utc, recorded_utc,
                reason_code, source_record_type, source_record_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def operator_role(self, run_id: str, operator_id: str) -> str | None:
        row = self._connection.execute(
            """
            SELECT role FROM operator
            WHERE run_id = ? AND operator_id = ? AND active_flag = 1
            """,
            (run_id, operator_id),
        ).fetchone()
        return str(row["role"]) if row is not None else None

    def shift_state(self, run_id: str, shift_id: str) -> ShiftState | None:
        row = self._connection.execute(
            """
            SELECT run_id, shift_id, start_utc, end_utc
            FROM shift WHERE run_id = ? AND shift_id = ?
            """,
            (run_id, shift_id),
        ).fetchone()
        return ShiftState(**dict(row)) if row is not None else None

    def zone_exists(self, run_id: str, zone_id: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM zone WHERE run_id = ? AND zone_id = ? AND active_flag = 1",
                (run_id, zone_id),
            ).fetchone()
            is not None
        )

    def insert_trip(self, record: TripRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO trip(
                run_id, trip_id, shift_id, selector_id, assigned_zone_id,
                start_utc, end_utc, continuation_flag, planned_pick_lines, planned_cases
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def trip_state(self, run_id: str, trip_id: str) -> TripState | None:
        row = self._connection.execute(
            """
            SELECT run_id, trip_id, shift_id, selector_id, assigned_zone_id, start_utc, end_utc
            FROM trip WHERE run_id = ? AND trip_id = ?
            """,
            (run_id, trip_id),
        ).fetchone()
        return TripState(**dict(row)) if row is not None else None

    def insert_pick_event(self, record: PickEventRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO pick_event(
                run_id, pick_event_id, command_id, event_sequence, trip_id,
                selector_id, item_id, pick_location_id, event_utc, recorded_utc,
                requested_qty_cases, picked_qty_cases, short_qty_cases,
                short_reason_code, system_qty_before_cases, system_qty_after_cases,
                eligible_pick_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def insert_replenishment_task(self, record: ReplenishmentTaskRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO replenishment_task(
                run_id, replenishment_task_id, create_command_id, confirm_command_id,
                event_sequence, item_id, source_location_id, destination_location_id,
                operator_id, created_utc, started_utc, confirmed_utc, recorded_utc,
                requested_qty_cases, confirmed_qty_cases, status, delay_reason_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def replenishment_task(
        self, run_id: str, replenishment_task_id: str
    ) -> ReplenishmentTaskState | None:
        row = self._connection.execute(
            """
            SELECT
                run_id, replenishment_task_id, item_id, source_location_id,
                destination_location_id, operator_id, created_utc, started_utc,
                confirmed_utc, recorded_utc, requested_qty_cases,
                confirmed_qty_cases, status
            FROM replenishment_task
            WHERE run_id = ? AND replenishment_task_id = ?
            """,
            (run_id, replenishment_task_id),
        ).fetchone()
        return ReplenishmentTaskState(**dict(row)) if row is not None else None

    def start_replenishment_task(
        self,
        *,
        run_id: str,
        replenishment_task_id: str,
        operator_id: str,
        started_utc: datetime,
        recorded_utc: datetime,
    ) -> None:
        self._connection.execute(
            """
            UPDATE replenishment_task
            SET operator_id = ?, started_utc = ?, recorded_utc = ?, status = 'STARTED'
            WHERE run_id = ? AND replenishment_task_id = ?
            """,
            (
                operator_id,
                _iso(started_utc),
                _iso(recorded_utc),
                run_id,
                replenishment_task_id,
            ),
        )

    def confirm_replenishment_task(
        self,
        *,
        run_id: str,
        replenishment_task_id: str,
        command_id: str,
        event_sequence: int,
        operator_id: str,
        confirmed_utc: datetime,
        recorded_utc: datetime,
        confirmed_qty_cases: int,
    ) -> None:
        self._connection.execute(
            """
            UPDATE replenishment_task
            SET confirm_command_id = ?, event_sequence = ?, operator_id = ?,
                confirmed_utc = ?, recorded_utc = ?, confirmed_qty_cases = ?,
                status = 'CONFIRMED'
            WHERE run_id = ? AND replenishment_task_id = ?
            """,
            (
                command_id,
                event_sequence,
                operator_id,
                _iso(confirmed_utc),
                _iso(recorded_utc),
                confirmed_qty_cases,
                run_id,
                replenishment_task_id,
            ),
        )

    def insert_adjustment(self, record: InventoryAdjustmentRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO inventory_adjustment(
                run_id, adjustment_id, command_id, event_sequence, item_id,
                location_id, operator_id, effective_utc, recorded_utc,
                qty_delta_cases, reason_code, reference_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def insert_qa_event(self, record: QaEventRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO qa_event(
                run_id, qa_event_id, command_id, event_sequence, item_id, location_id,
                operator_id, event_type, occurred_utc, recorded_utc,
                qty_affected_cases, reason_code, disposition_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def insert_system_event(self, record: SystemEventRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO system_event(
                run_id, system_event_id, command_id, event_sequence, event_type,
                zone_id, location_id, aisle_code, start_utc, end_utc,
                severity_code, recorded_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _db_values(record),
        )

    def all_inventory_positions(self, run_id: str) -> list[InventoryPosition]:
        location_ids = [
            str(row["location_id"])
            for row in self._connection.execute(
                """
                SELECT location_id FROM inventory_master
                WHERE run_id = ? ORDER BY location_id
                """,
                (run_id,),
            ).fetchall()
        ]
        return [
            position
            for location_id in location_ids
            if (position := self.inventory_position(run_id, location_id)) is not None
        ]

    def insert_snapshot_lines(self, records: list[SnapshotLineRecord]) -> None:
        self._connection.executemany(
            """
            INSERT INTO inventory_snapshot(
                run_id, snapshot_batch_id, snapshot_line_id, snapshot_utc,
                snapshot_type, location_id, item_id, qty_on_hand_cases, code_date,
                last_transaction_id, source_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_db_values(record) for record in records),
        )


def _db_values(record: object) -> tuple[object, ...]:
    return tuple(_db_value(value) for value in astuple(record))


def _db_value(value: object) -> object:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
