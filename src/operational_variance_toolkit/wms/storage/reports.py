"""Read-only SQLite queries for registered schema-3 WMS reports."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from operational_variance_toolkit.errors import DataValidationError


class WmsReportRepository:
    """Execute factual report queries against ordinary WMS source tables."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def rows(
        self,
        report_code: str,
        parameters: Mapping[str, str],
        as_of_utc: str,
    ) -> tuple[tuple[object, ...], ...]:
        method = getattr(self, f"_{report_code.replace('-', '_')}")
        return tuple(tuple(row) for row in method(parameters, as_of_utc))

    def _query(self, sql: str, values: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        cursor = self._connection.cursor()
        cursor.row_factory = sqlite3.Row
        return cursor.execute(sql, values).fetchall()

    def _inventory_by_location(self, parameters, as_of_utc):
        del parameters, as_of_utc
        return self._query(
            """
            SELECT
                location_id, zone_code, location_type, aisle_code, bay_number,
                level_number, position_number, pallet_capacity, pickable_flag,
                active_flag, item_id, item_description, qty_on_hand_cases,
                code_date, cases_per_pallet, calculated_physical_maximum_cases,
                available_capacity_cases, occupancy_percentage, minimum_qty_cases,
                reorder_trigger_cases, target_qty_cases, maximum_qty_cases,
                last_transaction_id, last_updated_utc
            FROM wms_inventory_by_location
            ORDER BY zone_code, location_type, aisle_code, bay_number,
                level_number, position_number, location_id
            """
        )

    def _inventory_by_item(self, parameters, as_of_utc):
        del as_of_utc
        where, values = _filters(parameters, {"item": "item_id"})
        return self._query(
            f"""
            SELECT
                item_id, item_description, required_zone_code, velocity_class,
                total_on_hand_cases, pick_cases, reserve_cases,
                occupied_location_count, earliest_code_date, latest_update_utc,
                cases_per_pallet, pallet_equivalent_qty
            FROM wms_inventory_by_item
            {where}
            ORDER BY item_id
            """,
            values,
        )

    def _location_profile(self, parameters, as_of_utc):
        del as_of_utc
        where, values = _filters(parameters, {"location": "location_id"})
        return self._query(
            f"""
            SELECT
                location_id, zone_code, location_type, aisle_code, bay_number,
                level_number, position_number, pallet_capacity, pickable_flag,
                active_flag, current_item_id, current_qty_on_hand_cases, occupied_flag
            FROM wms_location_profile
            {where}
            ORDER BY zone_code, location_type, aisle_code, bay_number,
                level_number, position_number, location_id
            """,
            values,
        )

    def _empty_locations(self, parameters, as_of_utc):
        del parameters, as_of_utc
        return self._query(
            """
            SELECT
                location_id, zone_code, location_type, aisle_code, bay_number,
                level_number, position_number, pallet_capacity, assigned_item_id,
                CASE
                    WHEN location_type = 'RESERVE' AND assigned_item_id IS NULL
                        THEN 'Unassigned Empty Reserve'
                    WHEN location_type = 'PICK' AND assigned_item_id IS NOT NULL
                        THEN 'Assigned Zero-Quantity Pick Slot'
                    ELSE 'Other Zero-Quantity Location'
                END AS empty_location_classification,
                active_flag, pickable_flag, last_updated_utc
            FROM wms_empty_locations
            ORDER BY zone_code, location_type, aisle_code, bay_number,
                level_number, position_number, location_id
            """
        )

    def _code_date_inventory(self, parameters, as_of_utc):
        del as_of_utc
        filters = {"item": "inventory.item_id", "location": "inventory.location_id"}
        where, values = _filters(parameters, filters, prefix="AND")
        return self._query(
            f"""
            SELECT
                inventory.item_id, item.item_description, inventory.location_id,
                inventory.qty_on_hand_cases, inventory.code_date,
                CAST(julianday(inventory.code_date) - julianday(?) AS INTEGER)
                    AS days_to_code_date,
                zone.zone_code, item.velocity_class, item.category
            FROM inventory_master AS inventory
            JOIN item_master AS item USING(run_id, item_id)
            JOIN location_master AS location USING(run_id, location_id)
            JOIN zone USING(run_id, zone_id)
            WHERE inventory.qty_on_hand_cases > 0 AND inventory.code_date IS NOT NULL
            {where}
            ORDER BY inventory.code_date, inventory.item_id, inventory.location_id
            """,
            (parameters["as_of_date"], *values),
        )

    def _replenishment_needs(self, parameters, as_of_utc):
        effective_as_of = parameters.get("as_of_utc", as_of_utc)
        return self._query(
            """
            WITH reserve AS (
                SELECT inventory.run_id, inventory.item_id,
                    SUM(inventory.qty_on_hand_cases) AS reserve_qty
                FROM inventory_master AS inventory
                JOIN location_master AS location USING(run_id, location_id)
                WHERE location.location_type = 'RESERVE'
                GROUP BY inventory.run_id, inventory.item_id
            ),
            open_task AS (
                SELECT task.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY task.run_id, task.destination_location_id
                        ORDER BY task.created_utc, task.replenishment_task_id
                    ) AS task_rank
                FROM replenishment_task AS task
                WHERE task.status IN ('CREATED', 'STARTED')
            )
            SELECT
                inventory.item_id, inventory.location_id,
                inventory.qty_on_hand_cases, inventory.minimum_qty_cases,
                inventory.reorder_trigger_cases, inventory.target_qty_cases,
                inventory.maximum_qty_cases,
                MAX(MIN(inventory.target_qty_cases, inventory.maximum_qty_cases)
                    - inventory.qty_on_hand_cases, 0) AS recommended_qty_cases,
                COALESCE(reserve.reserve_qty, 0) AS compatible_reserve_qty_cases,
                item.velocity_class, open_task.replenishment_task_id AS open_task_id,
                open_task.status AS open_task_status,
                CASE WHEN open_task.created_utc IS NULL THEN NULL ELSE ROUND(
                    (julianday(?) - julianday(open_task.created_utc)) * 24.0, 2
                ) END AS oldest_open_task_age_hours
            FROM inventory_master AS inventory
            JOIN location_master AS location USING(run_id, location_id)
            JOIN item_master AS item USING(run_id, item_id)
            LEFT JOIN reserve USING(run_id, item_id)
            LEFT JOIN open_task
                ON open_task.run_id = inventory.run_id
                AND open_task.destination_location_id = inventory.location_id
                AND open_task.task_rank = 1
            WHERE location.location_type = 'PICK'
                AND inventory.qty_on_hand_cases <= inventory.reorder_trigger_cases
            ORDER BY item.velocity_class, inventory.item_id, inventory.location_id
            """,
            (effective_as_of,),
        )

    def _open_replenishment_tasks(self, parameters, as_of_utc):
        effective_as_of = parameters.get("as_of_utc", as_of_utc)
        filters = {"item": "task.item_id", "operator": "task.operator_id"}
        where, values = _filters(parameters, filters, prefix="AND")
        return self._query(
            f"""
            SELECT
                task.replenishment_task_id, task.item_id, task.source_location_id,
                task.destination_location_id, task.status, task.operator_id,
                task.requested_qty_cases, task.created_utc, task.started_utc,
                ROUND((julianday(?) - julianday(task.created_utc)) * 24.0, 2)
                    AS age_hours,
                source.qty_on_hand_cases AS source_qty_on_hand_cases,
                destination.qty_on_hand_cases AS destination_qty_on_hand_cases,
                task.delay_reason_code
            FROM replenishment_task AS task
            JOIN inventory_master AS source
                ON source.run_id = task.run_id
                AND source.location_id = task.source_location_id
            JOIN inventory_master AS destination
                ON destination.run_id = task.run_id
                AND destination.location_id = task.destination_location_id
            WHERE task.status IN ('CREATED', 'STARTED')
            {where}
            ORDER BY task.created_utc, task.replenishment_task_id
            """,
            (effective_as_of, *values),
        )

    def _inventory_transaction_inquiry(self, parameters, as_of_utc):
        del as_of_utc
        where, values = _filters(
            parameters,
            {
                "item": "item_id",
                "location": "location_id",
                "operator": "operator_id",
                "transaction_group": "transaction_group_id",
                "source_record": "source_record_id",
                "start_utc": "event_utc >=",
                "end_utc": "event_utc <=",
            },
        )
        return self._query(
            f"""
            SELECT
                transaction_id, transaction_group_id, command_id, event_sequence,
                line_number, transaction_type, item_id, location_id,
                related_location_id, qty_delta_cases, balance_before_cases,
                balance_after_cases, operator_id, event_utc, recorded_utc,
                reason_code, source_record_type, source_record_id
            FROM inventory_transaction
            {where}
            ORDER BY event_sequence, line_number, transaction_id
            """,
            values,
        )

    def _adjustment_history(self, parameters, as_of_utc):
        del as_of_utc
        where, values = _filters(
            parameters,
            {
                "item": "item_id",
                "location": "location_id",
                "operator": "operator_id",
                "start_utc": "effective_utc >=",
                "end_utc": "effective_utc <=",
            },
        )
        return self._query(
            f"""
            SELECT
                adjustment_id, item_id, location_id, qty_delta_cases, reason_code,
                operator_id, effective_utc, recorded_utc, balance_before_cases,
                balance_after_cases, reference_code, transaction_id, command_id
            FROM wms_adjustment_history
            {where}
            ORDER BY effective_utc, adjustment_id
            """,
            values,
        )

    def _qa_activity(self, parameters, as_of_utc):
        del as_of_utc
        where, values = _filters(
            parameters,
            {
                "item": "item_id",
                "location": "location_id",
                "operator": "operator_id",
                "start_utc": "occurred_utc >=",
                "end_utc": "occurred_utc <=",
            },
        )
        return self._query(
            f"""
            SELECT
                qa_event_id, item_id, location_id, event_type, qty_affected_cases,
                operator_id, occurred_utc, recorded_utc, reason_code,
                disposition_code, command_id, event_sequence
            FROM wms_qa_activity
            {where}
            ORDER BY occurred_utc, qa_event_id
            """,
            values,
        )

    def _inventory_snapshot(self, parameters, as_of_utc):
        del as_of_utc
        self._require_snapshot(parameters["snapshot_batch"])
        return self._query(
            """
            SELECT
                snapshot_batch_id, snapshot_type, snapshot_utc, location_id,
                item_id, qty_on_hand_cases, code_date, last_transaction_id
            FROM inventory_snapshot
            WHERE snapshot_batch_id = ?
            ORDER BY location_id
            """,
            (parameters["snapshot_batch"],),
        )

    def _inventory_reconciliation(self, parameters, as_of_utc):
        del as_of_utc
        snapshot_batch = parameters["snapshot_batch"]
        self._require_snapshot(snapshot_batch)
        return self._query(
            """
            SELECT
                live.location_id, COALESCE(live.item_id, snapshot.item_id) AS item_id,
                live.qty_on_hand_cases AS live_qty_on_hand_cases,
                snapshot.snapshot_batch_id, snapshot.snapshot_utc,
                snapshot.qty_on_hand_cases AS snapshot_qty_on_hand_cases,
                live.qty_on_hand_cases - snapshot.qty_on_hand_cases
                    AS live_snapshot_difference_cases,
                CASE
                    WHEN live.item_id IS NOT snapshot.item_id THEN 'ITEM_MISMATCH'
                    WHEN live.qty_on_hand_cases = snapshot.qty_on_hand_cases THEN 'MATCH'
                    ELSE 'QUANTITY_DIFFERENCE'
                END AS status
            FROM inventory_master AS live
            JOIN inventory_snapshot AS snapshot
                ON snapshot.run_id = live.run_id
                AND snapshot.location_id = live.location_id
            WHERE snapshot.snapshot_batch_id = ?
            ORDER BY live.location_id
            """,
            (snapshot_batch,),
        )

    def _require_snapshot(self, snapshot_batch: str) -> None:
        row = self._connection.execute(
            "SELECT 1 FROM inventory_snapshot WHERE snapshot_batch_id = ? LIMIT 1",
            (snapshot_batch,),
        ).fetchone()
        if row is None:
            raise DataValidationError(f"Unknown inventory snapshot batch: {snapshot_batch}")


def _filters(
    parameters: Mapping[str, str],
    fields: Mapping[str, str],
    *,
    prefix: str = "WHERE",
) -> tuple[str, tuple[object, ...]]:
    clauses: list[str] = []
    values: list[object] = []
    for parameter, field in fields.items():
        value = parameters.get(parameter)
        if value is None:
            continue
        if field.endswith((">=", "<=")):
            clauses.append(f"{field} ?")
        else:
            clauses.append(f"{field} = ?")
        values.append(value)
    if not clauses:
        return "", ()
    return f"{prefix} " + " AND ".join(clauses), tuple(values)
