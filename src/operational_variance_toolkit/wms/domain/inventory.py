"""Typed records and calculations for the schema-3 WMS inventory files."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose

_CUBE_TOLERANCE = 1e-6


def calculate_case_cube_ft3(length_in: float, width_in: float, height_in: float) -> float:
    """Calculate case cube from positive inch dimensions."""

    if min(length_in, width_in, height_in) <= 0:
        raise ValueError("Case dimensions must be positive")
    return round(length_in * width_in * height_in / 1728.0, 6)


def calculate_cases_per_pallet(cases_per_layer: int, layers_per_pallet: int) -> int:
    """Calculate a pallet pattern from positive whole-number inputs."""

    if cases_per_layer <= 0 or layers_per_pallet <= 0:
        raise ValueError("Pallet pattern values must be positive")
    return cases_per_layer * layers_per_pallet


def calculate_location_maximum_cases(pallet_capacity: int, cases_per_pallet: int) -> int:
    """Calculate item-dependent physical capacity for a pallet-bearing location."""

    if pallet_capacity <= 0 or cases_per_pallet <= 0:
        raise ValueError("Pallet capacity and cases per pallet must be positive")
    return pallet_capacity * cases_per_pallet


@dataclass(frozen=True, slots=True)
class ZoneRecord:
    run_id: str
    zone_id: str
    facility_id: str
    zone_code: str
    min_temp_f: float | None
    max_temp_f: float | None
    active_flag: int = 1


@dataclass(frozen=True, slots=True)
class ItemMasterRecord:
    run_id: str
    item_id: str
    item_description: str
    category: str
    required_zone_code: str
    case_length_in: float
    case_width_in: float
    case_height_in: float
    case_cube_ft3: float
    case_weight_lb: float
    cases_per_layer: int
    layers_per_pallet: int
    cases_per_pallet: int
    fragility_score: float
    shelf_life_days: int | None
    velocity_class: str
    expected_cases_per_day: float
    active_flag: int = 1

    def __post_init__(self) -> None:
        expected_cube = calculate_case_cube_ft3(
            self.case_length_in,
            self.case_width_in,
            self.case_height_in,
        )
        if not isclose(
            self.case_cube_ft3,
            expected_cube,
            rel_tol=0.0,
            abs_tol=_CUBE_TOLERANCE,
        ):
            raise ValueError("case_cube_ft3 does not match case dimensions")
        expected_pallet = calculate_cases_per_pallet(
            self.cases_per_layer,
            self.layers_per_pallet,
        )
        if self.cases_per_pallet != expected_pallet:
            raise ValueError("cases_per_pallet does not match the pallet pattern")
        if self.case_weight_lb <= 0:
            raise ValueError("case_weight_lb must be positive")
        if not 0.0 <= self.fragility_score <= 1.0:
            raise ValueError("fragility_score must be between zero and one")
        if self.shelf_life_days is not None and self.shelf_life_days <= 0:
            raise ValueError("shelf_life_days must be positive when provided")


@dataclass(frozen=True, slots=True)
class LocationMasterRecord:
    run_id: str
    location_id: str
    zone_id: str
    location_type: str
    aisle_code: str | None
    bay_number: int | None
    level_number: int | None
    position_number: int | None
    pallet_capacity: int | None
    pickable_flag: int
    active_flag: int

    def __post_init__(self) -> None:
        if self.location_type in {"PICK", "RESERVE"}:
            if self.aisle_code is None or self.bay_number is None:
                raise ValueError("Ordinary inventory locations require aisle and bay")
            if self.pallet_capacity is None or self.pallet_capacity <= 0:
                raise ValueError("Ordinary inventory locations require pallet capacity")
        if self.location_type == "PICK" and self.pickable_flag != 1:
            raise ValueError("PICK locations must be pickable")
        if self.location_type != "PICK" and self.pickable_flag != 0:
            raise ValueError("Only PICK locations may be pickable")


@dataclass(frozen=True, slots=True)
class InventoryMasterRecord:
    run_id: str
    location_id: str
    item_id: str | None
    qty_on_hand_cases: int
    code_date: str | None
    reorder_trigger_cases: int | None
    minimum_qty_cases: int | None
    target_qty_cases: int | None
    maximum_qty_cases: int | None
    last_transaction_id: str | None
    last_updated_utc: str

    def __post_init__(self) -> None:
        if self.qty_on_hand_cases < 0:
            raise ValueError("qty_on_hand_cases cannot be negative")
        if self.item_id is None and (self.qty_on_hand_cases != 0 or self.code_date is not None):
            raise ValueError("An unassigned location must be empty and have no code date")
        controls = (
            self.minimum_qty_cases,
            self.reorder_trigger_cases,
            self.target_qty_cases,
            self.maximum_qty_cases,
        )
        if any(value is not None for value in controls):
            if any(value is None for value in controls):
                raise ValueError("Replenishment controls must be all present or all absent")
            minimum, trigger, target, maximum = controls
            assert minimum is not None
            assert trigger is not None
            assert target is not None
            assert maximum is not None
            if min(controls) < 0 or not minimum <= trigger <= target <= maximum:
                raise ValueError("Replenishment controls are not ordered")


@dataclass(frozen=True, slots=True)
class InventorySnapshotRecord:
    run_id: str
    snapshot_batch_id: str
    snapshot_line_id: str
    snapshot_utc: str
    snapshot_type: str
    location_id: str
    item_id: str | None
    qty_on_hand_cases: int
    code_date: str | None
    last_transaction_id: str | None
    source_code: str
