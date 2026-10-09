"""Deterministic handling-unit and opening-inventory generation for Phase 1."""

from __future__ import annotations

import sqlite3
from typing import Any

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.domain.identifiers import generate_identifier
from operational_variance_toolkit.domain.opening_inventory import (
    HandlingUnitRecord,
    InventorySnapshotRecord,
    PhysicalInventoryState,
)
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.generation.random_source import create_named_random_streams
from operational_variance_toolkit.storage.repositories import OpeningInventoryRepository


class OpeningInventoryGenerationResult:
    """Container for generated opening inventory artifacts."""

    def __init__(
        self,
        handling_units: list[HandlingUnitRecord],
        inventory_snapshots: list[InventorySnapshotRecord],
        physical_state: PhysicalInventoryState,
    ) -> None:
        self.handling_units = handling_units
        self.inventory_snapshots = inventory_snapshots
        self.physical_state = physical_state


def generate_opening_inventory(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    run_id: str,
) -> OpeningInventoryGenerationResult:
    """Generate deterministic opening handling units and inventory snapshots."""

    streams = create_named_random_streams(config.run.seed)
    rng = streams["opening_inventory"]

    repository = OpeningInventoryRepository(connection)
    item_rows = repository.list_items(run_id)

    handling_units: list[HandlingUnitRecord] = []
    inventory_snapshots: list[InventorySnapshotRecord] = []
    location_quantities: dict[tuple[str, str], int] = {}
    item_quantities: dict[str, int] = {}
    reserve_locations_by_zone: dict[str, list[str]] = {}
    reserve_offsets_by_zone: dict[str, int] = {}
    handling_unit_index = 1
    snapshot_index = 1

    for index, (item_id, required_zone_code, velocity_class, cases_per_pallet) in enumerate(
        item_rows, start=1
    ):
        forward_location_id = repository.get_forward_location_for_item(run_id, item_id)
        reserve_locations = reserve_locations_by_zone.setdefault(
            required_zone_code,
            repository.list_reserve_locations_for_zone(run_id, required_zone_code),
        )
        reserve_offset = reserve_offsets_by_zone.get(required_zone_code, 0)
        reserve_location_id = (
            reserve_locations[reserve_offset] if reserve_offset < len(reserve_locations) else None
        )
        reserve_offsets_by_zone[required_zone_code] = reserve_offset + 1
        if forward_location_id is None or reserve_location_id is None:
            raise DataValidationError("Unable to assign valid forward or reserve location")

        forward_qty = _derive_forward_quantity(index, velocity_class, cases_per_pallet, rng)
        reserve_qty = _derive_reserve_quantity(index, velocity_class, cases_per_pallet, rng)
        forward_capacity = _location_capacity_for_type(connection, run_id, forward_location_id)
        reserve_capacity = _location_capacity_for_type(connection, run_id, reserve_location_id)
        forward_qty = min(forward_qty, forward_capacity)
        reserve_qty = min(reserve_qty, reserve_capacity)
        total_qty = forward_qty + reserve_qty

        location_quantities[(item_id, forward_location_id)] = forward_qty
        location_quantities[(item_id, reserve_location_id)] = reserve_qty
        item_quantities[item_id] = total_qty

        for location_id, quantity in (
            (forward_location_id, forward_qty),
            (reserve_location_id, reserve_qty),
        ):
            handling_unit_id = generate_identifier("HU", handling_unit_index)
            snapshot_id = generate_identifier("SNAP", snapshot_index)
            handling_unit_index += 1
            snapshot_index += 1
            handling_unit = HandlingUnitRecord(
                run_id=run_id,
                handling_unit_id=handling_unit_id,
                item_id=item_id,
                lot_code=None,
                expiration_date=None,
                initial_qty_cases=quantity,
                status="AVAILABLE",
            )
            snapshot = InventorySnapshotRecord(
                run_id=run_id,
                snapshot_id=snapshot_id,
                snapshot_utc=config.run.start_utc.isoformat(),
                snapshot_type="OPENING_SYSTEM",
                item_id=item_id,
                location_id=location_id,
                handling_unit_id=handling_unit_id,
                qty_cases=quantity,
                source_code="opening_inventory",
            )
            handling_units.append(handling_unit)
            inventory_snapshots.append(snapshot)
            repository.insert_handling_unit(run_id, handling_unit_id, item_id, quantity)
            repository.insert_snapshot(
                run_id,
                snapshot_id,
                config.run.start_utc.isoformat(),
                "OPENING_SYSTEM",
                item_id,
                location_id,
                handling_unit_id,
                quantity,
                "opening_inventory",
            )

    result = OpeningInventoryGenerationResult(
        handling_units=handling_units,
        inventory_snapshots=inventory_snapshots,
        physical_state=PhysicalInventoryState(
            run_id=run_id,
            location_quantities=location_quantities,
            item_quantities=item_quantities,
        ),
    )
    validate_opening_inventory_state(
        connection, config, run_id, result.physical_state, handling_units, inventory_snapshots
    )
    return result


