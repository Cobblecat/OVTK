"""Fixed, parameterized schema-3 reads for console inquiry workflows."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence

ITEM_COLUMNS = (
    "run_id",
    "item_id",
    "item_description",
    "category",
    "required_zone_code",
    "case_length_in",
    "case_width_in",
    "case_height_in",
    "case_cube_ft3",
    "case_weight_lb",
    "cases_per_layer",
    "layers_per_pallet",
    "cases_per_pallet",
    "fragility_score",
    "shelf_life_days",
    "velocity_class",
    "expected_cases_per_day",
    "active_flag",
)

LOCATION_COLUMNS = (
    "run_id",
    "location_id",
    "zone_id",
    "location_type",
    "aisle_code",
    "bay_number",
    "level_number",
    "position_number",
    "pallet_capacity",
    "pickable_flag",
    "active_flag",
)

INVENTORY_COLUMNS = (
    "run_id",
    "location_id",
    "item_id",
    "qty_on_hand_cases",
    "code_date",
    "reorder_trigger_cases",
    "minimum_qty_cases",
    "target_qty_cases",
    "maximum_qty_cases",
    "last_transaction_id",
    "last_updated_utc",
)

TRANSACTION_COLUMNS = (
    "run_id",
    "transaction_id",
    "transaction_group_id",
    "command_id",
    "event_sequence",
    "line_number",
    "transaction_type",
    "location_id",
    "related_location_id",
    "item_id",
    "qty_delta_cases",
    "balance_before_cases",
    "balance_after_cases",
    "operator_id",
    "event_utc",
    "recorded_utc",
    "reason_code",
    "source_record_type",
    "source_record_id",
)

_TRANSACTION_FILTERS = {
    "item": "item_id",
    "location": "location_id",
    "operator": "operator_id",
    "transaction_group": "transaction_group_id",
    "command": "command_id",
    "source_record": "source_record_id",
}


class WmsInquiryRepository:
    """Read factual WMS records without accepting SQL structure from callers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def query_only_enabled(self) -> bool:
        return int(self._connection.execute("PRAGMA query_only").fetchone()[0]) == 1

    def item(self, item_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            f"SELECT {', '.join(ITEM_COLUMNS)} FROM item_master WHERE item_id = ?",
            (item_id,),
        )

    def location(self, location_id: str) -> tuple[tuple[object, ...], ...]:
        columns = ", ".join(f"l.{name}" for name in LOCATION_COLUMNS)
        return self._rows(
            f"""
            SELECT {columns}, z.zone_code
            FROM location_master AS l
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE l.location_id = ?
            """,
            (location_id,),
        )

    def inventory_by_location(self, location_id: str) -> tuple[tuple[object, ...], ...]:
        columns = ", ".join(f"i.{name}" for name in INVENTORY_COLUMNS)
        return self._rows(
            f"""
            SELECT {columns}, l.location_type, z.zone_code, m.item_description
            FROM inventory_master AS i
            JOIN location_master AS l
              ON l.run_id = i.run_id AND l.location_id = i.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            LEFT JOIN item_master AS m
              ON m.run_id = i.run_id AND m.item_id = i.item_id
            WHERE i.location_id = ?
            """,
            (location_id,),
        )

    def inventory_by_item(self, item_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            """
            SELECT i.location_id, l.location_type, z.zone_code,
                   i.item_id, i.qty_on_hand_cases, i.code_date,
                   i.reorder_trigger_cases, i.minimum_qty_cases,
                   i.target_qty_cases, i.maximum_qty_cases,
                   i.last_transaction_id, i.last_updated_utc
            FROM inventory_master AS i
            JOIN location_master AS l
              ON l.run_id = i.run_id AND l.location_id = i.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE i.item_id = ?
            ORDER BY z.zone_code, l.location_type, i.location_id
            """,
            (item_id,),
        )

    def trip(self, trip_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            """
            SELECT t.run_id, t.trip_id, t.shift_id, t.selector_id,
                   t.assigned_zone_id, z.zone_code, t.start_utc, t.end_utc,
                   t.continuation_flag, t.planned_pick_lines, t.planned_cases,
                   COUNT(p.pick_event_id) AS recorded_pick_lines,
                   COALESCE(SUM(p.requested_qty_cases), 0) AS requested_cases,
                   COALESCE(SUM(p.picked_qty_cases), 0) AS picked_cases,
                   COALESCE(SUM(p.short_qty_cases), 0) AS short_cases
            FROM trip AS t
            JOIN zone AS z ON z.run_id = t.run_id AND z.zone_id = t.assigned_zone_id
            LEFT JOIN pick_event AS p ON p.run_id = t.run_id AND p.trip_id = t.trip_id
            WHERE t.trip_id = ?
            GROUP BY t.run_id, t.trip_id
            """,
            (trip_id,),
        )

    def pick(self, pick_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            """
            SELECT p.*, t.transaction_id, t.transaction_group_id
            FROM pick_event AS p
            LEFT JOIN inventory_transaction AS t
              ON t.run_id = p.run_id AND t.command_id = p.command_id
            WHERE p.pick_event_id = ?
            ORDER BY t.line_number
            """,
            (pick_id,),
        )

    def replenishment(self, task_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            """
            SELECT r.*,
                   (SELECT c.command_id FROM wms_command AS c
                    WHERE c.run_id = r.run_id
                      AND c.result_record_id = r.replenishment_task_id
                      AND c.command_type = 'StartReplenishmentTask'
                    ORDER BY c.event_sequence LIMIT 1) AS start_command_id,
                   (SELECT t.transaction_group_id FROM inventory_transaction AS t
                    WHERE t.run_id = r.run_id
                      AND t.source_record_id = r.replenishment_task_id
                    ORDER BY t.line_number LIMIT 1) AS transaction_group_id
            FROM replenishment_task AS r
            WHERE r.replenishment_task_id = ?
            """,
            (task_id,),
        )

    def qa(self, qa_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows("SELECT * FROM qa_event WHERE qa_event_id = ?", (qa_id,))

    def adjustment(self, adjustment_id: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            """
            SELECT a.*, t.transaction_id, t.transaction_group_id,
                   t.balance_before_cases, t.balance_after_cases
            FROM inventory_adjustment AS a
            JOIN inventory_transaction AS t
              ON t.run_id = a.run_id AND t.command_id = a.command_id
            WHERE a.adjustment_id = ?
            ORDER BY t.line_number
            """,
            (adjustment_id,),
        )

    def transactions(self, filters: Mapping[str, str]) -> tuple[tuple[object, ...], ...]:
        clauses: list[str] = []
        values: list[str] = []
        for name, column in _TRANSACTION_FILTERS.items():
            value = filters.get(name)
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        if value := filters.get("start_utc"):
            clauses.append("event_utc >= ?")
            values.append(value)
        if value := filters.get("end_utc"):
            clauses.append("event_utc <= ?")
            values.append(value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._rows(
            f"""
            SELECT {", ".join(TRANSACTION_COLUMNS)}
            FROM inventory_transaction
            {where}
            ORDER BY event_sequence, line_number, transaction_id
            """,
            values,
        )

    def export_rows(self, dataset: str) -> tuple[tuple[object, ...], ...]:
        if dataset == "item-master":
            return self._rows(f"SELECT {', '.join(ITEM_COLUMNS)} FROM item_master ORDER BY item_id")
        if dataset == "location-master":
            return self._rows(
                f"SELECT {', '.join(LOCATION_COLUMNS)} FROM location_master "
                "ORDER BY zone_id, aisle_code, bay_number, level_number, "
                "position_number, location_id"
            )
        if dataset == "inventory-master":
            return self._rows(
                f"SELECT {', '.join(INVENTORY_COLUMNS)} FROM inventory_master ORDER BY location_id"
            )
        raise ValueError(f"Unsupported export dataset: {dataset}")

    def trace_commands(self, identifier: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            """
            SELECT DISTINCT c.run_id, c.command_id, c.command_type, c.payload_hash,
                   c.accepted_utc, c.result_record_type, c.result_record_id,
                   c.event_sequence, e.event_type, e.event_utc, e.recorded_utc
            FROM wms_command AS c
            JOIN event_sequence_registry AS e
              ON e.run_id = c.run_id AND e.event_sequence = c.event_sequence
            LEFT JOIN inventory_transaction AS t
              ON t.run_id = c.run_id AND t.command_id = c.command_id
            WHERE c.command_id = ?
               OR t.transaction_group_id = ?
               OR c.result_record_id = ?
               OR t.source_record_id = ?
            ORDER BY c.event_sequence, c.command_id
            """,
            (identifier, identifier, identifier, identifier),
        )

    def trace_transactions(self, identifier: str) -> tuple[tuple[object, ...], ...]:
        return self._rows(
            f"""
            SELECT {", ".join("t." + name for name in TRANSACTION_COLUMNS)}
            FROM inventory_transaction AS t
            WHERE t.transaction_group_id = ?
               OR t.source_record_id = ?
               OR t.command_id IN (
                   SELECT DISTINCT c.command_id
                   FROM wms_command AS c
                   LEFT JOIN inventory_transaction AS linked
                     ON linked.run_id = c.run_id AND linked.command_id = c.command_id
                   WHERE c.command_id = ?
                      OR linked.transaction_group_id = ?
                      OR c.result_record_id = ?
                      OR linked.source_record_id = ?
               )
            ORDER BY t.event_sequence, t.line_number, t.transaction_id
            """,
            (identifier, identifier, identifier, identifier, identifier, identifier),
        )

    def trace_workflow(
        self, record_type: str, record_id: str
    ) -> tuple[str, tuple[str, ...], tuple[tuple[object, ...], ...]]:
        queries = {
            "PICK": ("pick_event", "pick_event_id"),
            "REPLENISHMENT_TASK": ("replenishment_task", "replenishment_task_id"),
            "ADJUSTMENT": ("inventory_adjustment", "adjustment_id"),
            "QA_EVENT": ("qa_event", "qa_event_id"),
            "SYSTEM_EVENT": ("system_event", "system_event_id"),
            "TRIP": ("trip", "trip_id"),
        }
        target = queries.get(record_type)
        if target is None:
            if record_type == "INVENTORY_SNAPSHOT":
                rows = self._rows(
                    """
                    SELECT snapshot_batch_id, snapshot_type, snapshot_utc,
                           source_code, COUNT(*) AS line_count,
                           SUM(qty_on_hand_cases) AS recorded_cases
                    FROM inventory_snapshot
                    WHERE snapshot_batch_id = ?
                    GROUP BY snapshot_batch_id, snapshot_type, snapshot_utc, source_code
                    """,
                    (record_id,),
                )
                return (
                    "Recorded Inventory Snapshot",
                    (
                        "snapshot_batch_id",
                        "snapshot_type",
                        "snapshot_utc",
                        "source_code",
                        "line_count",
                        "recorded_cases",
                    ),
                    rows,
                )
            return record_type.replace("_", " ").title(), (), ()
        table, id_column = target
        cursor = self._connection.execute(
            f"SELECT * FROM {table} WHERE {id_column} = ?", (record_id,)
        )
        columns = tuple(description[0] for description in cursor.description)
        return record_type.replace("_", " ").title(), columns, tuple(cursor.fetchall())

    def live_inventory_for_transactions(
        self, transactions: Sequence[tuple[object, ...]]
    ) -> tuple[tuple[object, ...], ...]:
        location_index = TRANSACTION_COLUMNS.index("location_id")
        locations = tuple(dict.fromkeys(str(row[location_index]) for row in transactions))
        if not locations:
            return ()
        placeholders = ", ".join("?" for _ in locations)
        return self._rows(
            f"""
            SELECT location_id, item_id, qty_on_hand_cases, code_date,
                   last_transaction_id, last_updated_utc
            FROM inventory_master
            WHERE location_id IN ({placeholders})
            ORDER BY location_id
            """,
            locations,
        )

    def _rows(self, sql: str, parameters: Sequence[object] = ()) -> tuple[tuple[object, ...], ...]:
        return tuple(tuple(row) for row in self._connection.execute(sql, parameters).fetchall())
