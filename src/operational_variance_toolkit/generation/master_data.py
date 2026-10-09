"""Deterministic master-data generation for Phase 1."""

from __future__ import annotations

import sqlite3
from typing import Any

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.domain.identifiers import (
    generate_code_identifier,
    generate_identifier,
    generate_identifier_sequence,
)
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.generation.random_source import create_named_random_streams


def generate_master_data(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    run_id: str,
) -> dict[str, int]:
    """Generate deterministic master data rows for the supplied run."""

    streams = create_named_random_streams(config.run.seed)

    _insert_zones(connection, config, run_id)
    _insert_locations(connection, config, run_id)
    _insert_items(connection, config, run_id, streams["master_items"])
    _insert_operators(connection, config, run_id, streams["operators"])
    _insert_shifts(connection, config, run_id, streams["schedules"])
    _insert_slot_assignments(connection, config, run_id)
    _insert_work_assignments(connection, config, run_id)

    return {
        "zone": config.dimensions.zone_count,
        "location": _table_count(connection, run_id, "location"),
        "item": config.dimensions.item_count,
        "operator": (
            config.dimensions.selector_count
            + config.dimensions.replenisher_count
            + config.dimensions.qa_operator_count
            + 1
        ),
        "shift": config.dimensions.shift_count,
        "slot_assignment": config.dimensions.item_count,
        "work_assignment": (
            config.dimensions.selector_count
            + config.dimensions.replenisher_count
            + config.dimensions.qa_operator_count
            + 1
        ),
    }


def _insert_zones(connection: sqlite3.Connection, config: ProjectConfig, run_id: str) -> None:
    for zone_code in _zone_codes(config):
        zone_id = generate_code_identifier("ZONE", zone_code)
        connection.execute(
            """
            INSERT INTO zone(
                run_id,
                zone_id,
                facility_id,
                zone_code,
                active_flag
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, zone_id, config.facility.facility_id, zone_code, 1),
        )


def _insert_locations_for_zone(
    connection: sqlite3.Connection,
    run_id: str,
    zone_id: str,
    zone_code: str,
    zone_index: int,
    location_count: int,
) -> None:
    for location_type, offset, capacity_cases, capacity_pallets, level_number in (
        ("PICK", 0, 24, 1, 1),
        ("RESERVE", 5000, 48, 2, 2),
    ):
        for location_index in range(1, location_count + 1):
            aisle_index = ((location_index - 1) // 8) + 1
            bay_index = ((location_index - 1) % 8) + 1
            location_id = generate_identifier(
                "LOC",
                zone_index * 10000 + offset + location_index,
                width=5,
            )
            connection.execute(
                """
                INSERT INTO location(
                    run_id,
                    location_id,
                    zone_id,
                    location_type,
                    aisle_code,
                    bay_number,
                    level_number,
                    position_number,
                    equipment_area,
                    capacity_cases,
                    capacity_pallets,
                    pickable_flag,
                    active_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    location_id,
                    zone_id,
                    location_type,
                    f"A{aisle_index}",
                    bay_index,
                    level_number,
                    1,
                    f"{zone_code.lower()}-area",
                    capacity_cases,
                    capacity_pallets,
                    1 if location_type == "PICK" else 0,
                    1,
                ),
            )


def _insert_locations(connection: sqlite3.Connection, config: ProjectConfig, run_id: str) -> None:
    item_counts_by_zone = _item_counts_by_zone(config)
    zone_rows = connection.execute(
        "SELECT zone_id, zone_code FROM zone WHERE run_id = ? ORDER BY zone_id",
        (run_id,),
    ).fetchall()
    for zone_index, zone_row in enumerate(zone_rows, start=1):
        zone_id = zone_row[0]
        zone_code = zone_row[1]
        location_count = max(1, item_counts_by_zone[zone_code])
        _insert_locations_for_zone(
            connection, run_id, zone_id, zone_code, zone_index, location_count
        )


def _insert_items(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    run_id: str,
    rng: Any,
) -> None:
    item_ids = generate_identifier_sequence("ITEM", config.dimensions.item_count)
    zone_codes = _zone_codes(config)
    for index, item_id in enumerate(item_ids, start=1):
        zone_code = zone_codes[(index - 1) % len(zone_codes)]
        connection.execute(
            """
            INSERT INTO item(
                run_id,
                item_id,
                item_description,
                category,
                required_zone_code,
                cases_per_pallet,
                case_weight_lb,
                case_cube_ft3,
                fragility_score,
                shelf_life_days,
                velocity_class,
                expected_cases_per_day,
                active_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                item_id,
                f"Synthetic item {index}",
                f"Category {((index - 1) % 8) + 1}",
                zone_code,
                8 + (index % 3),
                20.0 + (index % 5),
                2.0 + (index % 4),
                round(rng.random(), 2),
                30 + (index % 10),
                "A" if index <= 32 else "B" if index <= 64 else "C",
                float(8 + (index % 6)),
                1,
            ),
        )


def _insert_operators(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    run_id: str,
    rng: Any,
) -> None:
    operator_ids: list[str] = []
    roles = [
        ("SELECTOR", config.dimensions.selector_count),
        ("REPLENISHMENT", config.dimensions.replenisher_count),
        ("QA", config.dimensions.qa_operator_count),
        ("INVENTORY_CONTROL", 1),
    ]
    for role, count in roles:
        for index in range(1, count + 1):
            operator_id = generate_identifier("OP", len(operator_ids) + 1)
            operator_ids.append(operator_id)
            connection.execute(
                """
                INSERT INTO operator(
                    run_id,
                    operator_id,
                    role,
                    home_zone_id,
                    shift_code,
                    experience_months,
                    active_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    operator_id,
                    role,
                    None,
                    "A" if rng.random() < 0.5 else "B",
                    12 + int(rng.integers(0, 24)),
                    1,
                ),
            )


