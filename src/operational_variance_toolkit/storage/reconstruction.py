"""Read-only source-table access for Phase 4 reconstruction."""

from __future__ import annotations

import sqlite3
from typing import Any

SOURCE_TABLE_NAMES: tuple[str, ...] = (
    "inventory_snapshot",
    "event_sequence_registry",
    "trip",
    "pick_event",
    "replenishment_task",
    "qa_event",
    "inventory_adjustment",
    "system_event",
    "item",
    "location",
    "zone",
    "operator",
)


class ReconstructionSourceRepository:
    """Load deterministic analyst-facing source rows for reconstruction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def source_tables(self) -> dict[str, list[dict[str, Any]]]:
        """Return stable source records needed by the analysis layer."""

        return {
            "inventory_snapshot": self._query(
                """
                SELECT
                    run_id,
                    snapshot_id,
                    snapshot_utc,
                    snapshot_type,
                    item_id,
                    location_id,
                    handling_unit_id,
                    qty_cases,
                    source_code
                FROM inventory_snapshot
                ORDER BY run_id, snapshot_type, item_id, location_id, snapshot_id
                """
            ),
            "event_sequence_registry": self._query(
                """
                SELECT
                    run_id,
                    event_sequence,
                    event_type,
                    source_table,
                    source_id,
                    event_utc
                FROM event_sequence_registry
                ORDER BY run_id, event_sequence
                """
            ),
            "trip": self._query(
                """
                SELECT
                    t.run_id,
                    t.trip_id,
                    t.shift_id,
                    t.selector_id,
                    t.assigned_zone_id,
                    z.zone_code AS assigned_zone_code,
                    t.start_utc,
                    t.end_utc,
                    t.continuation_flag,
                    t.planned_pick_lines,
                    t.planned_cases,
                    s.shift_code,
                    s.operating_date_local
                FROM trip AS t
                JOIN shift AS s ON s.run_id = t.run_id AND s.shift_id = t.shift_id
                JOIN zone AS z ON z.run_id = t.run_id AND z.zone_id = t.assigned_zone_id
                ORDER BY t.run_id, t.trip_id
                """
            ),
            "pick_event": self._query(
                """
                SELECT
                    run_id,
                    pick_event_id,
                    event_sequence,
                    trip_id,
                    selector_id,
                    item_id,
                    pick_location_id,
                    event_utc,
                    recorded_utc,
                    requested_qty_cases,
                    picked_qty_cases,
                    short_qty_cases,
                    short_reason_code,
                    system_qty_before_cases,
                    system_qty_after_cases,
                    eligible_pick_flag
                FROM pick_event
                ORDER BY run_id, event_sequence, pick_event_id
                """
            ),
            "replenishment_task": self._query(
                """
                SELECT
                    run_id,
                    replenishment_task_id,
                    event_sequence,
                    item_id,
                    source_location_id,
                    destination_location_id,
                    operator_id,
                    created_utc,
                    started_utc,
                    confirmed_utc,
                    recorded_utc,
                    requested_qty_cases,
                    confirmed_qty_cases,
                    status,
                    delay_reason_code
                FROM replenishment_task
                ORDER BY run_id, event_sequence, replenishment_task_id
                """
            ),
            "qa_event": self._query(
                """
                SELECT
                    run_id,
                    qa_event_id,
                    event_sequence,
                    item_id,
                    location_id,
                    handling_unit_id,
                    operator_id,
                    event_type,
                    occurred_utc,
                    recorded_utc,
                    qty_affected_cases,
                    reason_code,
                    disposition_code
                FROM qa_event
                ORDER BY run_id, event_sequence, qa_event_id
                """
            ),
            "inventory_adjustment": self._query(
                """
                SELECT
                    run_id,
                    adjustment_id,
                    event_sequence,
                    item_id,
                    location_id,
                    operator_id,
                    effective_utc,
                    recorded_utc,
                    qty_delta_cases,
                    reason_code,
                    reference_code
                FROM inventory_adjustment
                ORDER BY run_id, event_sequence, adjustment_id
                """
            ),
            "system_event": self._query(
                """
                SELECT
                    run_id,
                    system_event_id,
                    event_sequence,
                    event_type,
                    zone_id,
                    location_id,
                    equipment_area,
                    start_utc,
                    end_utc,
                    severity_code,
                    recorded_utc
                FROM system_event
                ORDER BY run_id, event_sequence, system_event_id
                """
            ),
            "item": self._query(
                """
                SELECT
                    run_id,
                    item_id,
                    category,
                    required_zone_code,
                    case_weight_lb,
                    case_cube_ft3,
                    fragility_score,
                    velocity_class,
                    expected_cases_per_day
                FROM item
                ORDER BY run_id, item_id
                """
            ),
            "location": self._query(
                """
                SELECT
                    l.run_id,
                    l.location_id,
                    l.zone_id,
                    z.zone_code,
                    l.location_type,
                    l.aisle_code,
                    l.equipment_area,
                    l.capacity_cases,
                    l.pickable_flag,
                    l.active_flag
                FROM location AS l
                JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
                ORDER BY l.run_id, l.location_id
                """
            ),
            "zone": self._query(
                """
                SELECT
                    run_id,
                    zone_id,
                    zone_code,
                    active_flag
                FROM zone
                ORDER BY run_id, zone_id
                """
            ),
            "operator": self._query(
                """
                SELECT
                    run_id,
                    operator_id,
                    role,
                    home_zone_id,
                    shift_code,
                    experience_months,
                    active_flag
                FROM operator
                ORDER BY run_id, operator_id
                """
            ),
        }

    def _query(self, sql: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(sql).fetchall()
        return [dict(row) for row in rows]
