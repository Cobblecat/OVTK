"""Deterministic schema-3 WMS master and opening-state generation."""

from __future__ import annotations

from datetime import timedelta

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.domain.identifiers import (
    generate_code_identifier,
    generate_identifier,
    generate_identifier_sequence,
)
from operational_variance_toolkit.domain.time import to_facility_local
from operational_variance_toolkit.generation.random_source import create_named_random_streams
from operational_variance_toolkit.wms.domain.foundation import (
    OperatorRecord,
    ShiftRecord,
    WmsFoundationRecords,
    WorkAssignmentRecord,
)
from operational_variance_toolkit.wms.domain.inventory import (
    InventoryMasterRecord,
    InventorySnapshotRecord,
    ItemMasterRecord,
    LocationMasterRecord,
    ZoneRecord,
    calculate_case_cube_ft3,
    calculate_cases_per_pallet,
    calculate_location_maximum_cases,
)


def generate_wms_foundation(
    config: ProjectConfig,
    run_id: str,
) -> WmsFoundationRecords:
    """Build deterministic schema-3 master files and opening recorded state."""

    streams = create_named_random_streams(config.run.seed)
    item_rng = streams["master_items"]
    zone_codes = _zone_codes(config)
    zones = tuple(
        ZoneRecord(
            run_id=run_id,
            zone_id=generate_code_identifier("ZONE", zone_code),
            facility_id=config.facility.facility_id,
            zone_code=zone_code,
            min_temp_f=_zone_temperature(zone_code)[0],
            max_temp_f=_zone_temperature(zone_code)[1],
        )
        for zone_code in zone_codes
    )

    items: list[ItemMasterRecord] = []
    locations: list[LocationMasterRecord] = []
    inventory: list[InventoryMasterRecord] = []
    snapshot: list[InventorySnapshotRecord] = []
    opening_utc = config.run.start_utc.isoformat()
    snapshot_batch_id = "SNAPSHOT-OPENING-001"

    for index, item_id in enumerate(
        generate_identifier_sequence("ITEM", config.dimensions.item_count),
        start=1,
    ):
        zone_code = zone_codes[(index - 1) % len(zone_codes)]
        zone_id = generate_code_identifier("ZONE", zone_code)
        length = float(item_rng.integers(10, 25))
        width = float(item_rng.integers(8, 19))
        height = float(item_rng.integers(5, 17))
        cases_per_layer = int(item_rng.integers(5, 13))
        layers_per_pallet = int(item_rng.integers(3, 8))
        shelf_life_days = 30 + (index % 45)
        item = ItemMasterRecord(
            run_id=run_id,
            item_id=item_id,
            item_description=f"Synthetic item {index}",
            category=f"Category {((index - 1) % 8) + 1}",
            required_zone_code=zone_code,
            case_length_in=length,
            case_width_in=width,
            case_height_in=height,
            case_cube_ft3=calculate_case_cube_ft3(length, width, height),
            case_weight_lb=round(float(item_rng.uniform(8.0, 42.0)), 2),
            cases_per_layer=cases_per_layer,
            layers_per_pallet=layers_per_pallet,
            cases_per_pallet=calculate_cases_per_pallet(
                cases_per_layer,
                layers_per_pallet,
            ),
            fragility_score=round(float(item_rng.random()), 2),
            shelf_life_days=shelf_life_days,
            velocity_class=_velocity_class(index, config.dimensions.item_count),
            expected_cases_per_day=round(float(item_rng.uniform(5.0, 18.0)), 2),
        )
        items.append(item)

        pick_location = _location_for_item(
            run_id=run_id,
            zone_id=zone_id,
            item_index=index,
            location_type="PICK",
        )
        reserve_location = _location_for_item(
            run_id=run_id,
            zone_id=zone_id,
            item_index=index,
            location_type="RESERVE",
        )
        locations.extend((pick_location, reserve_location))

        pick_maximum = calculate_location_maximum_cases(
            pick_location.pallet_capacity or 0,
            item.cases_per_pallet,
        )
        minimum = max(1, pick_maximum // 10)
        trigger = max(minimum, pick_maximum // 4)
        target = max(trigger, (pick_maximum * 3) // 5)
        code_date = (config.run.start_utc.date() + timedelta(days=shelf_life_days)).isoformat()
        reserve_is_empty = _reserve_is_empty(index, config.dimensions.item_count)
        pick_inventory = InventoryMasterRecord(
            run_id=run_id,
            location_id=pick_location.location_id,
            item_id=item_id,
            qty_on_hand_cases=_opening_pick_quantity(
                index,
                config.dimensions.item_count,
                target,
                pick_maximum,
            ),
            code_date=code_date,
            reorder_trigger_cases=trigger,
            minimum_qty_cases=minimum,
            target_qty_cases=target,
            maximum_qty_cases=pick_maximum,
            last_transaction_id=None,
            last_updated_utc=opening_utc,
        )
        reserve_maximum = calculate_location_maximum_cases(
            reserve_location.pallet_capacity or 0,
            item.cases_per_pallet,
        )
        reserve_inventory = InventoryMasterRecord(
            run_id=run_id,
            location_id=reserve_location.location_id,
            item_id=None if reserve_is_empty else item_id,
            qty_on_hand_cases=(
                0 if reserve_is_empty else max(item.cases_per_pallet, reserve_maximum // 2)
            ),
            code_date=None if reserve_is_empty else code_date,
            reorder_trigger_cases=None,
            minimum_qty_cases=None,
            target_qty_cases=None,
            maximum_qty_cases=None,
            last_transaction_id=None,
            last_updated_utc=opening_utc,
        )
        inventory.extend((pick_inventory, reserve_inventory))

    shifts = _generate_shifts(config, run_id)
    operators = _generate_operators(config, run_id, zones)
    work_assignments = _generate_work_assignments(run_id, operators, shifts, zones)

    for line_number, row in enumerate(inventory, start=1):
        snapshot.append(
            InventorySnapshotRecord(
                run_id=run_id,
                snapshot_batch_id=snapshot_batch_id,
                snapshot_line_id=generate_identifier("SNAPLINE", line_number),
                snapshot_utc=opening_utc,
                snapshot_type="OPENING_SYSTEM",
                location_id=row.location_id,
                item_id=row.item_id,
                qty_on_hand_cases=row.qty_on_hand_cases,
                code_date=row.code_date,
                last_transaction_id=row.last_transaction_id,
                source_code="WMS_INITIALIZATION",
            )
        )

    return WmsFoundationRecords(
        zones=zones,
        items=tuple(items),
        locations=tuple(locations),
        operators=operators,
        shifts=shifts,
        work_assignments=work_assignments,
        inventory=tuple(inventory),
        opening_snapshot=tuple(snapshot),
    )


def _zone_codes(config: ProjectConfig) -> list[str]:
    return ["FROZEN", "CHILLED", "AMBIENT"][: config.dimensions.zone_count]


def _zone_temperature(zone_code: str) -> tuple[float | None, float | None]:
    return {
        "FROZEN": (-10.0, 0.0),
        "CHILLED": (32.0, 40.0),
        "AMBIENT": (None, None),
    }[zone_code]


def _velocity_class(index: int, item_count: int) -> str:
    if index <= max(1, item_count // 3):
        return "A"
    if index <= max(2, (item_count * 2) // 3):
        return "B"
    return "C"


def _reserve_is_empty(item_index: int, item_count: int) -> bool:
    calibration_start = item_count // 3 + 1
    return item_index >= calibration_start and (item_index - calibration_start) % 5 == 0


def _opening_pick_quantity(
    item_index: int,
    item_count: int,
    target: int,
    maximum: int,
) -> int:
    if not _reserve_is_empty(item_index, item_count):
        return target
    calibration_start = item_count // 3 + 1
    calibration_position = (item_index - calibration_start) // 5
    if calibration_position % 4 == 0:
        return 0
    if calibration_position % 4 == 1:
        return maximum - max(1, maximum // 20)
    return target


def _location_for_item(
    *,
    run_id: str,
    zone_id: str,
    item_index: int,
    location_type: str,
) -> LocationMasterRecord:
    location_offset = 0 if location_type == "PICK" else 5000
    return LocationMasterRecord(
        run_id=run_id,
        location_id=generate_identifier("LOC", location_offset + item_index, width=5),
        zone_id=zone_id,
        location_type=location_type,
        aisle_code=f"A{((item_index - 1) // 8) + 1}",
        bay_number=((item_index - 1) % 8) + 1,
        level_number=1 if location_type == "PICK" else 2,
        position_number=1,
        pallet_capacity=1 if location_type == "PICK" else 2,
        pickable_flag=1 if location_type == "PICK" else 0,
        active_flag=1,
    )


def _generate_shifts(config: ProjectConfig, run_id: str) -> tuple[ShiftRecord, ...]:
    shift_count = config.dimensions.shift_count
    interval = (config.run.end_utc - config.run.start_utc) / shift_count
    shifts: list[ShiftRecord] = []
    for index in range(1, shift_count + 1):
        start = config.run.start_utc + interval * (index - 1)
        end = config.run.start_utc + interval * index
        shifts.append(
            ShiftRecord(
                run_id=run_id,
                shift_id=generate_identifier("SHIFT", index),
                facility_id=config.facility.facility_id,
                shift_code="A" if index % 2 else "B",
                start_utc=start.isoformat(),
                end_utc=end.isoformat(),
                operating_date_local=to_facility_local(start, config.run.facility_timezone)
                .date()
                .isoformat(),
            )
        )
    return tuple(shifts)


def _generate_operators(
    config: ProjectConfig,
    run_id: str,
    zones: tuple[ZoneRecord, ...],
) -> tuple[OperatorRecord, ...]:
    roles = (
        ("SELECTOR", config.dimensions.selector_count),
        ("REPLENISHMENT", config.dimensions.replenisher_count),
        ("QA", config.dimensions.qa_operator_count),
        ("INVENTORY_CONTROL", 1),
        ("SYSTEM", 1),
    )
    operators: list[OperatorRecord] = []
    for role, count in roles:
        for role_index in range(count):
            index = len(operators) + 1
            home_zone_id = (
                zones[role_index % len(zones)].zone_id
                if role not in {"INVENTORY_CONTROL", "SYSTEM"}
                else None
            )
            operators.append(
                OperatorRecord(
                    run_id=run_id,
                    operator_id=generate_identifier("OP", index),
                    role=role,
                    home_zone_id=home_zone_id,
                    shift_code="A" if index % 2 else "B",
                    experience_months=12 + (index % 36),
                )
            )
    return tuple(operators)


def _generate_work_assignments(
    run_id: str,
    operators: tuple[OperatorRecord, ...],
    shifts: tuple[ShiftRecord, ...],
    zones: tuple[ZoneRecord, ...],
) -> tuple[WorkAssignmentRecord, ...]:
    records: list[WorkAssignmentRecord] = []
    for index, operator in enumerate(operators, start=1):
        shift = shifts[(index - 1) % len(shifts)]
        zone_id = (
            operator.home_zone_id if operator.role not in {"INVENTORY_CONTROL", "SYSTEM"} else None
        )
        records.append(
            WorkAssignmentRecord(
                run_id=run_id,
                work_assignment_id=generate_identifier("WORK", index),
                operator_id=operator.operator_id,
                shift_id=shift.shift_id,
                role=operator.role,
                zone_id=zone_id,
                start_utc=shift.start_utc,
                end_utc=shift.end_utc,
            )
        )
    return tuple(records)