def _insert_shifts(
    connection: sqlite3.Connection, config: ProjectConfig, run_id: str, rng: Any
) -> None:
    for index in range(1, config.dimensions.shift_count + 1):
        shift_id = generate_identifier("SHIFT", index)
        start_utc = config.run.start_utc
        end_utc = config.run.end_utc
        connection.execute(
            """
            INSERT INTO shift(
                run_id,
                shift_id,
                facility_id,
                shift_code,
                start_utc,
                end_utc,
                operating_date_local
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                shift_id,
                config.facility.facility_id,
                "A" if rng.random() < 0.5 else "B",
                start_utc.isoformat(),
                end_utc.isoformat(),
                start_utc.date().isoformat(),
            ),
        )


def _insert_slot_assignments(
    connection: sqlite3.Connection, config: ProjectConfig, run_id: str
) -> None:
    item_rows = connection.execute(
        "SELECT item_id, required_zone_code FROM item WHERE run_id = ? ORDER BY item_id",
        (run_id,),
    ).fetchall()
    location_rows = connection.execute(
        "SELECT z.zone_code, l.location_id, l.capacity_cases "
        "FROM location AS l "
        "JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id "
        "WHERE l.run_id = ? AND l.pickable_flag = 1 "
        "ORDER BY z.zone_code, l.location_id",
        (run_id,),
    ).fetchall()
    locations_by_zone: dict[str, list[tuple[str, int]]] = {}
    for zone_code, location_id, capacity_cases in location_rows:
        locations_by_zone.setdefault(zone_code, []).append((location_id, int(capacity_cases)))

    used_locations_by_zone = {zone_code: 0 for zone_code in locations_by_zone}

    for index, item_row in enumerate(item_rows, start=1):
        item_id = item_row[0]
        zone_code = item_row[1]
        zone_locations = locations_by_zone.get(zone_code, [])
        location_offset = used_locations_by_zone.get(zone_code, 0)
        if location_offset >= len(zone_locations):
            raise DataValidationError(f"No available pick location for item zone {zone_code}")
        pick_location_id, capacity_cases = zone_locations[location_offset]
        used_locations_by_zone[zone_code] = location_offset + 1
        assignment_id = generate_identifier("ASSIGN", index)
        target_cases = min(12 + (index % 4), capacity_cases)
        maximum_cases = min(20, capacity_cases)
        connection.execute(
            """
            INSERT INTO slot_assignment(
                run_id,
                assignment_id,
                item_id,
                pick_location_id,
                effective_start_utc,
                effective_end_utc,
                reorder_trigger_cases,
                target_cases,
                minimum_cases,
                maximum_cases,
                priority_rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                assignment_id,
                item_id,
                pick_location_id,
                config.run.start_utc.isoformat(),
                None,
                2,
                target_cases,
                2,
                maximum_cases,
                index,
            ),
        )


def _insert_work_assignments(
    connection: sqlite3.Connection, config: ProjectConfig, run_id: str
) -> None:
    operator_ids = connection.execute(
        "SELECT operator_id FROM operator WHERE run_id = ? ORDER BY operator_id",
        (run_id,),
    ).fetchall()
    shift_ids = connection.execute(
        "SELECT shift_id FROM shift WHERE run_id = ? ORDER BY shift_id",
        (run_id,),
    ).fetchall()
    for index, operator_row in enumerate(operator_ids, start=1):
        operator_id = operator_row[0]
        shift_id = shift_ids[(index - 1) % len(shift_ids)][0]
        connection.execute(
            """
            INSERT INTO work_assignment(
                run_id,
                work_assignment_id,
                operator_id,
                shift_id,
                role,
                zone_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                generate_identifier("WORK", index),
                operator_id,
                shift_id,
                connection.execute(
                    "SELECT role FROM operator WHERE run_id = ? AND operator_id = ?",
                    (run_id, operator_id),
                ).fetchone()[0],
                None,
            ),
        )


def _zone_codes(config: ProjectConfig) -> list[str]:
    return ["FROZEN", "CHILLED", "AMBIENT"][: config.dimensions.zone_count]


def _item_counts_by_zone(config: ProjectConfig) -> dict[str, int]:
    zone_codes = _zone_codes(config)
    counts = {zone_code: 0 for zone_code in zone_codes}
    for index in range(config.dimensions.item_count):
        counts[zone_codes[index % len(zone_codes)]] += 1
    return counts


def _table_count(connection: sqlite3.Connection, run_id: str, table_name: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE run_id = ?", (run_id,)
    ).fetchone()
    return int(row[0])
