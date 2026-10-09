"""Read-only schema-3 source access for WMS reconstruction."""

from __future__ import annotations

import sqlite3
from typing import Any


class WmsReconstructionSourceRepository:
    """Load deterministic, audit-first rows from a schema-3 WMS database."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def source_tables(self) -> dict[str, list[dict[str, Any]]]:
        """Return source rows required to reconstruct and contextualize WMS state."""

        queries = {
            "inventory_snapshot": """
                SELECT * FROM inventory_snapshot
                ORDER BY run_id, snapshot_utc, snapshot_batch_id, snapshot_line_id
            """,
            "inventory_transaction": """
                SELECT * FROM inventory_transaction
                ORDER BY run_id, event_sequence, line_number, transaction_id
            """,
            "inventory_master": """
                SELECT * FROM inventory_master
                ORDER BY run_id, location_id
            """,
            "trip": """
                SELECT
                    t.*, s.shift_code, s.start_utc AS shift_start_utc,
                    s.end_utc AS shift_end_utc, s.operating_date_local,
                    z.zone_code AS assigned_zone_code
                FROM trip AS t
                JOIN shift AS s ON s.run_id = t.run_id AND s.shift_id = t.shift_id
                JOIN zone AS z
                    ON z.run_id = t.run_id AND z.zone_id = t.assigned_zone_id
                ORDER BY t.run_id, t.start_utc, t.trip_id
            """,
            "pick_event": """
                SELECT * FROM pick_event
                ORDER BY run_id, event_sequence, pick_event_id
            """,
            "replenishment_task": """
                SELECT * FROM replenishment_task
                ORDER BY run_id, created_utc, replenishment_task_id
            """,
            "qa_event": """
                SELECT * FROM qa_event
                ORDER BY run_id, event_sequence, qa_event_id
            """,
            "inventory_adjustment": """
                SELECT * FROM inventory_adjustment
                ORDER BY run_id, event_sequence, adjustment_id
            """,
            "system_event": """
                SELECT * FROM system_event
                ORDER BY run_id, event_sequence, system_event_id
            """,
            "item_master": """
                SELECT * FROM item_master
                ORDER BY run_id, item_id
            """,
            "location_master": """
                SELECT l.*, z.zone_code
                FROM location_master AS l
                JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
                ORDER BY l.run_id, l.location_id
            """,
        }
        return {name: self._query(sql) for name, sql in queries.items()}

    def _query(self, sql: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self._connection.execute(sql).fetchall()]
