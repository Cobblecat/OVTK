"""Typed records and deterministic state transitions for Phase 2 operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from operational_variance_toolkit.errors import DataValidationError


@dataclass(frozen=True, slots=True)
class TripRecord:
    run_id: str
    trip_id: str
    shift_id: str
    selector_id: str
    assigned_zone_id: str
    start_utc: str
    end_utc: str
    continuation_flag: int
    planned_pick_lines: int
    planned_cases: int


@dataclass(frozen=True, slots=True)
class PickEventRecord:
    run_id: str
    pick_event_id: str
    event_sequence: int
    trip_id: str
    selector_id: str
    item_id: str
    pick_location_id: str
    event_utc: str
    recorded_utc: str
    requested_qty_cases: int
    picked_qty_cases: int
    short_qty_cases: int
    short_reason_code: str | None
    system_qty_before_cases: int
    system_qty_after_cases: int
    eligible_pick_flag: int


@dataclass(frozen=True, slots=True)
class ReplenishmentTaskRecord:
    run_id: str
    replenishment_task_id: str
    event_sequence: int
    item_id: str
    source_location_id: str
    destination_location_id: str
    operator_id: str | None
    created_utc: str
    started_utc: str | None
    confirmed_utc: str | None
    recorded_utc: str
    requested_qty_cases: int
    confirmed_qty_cases: int
    status: str
    delay_reason_code: str | None


@dataclass(frozen=True, slots=True)
class QaEventRecord:
    run_id: str
    qa_event_id: str
    event_sequence: int
    item_id: str
    location_id: str
    handling_unit_id: str | None
    operator_id: str | None
    event_type: str
    occurred_utc: str
    recorded_utc: str
    qty_affected_cases: int
    reason_code: str
    disposition_code: str


@dataclass(frozen=True, slots=True)
class InventoryAdjustmentRecord:
    run_id: str
    adjustment_id: str
    event_sequence: int
    item_id: str
    location_id: str
    operator_id: str | None
    effective_utc: str
    recorded_utc: str
    qty_delta_cases: int
    reason_code: str
    reference_code: str | None


@dataclass(frozen=True, slots=True)
class SystemEventRecord:
    run_id: str
    system_event_id: str
    event_sequence: int
    event_type: str
    zone_id: str | None
    location_id: str | None
    equipment_area: str | None
    start_utc: str
    end_utc: str
    severity_code: str
    recorded_utc: str


@dataclass(frozen=True, slots=True)
class InventorySnapshotRecord:
    run_id: str
    snapshot_id: str
    snapshot_utc: str
    snapshot_type: str
    item_id: str
    location_id: str
    handling_unit_id: str | None
    qty_cases: int
    source_code: str


@dataclass(slots=True)
class SimulatorInventoryState:
    """Hidden physical state and analyst-facing system state during Phase 2 generation."""

    run_id: str
    physical: dict[tuple[str, str], int] = field(default_factory=dict)
    system: dict[tuple[str, str], int] = field(default_factory=dict)

    def physical_quantity(self, item_id: str, location_id: str) -> int:
        return self.physical.get((item_id, location_id), 0)

    def system_quantity(self, item_id: str, location_id: str) -> int:
        return self.system.get((item_id, location_id), 0)

    def require_nonnegative(self) -> None:
        if any(quantity < 0 for quantity in self.physical.values()):
            raise DataValidationError("Physical inventory state cannot be negative")
        if any(quantity < 0 for quantity in self.system.values()):
            raise DataValidationError("System inventory state cannot be negative")


@dataclass(slots=True)
class StateTransitionProcessor:
    """Apply accepted events in deterministic sequence order."""

    state: SimulatorInventoryState
    _next_sequence: int = 1

    def next_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def apply_pick(
        self,
        *,
        pick_event_id: str,
        trip_id: str,
        selector_id: str,
        item_id: str,
        location_id: str,
        event_utc: datetime,
        requested_qty_cases: int,
        force_short: bool = False,
    ) -> PickEventRecord:
        if requested_qty_cases <= 0:
            raise DataValidationError("Pick requested quantity must be positive")

        physical_before = self.state.physical_quantity(item_id, location_id)
        system_before = self.state.system_quantity(item_id, location_id)
        available = min(physical_before, system_before)
        if force_short and requested_qty_cases > 1 and available >= requested_qty_cases:
            picked = requested_qty_cases - 1
        else:
            picked = min(requested_qty_cases, available)
        short = requested_qty_cases - picked
        system_after = system_before - picked

        if picked < 0 or short < 0 or system_after < 0 or physical_before - picked < 0:
            raise DataValidationError("Pick transition would create invalid inventory")

        key = (item_id, location_id)
        self.state.physical[key] = physical_before - picked
        self.state.system[key] = system_after
        self.state.require_nonnegative()
        return PickEventRecord(
            run_id=self.state.run_id,
            pick_event_id=pick_event_id,
            event_sequence=self.next_sequence(),
            trip_id=trip_id,
            selector_id=selector_id,
            item_id=item_id,
            pick_location_id=location_id,
            event_utc=_iso(event_utc),
            recorded_utc=_iso(event_utc + timedelta(seconds=30)),
            requested_qty_cases=requested_qty_cases,
            picked_qty_cases=picked,
            short_qty_cases=short,
            short_reason_code="BASELINE_ACCESS" if short else None,
            system_qty_before_cases=system_before,
            system_qty_after_cases=system_after,
            eligible_pick_flag=1,
        )

    def apply_replenishment(
        self,
        *,
        replenishment_task_id: str,
        item_id: str,
        source_location_id: str,
        destination_location_id: str,
        operator_id: str | None,
        created_utc: datetime,
        requested_qty_cases: int,
    ) -> ReplenishmentTaskRecord:
        if requested_qty_cases <= 0:
            raise DataValidationError("Replenishment requested quantity must be positive")

        source_physical = self.state.physical_quantity(item_id, source_location_id)
        source_system = self.state.system_quantity(item_id, source_location_id)
        destination_physical = self.state.physical_quantity(item_id, destination_location_id)
        destination_system = self.state.system_quantity(item_id, destination_location_id)
        confirmed = min(requested_qty_cases, source_physical, source_system)
        if confirmed <= 0:
            raise DataValidationError("Replenishment source has no available quantity")

        source_key = (item_id, source_location_id)
        destination_key = (item_id, destination_location_id)
        self.state.physical[source_key] = source_physical - confirmed
        self.state.physical[destination_key] = destination_physical + confirmed
        self.state.system[source_key] = source_system - confirmed
        self.state.system[destination_key] = destination_system + confirmed
        self.state.require_nonnegative()

        started_utc = created_utc + timedelta(minutes=1)
        confirmed_utc = created_utc + timedelta(minutes=2)
        return ReplenishmentTaskRecord(
            run_id=self.state.run_id,
            replenishment_task_id=replenishment_task_id,
            event_sequence=self.next_sequence(),
            item_id=item_id,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            operator_id=operator_id,
            created_utc=_iso(created_utc),
            started_utc=_iso(started_utc),
            confirmed_utc=_iso(confirmed_utc),
            recorded_utc=_iso(confirmed_utc + timedelta(seconds=30)),
            requested_qty_cases=requested_qty_cases,
            confirmed_qty_cases=confirmed,
            status="CONFIRMED",
            delay_reason_code=None,
        )

    def apply_qa_event(
        self,
        *,
        qa_event_id: str,
        item_id: str,
        location_id: str,
        operator_id: str | None,
        occurred_utc: datetime,
        qty_affected_cases: int,
        damage: bool,
    ) -> QaEventRecord:
        if qty_affected_cases <= 0:
            raise DataValidationError("QA quantity must be positive")
        physical_before = self.state.physical_quantity(item_id, location_id)
        affected = min(qty_affected_cases, physical_before)
        if affected <= 0:
            raise DataValidationError("QA event has no physical quantity to inspect")
        if damage:
            self.state.physical[(item_id, location_id)] = physical_before - affected
        self.state.require_nonnegative()
        return QaEventRecord(
            run_id=self.state.run_id,
            qa_event_id=qa_event_id,
            event_sequence=self.next_sequence(),
            item_id=item_id,
            location_id=location_id,
            handling_unit_id=None,
            operator_id=operator_id,
            event_type="DAMAGE_FOUND" if damage else "INSPECTION",
            occurred_utc=_iso(occurred_utc),
            recorded_utc=_iso(occurred_utc + timedelta(minutes=1)),
            qty_affected_cases=affected,
            reason_code="DAMAGED_CASE" if damage else "ROUTINE_CHECK",
            disposition_code="DISPOSE" if damage else "NO_ACTION",
        )

    def apply_adjustment(
        self,
        *,
        adjustment_id: str,
        item_id: str,
        location_id: str,
        operator_id: str | None,
        effective_utc: datetime,
        qty_delta_cases: int,
        reason_code: str,
        reference_code: str | None = None,
    ) -> InventoryAdjustmentRecord:
        if qty_delta_cases == 0:
            raise DataValidationError("Inventory adjustment must be nonzero")
        key = (item_id, location_id)
        system_before = self.state.system_quantity(item_id, location_id)
        system_after = system_before + qty_delta_cases
        if system_after < 0:
            raise DataValidationError("Inventory adjustment would make system inventory negative")
        self.state.system[key] = system_after
        if reason_code == "FOUND_PRODUCT":
            self.state.physical[key] = (
                self.state.physical_quantity(item_id, location_id) + qty_delta_cases
            )
        self.state.require_nonnegative()
        return InventoryAdjustmentRecord(
            run_id=self.state.run_id,
            adjustment_id=adjustment_id,
            event_sequence=self.next_sequence(),
            item_id=item_id,
            location_id=location_id,
            operator_id=operator_id,
            effective_utc=_iso(effective_utc),
            recorded_utc=_iso(effective_utc + timedelta(minutes=1)),
            qty_delta_cases=qty_delta_cases,
            reason_code=reason_code,
            reference_code=reference_code,
        )

    def record_system_event(
        self,
        *,
        system_event_id: str,
        event_type: str,
        zone_id: str | None,
        location_id: str | None,
        equipment_area: str | None,
        start_utc: datetime,
        end_utc: datetime,
        severity_code: str,
    ) -> SystemEventRecord:
        if start_utc >= end_utc:
            raise DataValidationError("System event start must be before end")
        if zone_id is None and location_id is None and equipment_area is None:
            raise DataValidationError("System event requires a scope")
        return SystemEventRecord(
            run_id=self.state.run_id,
            system_event_id=system_event_id,
            event_sequence=self.next_sequence(),
            event_type=event_type,
            zone_id=zone_id,
            location_id=location_id,
            equipment_area=equipment_area,
            start_utc=_iso(start_utc),
            end_utc=_iso(end_utc),
            severity_code=severity_code,
            recorded_utc=_iso(start_utc + timedelta(minutes=1)),
        )


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
