"""Typed public commands for the independent schema-3 WMS."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class WmsCommand:
    run_id: str
    command_id: str
    event_utc: datetime
    recorded_utc: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateTrip(WmsCommand):
    shift_id: str
    selector_id: str
    assigned_zone_id: str
    end_utc: datetime
    planned_pick_lines: int
    planned_cases: int
    continuation_flag: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class AssignItemToLocation(WmsCommand):
    location_id: str
    item_id: str
    code_date: date | None
    minimum_qty_cases: int | None = None
    reorder_trigger_cases: int | None = None
    target_qty_cases: int | None = None
    maximum_qty_cases: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ClearLocation(WmsCommand):
    location_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordPickAttempt(WmsCommand):
    trip_id: str
    selector_id: str
    item_id: str
    location_id: str
    requested_qty_cases: int
    picked_qty_cases: int
    short_qty_cases: int
    short_reason_code: str | None
    eligible_pick_flag: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateReplenishmentTask(WmsCommand):
    item_id: str
    source_location_id: str
    destination_location_id: str
    requested_qty_cases: int
    operator_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class StartReplenishmentTask(WmsCommand):
    replenishment_task_id: str
    operator_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfirmReplenishmentTask(WmsCommand):
    replenishment_task_id: str
    confirmed_qty_cases: int
    operator_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TransferInventory(WmsCommand):
    item_id: str
    source_location_id: str
    destination_location_id: str
    qty_cases: int
    operator_id: str | None = None
    reason_code: str = "DIRECT_TRANSFER"


@dataclass(frozen=True, slots=True, kw_only=True)
class AdjustInventory(WmsCommand):
    item_id: str
    location_id: str
    operator_id: str
    qty_delta_cases: int
    reason_code: str
    reference_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordQaEvent(WmsCommand):
    item_id: str
    location_id: str
    operator_id: str
    event_type: str
    qty_affected_cases: int
    reason_code: str
    disposition_code: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordSystemEvent(WmsCommand):
    event_type: str
    end_utc: datetime
    severity_code: str
    zone_id: str | None = None
    location_id: str | None = None
    aisle_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureInventorySnapshot(WmsCommand):
    snapshot_type: str
    source_code: str


@dataclass(frozen=True, slots=True)
class WmsCommandResult:
    command_id: str
    result_record_type: str
    result_record_id: str
    event_sequence: int | None
    transaction_ids: tuple[str, ...] = ()


def command_payload_hash(command: WmsCommand) -> str:
    """Return a stable hash of a command payload for audit and duplicate checks."""

    payload = json.dumps(
        asdict(command),
        default=_json_default,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported command payload value: {type(value).__name__}")
