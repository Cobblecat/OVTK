"""Typed schema-3 WMS state and persistence records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class InventoryPosition:
    run_id: str
    location_id: str
    item_id: str | None
    qty_on_hand_cases: int
    code_date: str | None
    minimum_qty_cases: int | None
    reorder_trigger_cases: int | None
    target_qty_cases: int | None
    maximum_qty_cases: int | None
    last_transaction_id: str | None
    last_updated_utc: str
    location_type: str
    zone_code: str
    pallet_capacity: int | None
    pickable_flag: int
    active_flag: int
    item_required_zone_code: str | None
    cases_per_pallet: int | None


@dataclass(frozen=True, slots=True)
class TripState:
    run_id: str
    trip_id: str
    shift_id: str
    selector_id: str
    assigned_zone_id: str
    start_utc: str
    end_utc: str


@dataclass(frozen=True, slots=True)
class ShiftState:
    run_id: str
    shift_id: str
    start_utc: str
    end_utc: str


@dataclass(frozen=True, slots=True)
class ReplenishmentTaskState:
    run_id: str
    replenishment_task_id: str
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


@dataclass(frozen=True, slots=True)
class EventSequenceRecord:
    run_id: str
    event_sequence: int
    event_type: str
    source_record_id: str
    event_utc: datetime
    recorded_utc: datetime


@dataclass(frozen=True, slots=True)
class InventoryTransactionRecord:
    run_id: str
    transaction_id: str
    transaction_group_id: str
    command_id: str
    event_sequence: int
    line_number: int
    transaction_type: str
    location_id: str
    related_location_id: str | None
    item_id: str
    qty_delta_cases: int
    balance_before_cases: int
    balance_after_cases: int
    operator_id: str | None
    event_utc: datetime
    recorded_utc: datetime
    reason_code: str | None
    source_record_type: str
    source_record_id: str


@dataclass(frozen=True, slots=True)
class TripRecord:
    run_id: str
    trip_id: str
    shift_id: str
    selector_id: str
    assigned_zone_id: str
    start_utc: datetime
    end_utc: datetime
    continuation_flag: int
    planned_pick_lines: int
    planned_cases: int


@dataclass(frozen=True, slots=True)
class PickEventRecord:
    run_id: str
    pick_event_id: str
    command_id: str
    event_sequence: int
    trip_id: str
    selector_id: str
    item_id: str
    pick_location_id: str
    event_utc: datetime
    recorded_utc: datetime
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
    create_command_id: str
    confirm_command_id: str | None
    event_sequence: int | None
    item_id: str
    source_location_id: str
    destination_location_id: str
    operator_id: str | None
    created_utc: datetime
    started_utc: datetime | None
    confirmed_utc: datetime | None
    recorded_utc: datetime
    requested_qty_cases: int
    confirmed_qty_cases: int
    status: str
    delay_reason_code: str | None


@dataclass(frozen=True, slots=True)
class InventoryAdjustmentRecord:
    run_id: str
    adjustment_id: str
    command_id: str
    event_sequence: int
    item_id: str
    location_id: str
    operator_id: str | None
    effective_utc: datetime
    recorded_utc: datetime
    qty_delta_cases: int
    reason_code: str
    reference_code: str | None


@dataclass(frozen=True, slots=True)
class QaEventRecord:
    run_id: str
    qa_event_id: str
    command_id: str
    event_sequence: int
    item_id: str
    location_id: str
    operator_id: str | None
    event_type: str
    occurred_utc: datetime
    recorded_utc: datetime
    qty_affected_cases: int
    reason_code: str
    disposition_code: str


@dataclass(frozen=True, slots=True)
class SystemEventRecord:
    run_id: str
    system_event_id: str
    command_id: str
    event_sequence: int
    event_type: str
    zone_id: str | None
    location_id: str | None
    aisle_code: str | None
    start_utc: datetime
    end_utc: datetime
    severity_code: str
    recorded_utc: datetime


@dataclass(frozen=True, slots=True)
class SnapshotLineRecord:
    run_id: str
    snapshot_batch_id: str
    snapshot_line_id: str
    snapshot_utc: datetime
    snapshot_type: str
    location_id: str
    item_id: str | None
    qty_on_hand_cases: int
    code_date: date | None
    last_transaction_id: str | None
    source_code: str
