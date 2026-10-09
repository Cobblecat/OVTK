"""Scenario-neutral work and timing policy hooks for external drivers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from operational_variance_toolkit.simulation.physical import PhysicalPickResult
from operational_variance_toolkit.simulation.read_model import BaselineInputs, SlotPlan


@dataclass(frozen=True, slots=True)
class PolicyAdjustment:
    slot: SlotPlan
    qty_delta_cases: int
    reason_code: str
    tracking_key: str | None = None


@dataclass(frozen=True, slots=True)
class PostPickPolicy:
    release_pending_movements: bool = False
    adjustments: tuple[PolicyAdjustment, ...] = ()


@dataclass(frozen=True, slots=True)
class QaPolicy:
    physical_damage: bool
    event_type: str
    reason_code: str
    disposition_code: str
    adjustment_reason_code: str | None
    tracking_key: str | None = None


class DriverPolicy(Protocol):
    def trip_zone(self, trip_index: int, default_zone_id: str) -> str: ...
    def trip_selector(self, trip_index: int, default_selector_id: str) -> str: ...
    def slot(self, trip_index: int, line_index: int, default_slot: SlotPlan) -> SlotPlan: ...
    def requested_quantity(self, slot: SlotPlan, default_quantity: int) -> int: ...
    def force_short(self, slot: SlotPlan, default_force_short: bool) -> bool: ...
    def movement_mode(self, slot: SlotPlan) -> str: ...
    def after_replenishment(
        self,
        task_id: str,
        slot: SlotPlan,
        movement_mode: str,
        confirmed_utc: datetime,
    ) -> None: ...
    def after_physical_movement(self, task_id: str, completed_utc: datetime) -> None: ...
    def after_trip(self, trip_id: str, selector_id: str) -> None: ...
    def after_pick(
        self,
        pick_id: str,
        selector_id: str,
        slot: SlotPlan,
        result: PhysicalPickResult,
    ) -> PostPickPolicy: ...
    def qa_target_count(self, default_count: int) -> int: ...
    def adjustment_target_count(self, default_count: int) -> int: ...
    def qa_policy(self, qa_index: int, default_damage: bool, slot: SlotPlan) -> QaPolicy: ...
    def after_qa(
        self, tracking_key: str | None, qa_event_id: str, adjustment_id: str | None
    ) -> None: ...
    def after_adjustment(self, tracking_key: str | None, adjustment_id: str) -> None: ...


class StandardDriverPolicy:
    """Leave ordinary baseline allocation and timing unchanged."""

    def trip_zone(self, trip_index: int, default_zone_id: str) -> str:
        del trip_index
        return default_zone_id

    def trip_selector(self, trip_index: int, default_selector_id: str) -> str:
        del trip_index
        return default_selector_id

    def slot(self, trip_index: int, line_index: int, default_slot: SlotPlan) -> SlotPlan:
        del trip_index, line_index
        return default_slot

    def requested_quantity(self, slot: SlotPlan, default_quantity: int) -> int:
        del slot
        return default_quantity

    def force_short(self, slot: SlotPlan, default_force_short: bool) -> bool:
        del slot
        return default_force_short

    def movement_mode(self, slot: SlotPlan) -> str:
        del slot
        return "coordinated"

    def after_replenishment(
        self,
        task_id: str,
        slot: SlotPlan,
        movement_mode: str,
        confirmed_utc: datetime,
    ) -> None:
        del task_id, slot, movement_mode, confirmed_utc

    def after_physical_movement(self, task_id: str, completed_utc: datetime) -> None:
        del task_id, completed_utc

    def after_trip(self, trip_id: str, selector_id: str) -> None:
        del trip_id, selector_id

    def after_pick(
        self,
        pick_id: str,
        selector_id: str,
        slot: SlotPlan,
        result: PhysicalPickResult,
    ) -> PostPickPolicy:
        del pick_id, selector_id, slot, result
        return PostPickPolicy()

    def qa_target_count(self, default_count: int) -> int:
        return default_count

    def adjustment_target_count(self, default_count: int) -> int:
        return default_count

    def qa_policy(self, qa_index: int, default_damage: bool, slot: SlotPlan) -> QaPolicy:
        del qa_index, slot
        return QaPolicy(
            physical_damage=default_damage,
            event_type="DAMAGE_FOUND" if default_damage else "COUNT_VERIFICATION",
            reason_code="DAMAGED_CASE" if default_damage else "ROUTINE_CHECK",
            disposition_code="DISPOSE" if default_damage else "NO_ACTION",
            adjustment_reason_code="DAMAGE" if default_damage else None,
        )

    def after_qa(
        self, tracking_key: str | None, qa_event_id: str, adjustment_id: str | None
    ) -> None:
        del tracking_key, qa_event_id, adjustment_id

    def after_adjustment(self, tracking_key: str | None, adjustment_id: str) -> None:
        del tracking_key, adjustment_id


def standard_policy(inputs: BaselineInputs) -> StandardDriverPolicy:
    del inputs
    return StandardDriverPolicy()
