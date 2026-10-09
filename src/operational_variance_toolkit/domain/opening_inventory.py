"""Typed domain models for opening inventory and physical-state tracking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandlingUnitRecord:
    """A deterministic handling unit representing a pallet or case bundle."""

    run_id: str
    handling_unit_id: str
    item_id: str
    lot_code: str | None
    expiration_date: str | None
    initial_qty_cases: int
    status: str


@dataclass(frozen=True, slots=True)
class InventorySnapshotRecord:
    """A deterministic opening inventory snapshot record."""

    run_id: str
    snapshot_id: str
    snapshot_utc: str
    snapshot_type: str
    item_id: str
    location_id: str | None
    handling_unit_id: str | None
    qty_cases: int
    source_code: str


@dataclass(frozen=True, slots=True)
class PhysicalInventoryState:
    """In-memory physical inventory state for deterministic later simulation."""

    run_id: str
    location_quantities: dict[tuple[str, str], int]
    item_quantities: dict[str, int]