def validate_opening_inventory_state(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    run_id: str,
    physical_state: PhysicalInventoryState,
    handling_units: list[HandlingUnitRecord],
    inventory_snapshots: list[InventorySnapshotRecord],
) -> None:
    """Validate opening inventory integrity and reconciliation rules."""

    repository = OpeningInventoryRepository(connection)
    physical_location_totals: dict[str, int] = {}

    for quantity in physical_state.item_quantities.values():
        if not isinstance(quantity, int) or quantity < 0:
            raise DataValidationError("Opening inventory quantities must be nonnegative integers")

    for (item_id, location_id), quantity in physical_state.location_quantities.items():
        if not isinstance(quantity, int) or quantity < 0:
            raise DataValidationError("Opening inventory quantities must be nonnegative integers")
        location_details = repository.get_location_details(run_id, location_id)
        if location_details is None:
            raise DataValidationError("Opening inventory uses an invalid location")
        location_type, pickable_flag, capacity = location_details
        if capacity is not None and quantity > capacity:
            raise DataValidationError("Opening inventory exceeds location capacity")
        if location_type == "PICK" and pickable_flag != 1:
            raise DataValidationError("Forward inventory uses a non-pickable location")

        item_details = repository.get_item_details(run_id, item_id)
        if item_details is None:
            raise DataValidationError("Opening inventory uses an invalid item")
        if not repository.item_is_valid_at_location(run_id, item_id, location_id):
            raise DataValidationError("Opening inventory uses an invalid item/location pair")
        physical_location_totals[location_id] = (
            physical_location_totals.get(location_id, 0) + quantity
        )

    for location_id, quantity in physical_location_totals.items():
        location_details = repository.get_location_details(run_id, location_id)
        if location_details is None:
            raise DataValidationError("Opening inventory uses an invalid location")
        _, _, capacity = location_details
        if capacity is not None and quantity > capacity:
            raise DataValidationError("Opening inventory exceeds aggregate location capacity")

    for handling_unit in handling_units:
        if handling_unit.initial_qty_cases <= 0:
            raise DataValidationError("Handling unit quantities must be positive")
        snapshot_total = sum(
            snapshot.qty_cases
            for snapshot in inventory_snapshots
            if snapshot.handling_unit_id == handling_unit.handling_unit_id
        )
        if snapshot_total != handling_unit.initial_qty_cases:
            raise DataValidationError("Handling units do not reconcile to snapshots")

    handling_unit_locations: dict[str, set[str]] = {}
    system_location_quantities: dict[tuple[str, str], int] = {}
    for snapshot in inventory_snapshots:
        if snapshot.qty_cases < 0:
            raise DataValidationError("Opening inventory snapshots cannot be negative")
        if snapshot.location_id is None:
            raise DataValidationError("Opening inventory snapshots must have a location")
        if snapshot.snapshot_utc != config.run.start_utc.isoformat():
            raise DataValidationError("Opening inventory snapshot timestamps are invalid")
        if snapshot.handling_unit_id is not None:
            handling_unit_locations.setdefault(snapshot.handling_unit_id, set()).add(
                snapshot.location_id
            )
        key = (snapshot.item_id, snapshot.location_id)
        system_location_quantities[key] = (
            system_location_quantities.get(key, 0) + snapshot.qty_cases
        )

    if any(len(locations) > 1 for locations in handling_unit_locations.values()):
        raise DataValidationError("Handling units cannot span multiple opening locations")

    for item_id, quantity in physical_state.item_quantities.items():
        if quantity != sum(
            snapshot.qty_cases for snapshot in inventory_snapshots if snapshot.item_id == item_id
        ):
            raise DataValidationError("Physical and system opening totals are not aligned")

    if physical_state.location_quantities != system_location_quantities:
        raise DataValidationError("Physical and system opening location state is not aligned")


def _derive_forward_quantity(
    index: int, velocity_class: str, cases_per_pallet: int, rng: Any
) -> int:
    base = 4 + (index % 5) * 2
    velocity_adjustment = {"A": 4, "B": 2, "C": 1}.get(velocity_class, 1)
    return max(0, base + velocity_adjustment + int(rng.integers(0, 3)))


def _derive_reserve_quantity(
    index: int, velocity_class: str, cases_per_pallet: int, rng: Any
) -> int:
    velocity_adjustment = {"A": 12, "B": 8, "C": 4}.get(velocity_class, 4)
    return max(0, cases_per_pallet * 2 + velocity_adjustment + int(rng.integers(0, 3)))


def _location_capacity_for_type(
    connection: sqlite3.Connection, run_id: str, location_id: str
) -> int:
    row = connection.execute(
        "SELECT capacity_cases FROM location WHERE run_id = ? AND location_id = ?",
        (run_id, location_id),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0
