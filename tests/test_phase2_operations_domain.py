from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from operational_variance_toolkit.domain.operations import (
    SimulatorInventoryState,
    StateTransitionProcessor,
)
from operational_variance_toolkit.errors import DataValidationError


def test_state_processor_applies_pick_before_after_quantities() -> None:
    state = SimulatorInventoryState(
        run_id="RUN-TEST",
        physical={("ITEM-001", "LOC-PICK"): 5},
        system={("ITEM-001", "LOC-PICK"): 5},
    )
    processor = StateTransitionProcessor(state)

    record = processor.apply_pick(
        pick_event_id="PICK-0001",
        trip_id="TRIP-0001",
        selector_id="OP-0001",
        item_id="ITEM-001",
        location_id="LOC-PICK",
        event_utc=datetime(2026, 5, 4, 8, tzinfo=UTC),
        requested_qty_cases=3,
    )

    assert record.event_sequence == 1
    assert record.system_qty_before_cases == 5
    assert record.system_qty_after_cases == 2
    assert record.picked_qty_cases == 3
    assert record.short_qty_cases == 0
    assert state.physical[("ITEM-001", "LOC-PICK")] == 2
    assert state.system[("ITEM-001", "LOC-PICK")] == 2


def test_state_processor_records_legitimate_short_without_negative_inventory() -> None:
    state = SimulatorInventoryState(
        run_id="RUN-TEST",
        physical={("ITEM-001", "LOC-PICK"): 1},
        system={("ITEM-001", "LOC-PICK"): 1},
    )
    processor = StateTransitionProcessor(state)

    record = processor.apply_pick(
        pick_event_id="PICK-0001",
        trip_id="TRIP-0001",
        selector_id="OP-0001",
        item_id="ITEM-001",
        location_id="LOC-PICK",
        event_utc=datetime(2026, 5, 4, 8, tzinfo=UTC),
        requested_qty_cases=3,
    )

    assert record.picked_qty_cases == 1
    assert record.short_qty_cases == 2
    assert record.short_reason_code == "BASELINE_ACCESS"
    assert state.physical[("ITEM-001", "LOC-PICK")] == 0
    assert state.system[("ITEM-001", "LOC-PICK")] == 0


def test_state_processor_replenishment_conserves_quantity() -> None:
    state = SimulatorInventoryState(
        run_id="RUN-TEST",
        physical={("ITEM-001", "LOC-RESERVE"): 10, ("ITEM-001", "LOC-PICK"): 1},
        system={("ITEM-001", "LOC-RESERVE"): 10, ("ITEM-001", "LOC-PICK"): 1},
    )
    processor = StateTransitionProcessor(state)

    record = processor.apply_replenishment(
        replenishment_task_id="REPL-0001",
        item_id="ITEM-001",
        source_location_id="LOC-RESERVE",
        destination_location_id="LOC-PICK",
        operator_id="OP-0002",
        created_utc=datetime(2026, 5, 4, 8, tzinfo=UTC),
        requested_qty_cases=6,
    )

    assert record.event_sequence == 1
    assert record.status == "CONFIRMED"
    assert record.confirmed_qty_cases == 6
    assert state.physical[("ITEM-001", "LOC-RESERVE")] == 4
    assert state.physical[("ITEM-001", "LOC-PICK")] == 7
    assert state.system == state.physical


def test_state_processor_rejects_invalid_adjustment() -> None:
    state = SimulatorInventoryState(
        run_id="RUN-TEST",
        physical={("ITEM-001", "LOC-PICK"): 0},
        system={("ITEM-001", "LOC-PICK"): 0},
    )
    processor = StateTransitionProcessor(state)

    with pytest.raises(DataValidationError):
        processor.apply_adjustment(
            adjustment_id="ADJ-0001",
            item_id="ITEM-001",
            location_id="LOC-PICK",
            operator_id=None,
            effective_utc=datetime(2026, 5, 4, 8, tzinfo=UTC) + timedelta(minutes=1),
            qty_delta_cases=-1,
            reason_code="COUNT_CORRECTION",
        )
