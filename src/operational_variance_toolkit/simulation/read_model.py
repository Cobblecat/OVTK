"""Read-only SQLite input adapter for external simulation drivers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from operational_variance_toolkit.simulation.physical import PhysicalPosition


@dataclass(frozen=True, slots=True)
class SlotPlan:
    item_id: str
    pick_location_id: str
    reserve_location_id: str
    zone_id: str
    zone_code: str
    minimum_qty_cases: int
    reorder_trigger_cases: int
    target_qty_cases: int
    maximum_qty_cases: int
    fragility_score: float
    velocity_class: str


@dataclass(frozen=True, slots=True)
class ShiftPlan:
    shift_id: str
    start_utc: str
    end_utc: str


@dataclass(frozen=True, slots=True)
class BaselineInputs:
    positions: tuple[PhysicalPosition, ...]
    slots: tuple[SlotPlan, ...]
    shifts: tuple[ShiftPlan, ...]
    selectors: tuple[str, ...]
    replenishers: tuple[str, ...]
    qa_operators: tuple[str, ...]
    inventory_control_operator: str
    zone_ids: tuple[str, ...]


class SimulationReadModel:
    """Load WMS facts needed to seed and plan an external simulation."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def baseline_inputs(self, run_id: str) -> BaselineInputs:
        return BaselineInputs(
            positions=self._positions(run_id),
            slots=self._slots(run_id),
            shifts=self._shifts(run_id),
            selectors=self._operators(run_id, "SELECTOR"),
            replenishers=self._operators(run_id, "REPLENISHMENT"),
            qa_operators=self._operators(run_id, "QA"),
            inventory_control_operator=self._operators(run_id, "INVENTORY_CONTROL")[0],
            zone_ids=tuple(
                str(row[0])
                for row in self._connection.execute(
                    "SELECT zone_id FROM zone WHERE run_id = ? ORDER BY zone_id",
                    (run_id,),
                )
            ),
        )

    def recorded_quantities(self, run_id: str) -> dict[str, int]:
        return {
            str(row[0]): int(row[1])
            for row in self._connection.execute(
                """
                SELECT location_id, qty_on_hand_cases
                FROM inventory_master WHERE run_id = ? ORDER BY location_id
                """,
                (run_id,),
            )
        }

    def _positions(self, run_id: str) -> tuple[PhysicalPosition, ...]:
        return tuple(
            PhysicalPosition(str(row[0]), row[1], int(row[2]), row[3])
            for row in self._connection.execute(
                """
                SELECT location_id, item_id, qty_on_hand_cases, code_date
                FROM inventory_master WHERE run_id = ? ORDER BY location_id
                """,
                (run_id,),
            )
        )

    def _slots(self, run_id: str) -> tuple[SlotPlan, ...]:
        return tuple(
            SlotPlan(*row)
            for row in self._connection.execute(
                """
                SELECT
                    pick.item_id, pick.location_id, reserve.location_id,
                    pick_location.zone_id, zone.zone_code, pick.minimum_qty_cases,
                    pick.reorder_trigger_cases, pick.target_qty_cases,
                    pick.maximum_qty_cases, item.fragility_score, item.velocity_class
                FROM inventory_master AS pick
                JOIN location_master AS pick_location USING(run_id, location_id)
                JOIN item_master AS item USING(run_id, item_id)
                JOIN zone ON zone.run_id = pick_location.run_id
                    AND zone.zone_id = pick_location.zone_id
                JOIN inventory_master AS reserve
                    ON reserve.run_id = pick.run_id AND reserve.item_id = pick.item_id
                JOIN location_master AS reserve_location
                    ON reserve_location.run_id = reserve.run_id
                    AND reserve_location.location_id = reserve.location_id
                WHERE pick.run_id = ? AND pick_location.location_type = 'PICK'
                    AND reserve_location.location_type = 'RESERVE'
                ORDER BY pick.item_id
                """,
                (run_id,),
            )
        )

    def _shifts(self, run_id: str) -> tuple[ShiftPlan, ...]:
        return tuple(
            ShiftPlan(str(row[0]), str(row[1]), str(row[2]))
            for row in self._connection.execute(
                """
                SELECT shift_id, start_utc, end_utc
                FROM shift WHERE run_id = ? ORDER BY start_utc, shift_id
                """,
                (run_id,),
            )
        )

    def _operators(self, run_id: str, role: str) -> tuple[str, ...]:
        return tuple(
            str(row[0])
            for row in self._connection.execute(
                """
                SELECT operator_id FROM operator
                WHERE run_id = ? AND role = ? AND active_flag = 1
                ORDER BY operator_id
                """,
                (run_id, role),
            )
        )
