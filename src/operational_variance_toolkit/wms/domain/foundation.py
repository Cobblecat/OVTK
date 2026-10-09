"""Aggregate record set used to initialize a schema-3 WMS."""

from __future__ import annotations

from dataclasses import dataclass

from operational_variance_toolkit.wms.domain.inventory import (
    InventoryMasterRecord,
    InventorySnapshotRecord,
    ItemMasterRecord,
    LocationMasterRecord,
    ZoneRecord,
)


@dataclass(frozen=True, slots=True)
class OperatorRecord:
    run_id: str
    operator_id: str
    role: str
    home_zone_id: str | None
    shift_code: str
    experience_months: int
    active_flag: int = 1


@dataclass(frozen=True, slots=True)
class ShiftRecord:
    run_id: str
    shift_id: str
    facility_id: str
    shift_code: str
    start_utc: str
    end_utc: str
    operating_date_local: str


@dataclass(frozen=True, slots=True)
class WorkAssignmentRecord:
    run_id: str
    work_assignment_id: str
    operator_id: str
    shift_id: str
    role: str
    zone_id: str | None
    start_utc: str
    end_utc: str


@dataclass(frozen=True, slots=True)
class WmsFoundationRecords:
    zones: tuple[ZoneRecord, ...]
    items: tuple[ItemMasterRecord, ...]
    locations: tuple[LocationMasterRecord, ...]
    operators: tuple[OperatorRecord, ...]
    shifts: tuple[ShiftRecord, ...]
    work_assignments: tuple[WorkAssignmentRecord, ...]
    inventory: tuple[InventoryMasterRecord, ...]
    opening_snapshot: tuple[InventorySnapshotRecord, ...]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "zone": len(self.zones),
            "item_master": len(self.items),
            "location_master": len(self.locations),
            "operator": len(self.operators),
            "shift": len(self.shifts),
            "work_assignment": len(self.work_assignments),
            "inventory_master": len(self.inventory),
            "inventory_snapshot": len(self.opening_snapshot),
        }
