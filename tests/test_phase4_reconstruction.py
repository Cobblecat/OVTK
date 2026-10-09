from __future__ import annotations

from operational_variance_toolkit.analysis.reconstruction import (
    ReconstructionSourceData,
    build_reconstruction_tables,
    validate_reconstruction_tables,
)


def test_hand_calculated_ledger_signs_order_and_reconciliation() -> None:
    source = _hand_source()

    derived = build_reconstruction_tables(source)
    ledger = derived.tables["inventory_event_ledger"]
    reconciliation = derived.tables["inventory_reconciliation"]
    validation = validate_reconstruction_tables(source, derived)

    assert validation.passed
    assert [
        (
            row["event_sequence"],
            row["event_type"],
            row["source_line"],
            row["location_id"],
            row["quantity_delta_cases"],
            row["balance_before_cases"],
            row["balance_after_cases"],
        )
        for row in ledger
    ] == [
        (2, "PICK", "pick", "LOC-PICK", -4, 20, 16),
        (4, "REPLENISHMENT_SOURCE", "source", "LOC-RESERVE", -6, 10, 4),
        (4, "REPLENISHMENT_DESTINATION", "destination", "LOC-PICK", 6, 16, 22),
        (6, "ADJUSTMENT", "adjustment", "LOC-PICK", -2, 22, 20),
    ]
    assert not any(row["source_record_id"] == "PICK-002" for row in ledger)
    assert not any(row["source_table"] == "qa_event" for row in ledger)
    assert not any(row["source_table"] == "system_event" for row in ledger)
    assert {row["reconciliation_status"] for row in reconciliation} == {"PASS"}


def test_context_tables_use_factual_relationship_rules() -> None:
    source = _hand_source()

    derived = build_reconstruction_tables(source)
    pick_context = derived.tables["pick_context"]
    replenishment_context = derived.tables["replenishment_context"]
    qa_adjustment_context = derived.tables["qa_adjustment_context"]
    selector_exposure = derived.tables["selector_exposure"]

    first_pick = pick_context[0]
    second_pick = pick_context[1]
    assert first_pick["nearest_replenishment_task_id"] == "REPL-001"
    assert first_pick["minutes_to_nearest_replenishment_completion"] == 10.0
    assert first_pick["active_replenishment_at_pick_flag"] == 1
    assert first_pick["system_event_overlap_flag"] == 1
    assert second_pick["short_qty_cases"] == 3
    assert second_pick["reconstructed_balance_before_cases"] == 16
    assert second_pick["reconstructed_balance_after_cases"] == 16
    assert replenishment_context[0]["pick_lines_during_creation_confirmation"] == 2
    assert replenishment_context[0]["short_lines_during_creation_confirmation"] == 2
    assert qa_adjustment_context[0]["relationship_rule"] == (
        "same_item_same_location_adjustment_after_qa_within_4h"
    )
    assert qa_adjustment_context[0]["compatible_quantity_direction_flag"] == 1
    assert selector_exposure == [
        {
            "run_id": "RUN-HAND",
            "selector_id": "OP-SEL-001",
            "trips": 1,
            "pick_lines": 2,
            "eligible_pick_lines": 2,
            "requested_cases": 8,
            "picked_cases": 4,
            "short_lines": 2,
            "short_cases": 4,
            "high_velocity_pick_lines": 2,
            "replenishment_adjacent_pick_lines": 2,
            "ambient_pick_lines": 2,
            "chilled_pick_lines": 0,
            "frozen_pick_lines": 0,
            "aisles_worked": 1,
            "operating_dates_worked": 1,
            "shifts_worked": 1,
        }
    ]


def test_reconstruction_validation_reports_closing_difference() -> None:
    source = _hand_source(closing_pick_qty=21)
    derived = build_reconstruction_tables(source)

    validation = validate_reconstruction_tables(source, derived)

    assert not validation.passed
    assert any(
        "unexplained closing difference" in issue.message for issue in validation.hard_failures
    )


def _hand_source(closing_pick_qty: int = 20) -> ReconstructionSourceData:
    return ReconstructionSourceData(
        run_id="RUN-HAND",
        source_schema_version="2.0.0",
        sqlite_user_version=2,
        table_counts={},
        tables={
            "inventory_snapshot": [
                _snapshot("OPENING-SYS-PICK", "OPENING_SYSTEM", "SKU-001", "LOC-PICK", 20),
                _snapshot("OPENING-SYS-RES", "OPENING_SYSTEM", "SKU-001", "LOC-RESERVE", 10),
                _snapshot(
                    "CLOSING-SYS-PICK",
                    "CLOSING_SYSTEM",
                    "SKU-001",
                    "LOC-PICK",
                    closing_pick_qty,
                    "2026-05-04T08:00:00+00:00",
                ),
                _snapshot(
                    "CLOSING-SYS-RES",
                    "CLOSING_SYSTEM",
                    "SKU-001",
                    "LOC-RESERVE",
                    4,
                    "2026-05-04T08:00:00+00:00",
                ),
            ],
            "event_sequence_registry": [
                _registry(
                    1, "SYSTEM_EVENT", "system_event", "SYS-001", "2026-05-04T03:58:00+00:00"
                ),
                _registry(2, "PICK", "pick_event", "PICK-001", "2026-05-04T04:00:00+00:00"),
                _registry(3, "PICK", "pick_event", "PICK-002", "2026-05-04T04:05:00+00:00"),
                _registry(
                    4,
                    "REPLENISHMENT",
                    "replenishment_task",
                    "REPL-001",
                    "2026-05-04T04:10:00+00:00",
                ),
                _registry(5, "QA", "qa_event", "QA-001", "2026-05-04T04:12:00+00:00"),
                _registry(
                    6,
                    "ADJUSTMENT",
                    "inventory_adjustment",
                    "ADJ-001",
                    "2026-05-04T04:20:00+00:00",
                ),
            ],
            "trip": [
                {
                    "run_id": "RUN-HAND",
                    "trip_id": "TRIP-001",
                    "shift_id": "SHIFT-001",
                    "selector_id": "OP-SEL-001",
                    "assigned_zone_id": "ZONE-AMBIENT",
                    "assigned_zone_code": "AMBIENT",
                    "start_utc": "2026-05-04T03:45:00+00:00",
                    "end_utc": "2026-05-04T04:30:00+00:00",
                    "continuation_flag": 0,
                    "planned_pick_lines": 2,
                    "planned_cases": 8,
                    "shift_code": "A",
                    "operating_date_local": "2026-05-04",
                }
            ],
            "pick_event": [
                _pick("PICK-001", 2, 5, 4, 1, 20, 16, "2026-05-04T04:00:00+00:00"),
                _pick("PICK-002", 3, 3, 0, 3, 16, 16, "2026-05-04T04:05:00+00:00"),
            ],
            "replenishment_task": [
                {
                    "run_id": "RUN-HAND",
                    "replenishment_task_id": "REPL-001",
                    "event_sequence": 4,
                    "item_id": "SKU-001",
                    "source_location_id": "LOC-RESERVE",
                    "destination_location_id": "LOC-PICK",
                    "operator_id": "OP-REPL-001",
                    "created_utc": "2026-05-04T03:50:00+00:00",
                    "started_utc": "2026-05-04T03:55:00+00:00",
                    "confirmed_utc": "2026-05-04T04:10:00+00:00",
                    "recorded_utc": "2026-05-04T04:11:00+00:00",
                    "requested_qty_cases": 6,
                    "confirmed_qty_cases": 6,
                    "status": "CONFIRMED",
                    "delay_reason_code": None,
                }
            ],
            "qa_event": [
                {
                    "run_id": "RUN-HAND",
                    "qa_event_id": "QA-001",
                    "event_sequence": 5,
                    "item_id": "SKU-001",
                    "location_id": "LOC-PICK",
                    "handling_unit_id": None,
                    "operator_id": "OP-QA-001",
                    "event_type": "DAMAGE_FOUND",
                    "occurred_utc": "2026-05-04T04:12:00+00:00",
                    "recorded_utc": "2026-05-04T04:13:00+00:00",
                    "qty_affected_cases": 2,
                    "reason_code": "DAMAGED_CASE",
                    "disposition_code": "DISPOSE",
                }
            ],
            "inventory_adjustment": [
                {
                    "run_id": "RUN-HAND",
                    "adjustment_id": "ADJ-001",
                    "event_sequence": 6,
                    "item_id": "SKU-001",
                    "location_id": "LOC-PICK",
                    "operator_id": "OP-IC-001",
                    "effective_utc": "2026-05-04T04:20:00+00:00",
                    "recorded_utc": "2026-05-04T04:21:00+00:00",
                    "qty_delta_cases": -2,
                    "reason_code": "COUNT_CORRECTION",
                    "reference_code": "REF-001",
                }
            ],
            "system_event": [
                {
                    "run_id": "RUN-HAND",
                    "system_event_id": "SYS-001",
                    "event_sequence": 1,
                    "event_type": "RF_DELAY",
                    "zone_id": "ZONE-AMBIENT",
                    "location_id": None,
                    "equipment_area": None,
                    "start_utc": "2026-05-04T03:58:00+00:00",
                    "end_utc": "2026-05-04T04:06:00+00:00",
                    "severity_code": "LOW",
                    "recorded_utc": "2026-05-04T03:59:00+00:00",
                }
            ],
            "item": [
                {
                    "run_id": "RUN-HAND",
                    "item_id": "SKU-001",
                    "category": "Frozen Grocery",
                    "required_zone_code": "AMBIENT",
                    "case_weight_lb": 10.0,
                    "case_cube_ft3": 1.0,
                    "fragility_score": 0.7,
                    "velocity_class": "A",
                    "expected_cases_per_day": 20.0,
                }
            ],
            "location": [
                _location("LOC-PICK", "PICK", "A01", 50),
                _location("LOC-RESERVE", "RESERVE", "A01", 100),
            ],
            "zone": [
                {
                    "run_id": "RUN-HAND",
                    "zone_id": "ZONE-AMBIENT",
                    "zone_code": "AMBIENT",
                    "active_flag": 1,
                }
            ],
            "operator": [],
        },
    )


def _snapshot(
    snapshot_id: str,
    snapshot_type: str,
    item_id: str,
    location_id: str,
    qty_cases: int,
    snapshot_utc: str = "2026-05-04T03:00:00+00:00",
) -> dict[str, object]:
    return {
        "run_id": "RUN-HAND",
        "snapshot_id": snapshot_id,
        "snapshot_utc": snapshot_utc,
        "snapshot_type": snapshot_type,
        "item_id": item_id,
        "location_id": location_id,
        "handling_unit_id": None,
        "qty_cases": qty_cases,
        "source_code": "TEST",
    }


def _registry(
    event_sequence: int,
    event_type: str,
    source_table: str,
    source_id: str,
    event_utc: str,
) -> dict[str, object]:
    return {
        "run_id": "RUN-HAND",
        "event_sequence": event_sequence,
        "event_type": event_type,
        "source_table": source_table,
        "source_id": source_id,
        "event_utc": event_utc,
    }


def _pick(
    pick_event_id: str,
    event_sequence: int,
    requested: int,
    picked: int,
    short: int,
    before: int,
    after: int,
    event_utc: str,
) -> dict[str, object]:
    return {
        "run_id": "RUN-HAND",
        "pick_event_id": pick_event_id,
        "event_sequence": event_sequence,
        "trip_id": "TRIP-001",
        "selector_id": "OP-SEL-001",
        "item_id": "SKU-001",
        "pick_location_id": "LOC-PICK",
        "event_utc": event_utc,
        "recorded_utc": event_utc,
        "requested_qty_cases": requested,
        "picked_qty_cases": picked,
        "short_qty_cases": short,
        "short_reason_code": "BASELINE_ACCESS" if short else None,
        "system_qty_before_cases": before,
        "system_qty_after_cases": after,
        "eligible_pick_flag": 1,
    }


def _location(
    location_id: str, location_type: str, aisle_code: str, capacity_cases: int
) -> dict[str, object]:
    return {
        "run_id": "RUN-HAND",
        "location_id": location_id,
        "zone_id": "ZONE-AMBIENT",
        "zone_code": "AMBIENT",
        "location_type": location_type,
        "aisle_code": aisle_code,
        "equipment_area": "AREA-1",
        "capacity_cases": capacity_cases,
        "pickable_flag": 1 if location_type == "PICK" else 0,
        "active_flag": 1,
    }
