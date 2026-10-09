"""Focused Slice 2 tests for schema-3 WMS commands."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from operational_variance_toolkit.errors import DataValidationError, DuplicateCommandError
from operational_variance_toolkit.storage.database import connect_database
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.initialize import initialize_wms_foundation
from operational_variance_toolkit.wms.application.service import WmsService
from operational_variance_toolkit.wms.domain.commands import (
    AdjustInventory,
    AssignItemToLocation,
    CaptureInventorySnapshot,
    ClearLocation,
    ConfirmReplenishmentTask,
    CreateReplenishmentTask,
    CreateTrip,
    RecordPickAttempt,
    RecordQaEvent,
    RecordSystemEvent,
    StartReplenishmentTask,
    TransferInventory,
)

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


@pytest.fixture()
def wms(baseline_config_path, tmp_path):
    result = initialize_wms_foundation(
        baseline_config_path,
        tmp_path / "commands.sqlite3",
        generated_at_utc=NOW,
    )
    connection = connect_database(result.database_path)
    yield result.run_metadata.run_id, connection, WmsService(connection)
    connection.close()


def _row(connection, sql, *args):
    row = connection.execute(sql, args).fetchone()
    assert row is not None
    return row


def _command(run_id, command_id, **fields):
    values = {
        "run_id": run_id,
        "command_id": command_id,
        "event_utc": NOW,
        "recorded_utc": NOW,
    }
    values.update(fields)
    return values


def _quantity(connection, location_id):
    return _row(
        connection,
        "SELECT qty_on_hand_cases FROM inventory_master WHERE location_id = ?",
        location_id,
    )[0]


def _item_locations(connection):
    return _row(
        connection,
        """
        SELECT reserve.item_id, reserve.location_id, pick.location_id
        FROM inventory_master AS reserve
        JOIN location_master AS reserve_location
            USING(run_id, location_id)
        JOIN inventory_master AS pick
            ON pick.run_id = reserve.run_id AND pick.item_id = reserve.item_id
        JOIN location_master AS pick_location
            ON pick_location.run_id = pick.run_id
            AND pick_location.location_id = pick.location_id
        WHERE reserve_location.location_type = 'RESERVE'
            AND pick_location.location_type = 'PICK'
            AND reserve.qty_on_hand_cases >= 4
        LIMIT 1
        """,
    )


def test_pick_success_and_short_preserves_unpicked_quantity(wms):
    run_id, database, service = wms
    location_id, item_id, before = _row(
        database,
        """
        SELECT inventory.location_id, inventory.item_id, inventory.qty_on_hand_cases
        FROM inventory_master AS inventory
        JOIN location_master AS location USING(run_id, location_id)
        WHERE inventory.item_id IS NOT NULL
            AND inventory.qty_on_hand_cases >= 3
            AND location.location_type = 'PICK'
            AND location.pickable_flag = 1
        LIMIT 1
        """,
    )
    shift_id, shift_start = _row(database, "SELECT shift_id, start_utc FROM shift LIMIT 1")
    selector_id = _row(
        database, "SELECT operator_id FROM operator WHERE role = 'SELECTOR' LIMIT 1"
    )[0]
    zone_id = _row(database, "SELECT zone_id FROM zone LIMIT 1")[0]
    start = datetime.fromisoformat(shift_start.replace("Z", "+00:00")) + timedelta(minutes=1)
    trip = service.create_trip(
        CreateTrip(
            **_command(
                run_id,
                "trip-1",
                event_utc=start,
                shift_id=shift_id,
                selector_id=selector_id,
                assigned_zone_id=zone_id,
                end_utc=start + timedelta(hours=1),
                planned_pick_lines=1,
                planned_cases=2,
            )
        )
    )

    service.record_pick(
        RecordPickAttempt(
            **_command(
                run_id,
                "pick-1",
                event_utc=start + timedelta(minutes=2),
                trip_id=trip.result_record_id,
                selector_id=selector_id,
                item_id=item_id,
                location_id=location_id,
                requested_qty_cases=2,
                picked_qty_cases=1,
                short_qty_cases=1,
                short_reason_code="NO_STOCK",
            )
        )
    )
    assert _quantity(database, location_id) == before - 1

    service.record_pick(
        RecordPickAttempt(
            **_command(
                run_id,
                "pick-2",
                event_utc=start + timedelta(minutes=3),
                trip_id=trip.result_record_id,
                selector_id=selector_id,
                item_id=item_id,
                location_id=location_id,
                requested_qty_cases=2,
                picked_qty_cases=0,
                short_qty_cases=2,
                short_reason_code="NO_STOCK",
            )
        )
    )
    assert _quantity(database, location_id) == before - 1
    assert (
        database.execute(
            "SELECT COUNT(*) FROM inventory_transaction WHERE command_id = 'pick-2'"
        ).fetchone()[0]
        == 0
    )

    service.record_pick(
        RecordPickAttempt(
            **_command(
                run_id,
                "pick-3",
                event_utc=start + timedelta(minutes=4),
                trip_id=trip.result_record_id,
                selector_id=selector_id,
                item_id=item_id,
                location_id=location_id,
                requested_qty_cases=1,
                picked_qty_cases=1,
                short_qty_cases=0,
                short_reason_code=None,
            )
        )
    )
    assert _quantity(database, location_id) == before - 2


def test_transfer_replenishment_adjustment_and_nonmovement_events(wms):
    run_id, database, service = wms
    item_id, source_id, destination_id = _item_locations(database)
    replenisher_id = _row(
        database,
        "SELECT operator_id FROM operator WHERE role = 'REPLENISHMENT' LIMIT 1",
    )[0]
    source_before = _quantity(database, source_id)
    destination_before = _quantity(database, destination_id)

    moved = service.transfer_inventory(
        TransferInventory(
            **_command(
                run_id,
                "move-1",
                item_id=item_id,
                source_location_id=source_id,
                destination_location_id=destination_id,
                qty_cases=2,
            )
        )
    )
    assert len(moved.transaction_ids) == 2
    assert _quantity(database, source_id) == source_before - 2
    assert _quantity(database, destination_id) == destination_before + 2
    deltas = database.execute(
        """
        SELECT qty_delta_cases
        FROM inventory_transaction
        WHERE command_id = 'move-1'
        ORDER BY line_number
        """
    ).fetchall()
    assert [row[0] for row in deltas] == [-2, 2]

    task = service.create_replenishment(
        CreateReplenishmentTask(
            **_command(
                run_id,
                "repl-create",
                item_id=item_id,
                source_location_id=source_id,
                destination_location_id=destination_id,
                requested_qty_cases=1,
                operator_id=replenisher_id,
            )
        )
    )
    service.start_replenishment(
        StartReplenishmentTask(
            **_command(
                run_id,
                "repl-start",
                replenishment_task_id=task.result_record_id,
                operator_id=replenisher_id,
            )
        )
    )
    confirmed = service.confirm_replenishment(
        ConfirmReplenishmentTask(
            **_command(
                run_id,
                "repl-confirm",
                replenishment_task_id=task.result_record_id,
                confirmed_qty_cases=1,
                operator_id=replenisher_id,
            )
        )
    )
    assert len(confirmed.transaction_ids) == 2

    control_id = _row(
        database,
        "SELECT operator_id FROM operator WHERE role = 'INVENTORY_CONTROL' LIMIT 1",
    )[0]
    adjustment = service.adjust_inventory(
        AdjustInventory(
            **_command(
                run_id,
                "adj-1",
                item_id=item_id,
                location_id=destination_id,
                operator_id=control_id,
                qty_delta_cases=1,
                reason_code="COUNT_CORRECTION",
            )
        )
    )
    quantity_after_movements = _quantity(database, destination_id)
    transaction_count = database.execute("SELECT COUNT(*) FROM inventory_transaction").fetchone()[0]

    qa_id = _row(database, "SELECT operator_id FROM operator WHERE role = 'QA' LIMIT 1")[0]
    service.record_qa_event(
        RecordQaEvent(
            **_command(
                run_id,
                "qa-1",
                item_id=item_id,
                location_id=destination_id,
                operator_id=qa_id,
                event_type="COUNT_VERIFICATION",
                qty_affected_cases=1,
                reason_code="CHECK",
                disposition_code="NO_ACTION",
            )
        )
    )
    service.record_system_event(
        RecordSystemEvent(
            **_command(
                run_id,
                "sys-1",
                event_type="SYSTEM_LAG",
                end_utc=NOW + timedelta(minutes=1),
                severity_code="LOW",
                location_id=destination_id,
            )
        )
    )
    snapshot = service.capture_snapshot(
        CaptureInventorySnapshot(
            **_command(
                run_id,
                "snap-1",
                snapshot_type="SHIFT_END",
                source_code="TEST",
            )
        )
    )
    assert _quantity(database, destination_id) == quantity_after_movements
    assert (
        database.execute("SELECT COUNT(*) FROM inventory_transaction").fetchone()[0]
        == transaction_count
    )
    assert (
        database.execute(
            """
        SELECT COUNT(*)
        FROM inventory_snapshot AS snapshot
        JOIN inventory_master AS live USING(run_id, location_id)
        WHERE snapshot.snapshot_batch_id = ?
            AND (snapshot.item_id IS NOT live.item_id
                OR snapshot.qty_on_hand_cases != live.qty_on_hand_cases
                OR snapshot.code_date IS NOT live.code_date)
        """,
            (snapshot.result_record_id,),
        ).fetchone()[0]
        == 0
    )
    source_reference = database.execute(
        """
        SELECT source_record_type, source_record_id
        FROM inventory_transaction
        WHERE command_id = 'adj-1'
        """
    ).fetchone()
    assert tuple(source_reference) == ("ADJUSTMENT", adjustment.result_record_id)


def test_transfer_clears_depleted_reserve_assignment(wms):
    run_id, database, service = wms
    source = _row(
        database,
        """
        SELECT inventory.item_id, inventory.location_id, inventory.qty_on_hand_cases,
            location.zone_id
        FROM inventory_master AS inventory
        JOIN location_master AS location USING(run_id, location_id)
        WHERE location.location_type = 'RESERVE'
            AND inventory.item_id IS NOT NULL
            AND inventory.qty_on_hand_cases > 0
        ORDER BY inventory.location_id
        LIMIT 1
        """,
    )
    destination_id = _row(
        database,
        """
        SELECT inventory.location_id
        FROM inventory_master AS inventory
        JOIN location_master AS location USING(run_id, location_id)
        WHERE location.location_type = 'RESERVE'
            AND location.zone_id = ?
            AND inventory.item_id IS NULL
            AND inventory.qty_on_hand_cases = 0
        ORDER BY inventory.location_id
        LIMIT 1
        """,
        source[3],
    )[0]

    service.transfer_inventory(
        TransferInventory(
            **_command(
                run_id,
                "deplete-reserve",
                item_id=source[0],
                source_location_id=source[1],
                destination_location_id=destination_id,
                qty_cases=source[2],
            )
        )
    )

    depleted = _row(
        database,
        "SELECT item_id, qty_on_hand_cases, code_date FROM inventory_master WHERE location_id = ?",
        source[1],
    )
    assert tuple(depleted) == (None, 0, None)


def test_duplicate_invalid_commands_and_trigger_rollback(wms):
    run_id, database, service = wms
    item_id, location_id, _ = _row(
        database,
        """
        SELECT item_id, location_id, qty_on_hand_cases
        FROM inventory_master
        WHERE item_id IS NOT NULL AND qty_on_hand_cases > 0
        LIMIT 1
        """,
    )
    control_id = _row(
        database,
        "SELECT operator_id FROM operator WHERE role = 'INVENTORY_CONTROL' LIMIT 1",
    )[0]
    command = AdjustInventory(
        **_command(
            run_id,
            "dup-1",
            item_id=item_id,
            location_id=location_id,
            operator_id=control_id,
            qty_delta_cases=1,
            reason_code="COUNT_CORRECTION",
        )
    )
    service.adjust_inventory(command)
    after_first = _quantity(database, location_id)
    with pytest.raises(DuplicateCommandError):
        service.adjust_inventory(command)
    assert _quantity(database, location_id) == after_first

    with pytest.raises(DataValidationError):
        service.adjust_inventory(
            AdjustInventory(
                **_command(
                    run_id,
                    "bad-negative",
                    item_id=item_id,
                    location_id=location_id,
                    operator_id=control_id,
                    qty_delta_cases=-999999,
                    reason_code="COUNT_CORRECTION",
                )
            )
        )
    with pytest.raises(DataValidationError):
        service.transfer_inventory(
            TransferInventory(
                **_command(
                    run_id,
                    "bad-item",
                    item_id="NO-SUCH",
                    source_location_id=location_id,
                    destination_location_id="NO-SUCH-LOCATION",
                    qty_cases=1,
                )
            )
        )
    selector_id = _row(
        database, "SELECT operator_id FROM operator WHERE role = 'SELECTOR' LIMIT 1"
    )[0]
    with pytest.raises(DataValidationError, match="requires role"):
        service.adjust_inventory(
            AdjustInventory(
                **_command(
                    run_id,
                    "bad-role",
                    item_id=item_id,
                    location_id=location_id,
                    operator_id=selector_id,
                    qty_delta_cases=1,
                    reason_code="COUNT_CORRECTION",
                )
            )
        )
    with pytest.raises(DataValidationError, match="timezone-aware"):
        service.adjust_inventory(
            AdjustInventory(
                **_command(
                    run_id,
                    "bad-time",
                    event_utc=datetime(2026, 8, 2, 12),
                    recorded_utc=datetime(2026, 8, 2, 12),
                    item_id=item_id,
                    location_id=location_id,
                    operator_id=control_id,
                    qty_delta_cases=1,
                    reason_code="COUNT_CORRECTION",
                )
            )
        )

    transaction_count = database.execute("SELECT COUNT(*) FROM inventory_transaction").fetchone()[0]
    command_count = database.execute("SELECT COUNT(*) FROM wms_command").fetchone()[0]
    database.execute(
        """
        CREATE TRIGGER fail_wms_transaction
        AFTER INSERT ON inventory_transaction
        BEGIN
            SELECT RAISE(ABORT, 'test rollback');
        END
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        service.adjust_inventory(
            AdjustInventory(
                **_command(
                    run_id,
                    "trigger-fail",
                    item_id=item_id,
                    location_id=location_id,
                    operator_id=control_id,
                    qty_delta_cases=1,
                    reason_code="COUNT_CORRECTION",
                )
            )
        )
    assert _quantity(database, location_id) == after_first
    assert (
        database.execute("SELECT COUNT(*) FROM inventory_transaction").fetchone()[0]
        == transaction_count
    )
    assert database.execute("SELECT COUNT(*) FROM wms_command").fetchone()[0] == command_count


def test_assignment_rules_and_transaction_replay_match_live_balances(wms):
    run_id, database, service = wms
    item_id, location_id, quantity = _row(
        database,
        """
        SELECT inventory.item_id, inventory.location_id, inventory.qty_on_hand_cases
        FROM inventory_master AS inventory
        JOIN location_master AS location USING(run_id, location_id)
        WHERE location.location_type = 'RESERVE' AND inventory.qty_on_hand_cases > 0
        LIMIT 1
        """,
    )
    control_id = _row(
        database,
        "SELECT operator_id FROM operator WHERE role = 'INVENTORY_CONTROL' LIMIT 1",
    )[0]
    service.adjust_inventory(
        AdjustInventory(
            **_command(
                run_id,
                "empty-reserve",
                item_id=item_id,
                location_id=location_id,
                operator_id=control_id,
                qty_delta_cases=-quantity,
                reason_code="COUNT_CORRECTION",
            )
        )
    )
    service.clear_location(
        ClearLocation(**_command(run_id, "clear-location", location_id=location_id))
    )
    service.assign_item(
        AssignItemToLocation(
            **_command(
                run_id,
                "assign-location",
                location_id=location_id,
                item_id=item_id,
                code_date=date(2026, 9, 1),
            )
        )
    )
    other_item_id = _row(
        database,
        """
        SELECT candidate.item_id
        FROM item_master AS candidate
        JOIN item_master AS current
            ON current.run_id = candidate.run_id
            AND current.required_zone_code = candidate.required_zone_code
        WHERE current.item_id = ? AND candidate.item_id != current.item_id
        LIMIT 1
        """,
        item_id,
    )[0]
    with pytest.raises(DataValidationError, match="explicitly cleared"):
        service.assign_item(
            AssignItemToLocation(
                **_command(
                    run_id,
                    "invalid-reassignment",
                    location_id=location_id,
                    item_id=other_item_id,
                    code_date=date(2026, 9, 1),
                )
            )
        )
    pick_location_id = _row(
        database,
        """
        SELECT inventory.location_id
        FROM inventory_master AS inventory
        JOIN location_master AS location USING(run_id, location_id)
        WHERE location.location_type = 'PICK'
        LIMIT 1
        """,
    )[0]
    with pytest.raises(DataValidationError, match="cannot be cleared"):
        service.clear_location(
            ClearLocation(**_command(run_id, "invalid-pick-clear", location_id=pick_location_id))
        )

    differences = database.execute(
        """
        WITH opening AS (
            SELECT location_id, qty_on_hand_cases
            FROM inventory_snapshot
            WHERE snapshot_type = 'OPENING_SYSTEM'
        ),
        movement AS (
            SELECT location_id, SUM(qty_delta_cases) AS qty_delta_cases
            FROM inventory_transaction
            GROUP BY location_id
        )
        SELECT COUNT(*)
        FROM inventory_master AS live
        JOIN opening USING(location_id)
        LEFT JOIN movement USING(location_id)
        WHERE live.qty_on_hand_cases
            != opening.qty_on_hand_cases + COALESCE(movement.qty_delta_cases, 0)
        """
    ).fetchone()[0]
    assert differences == 0
    assert validate_wms_dataset(database).passed


def test_replenishment_confirmation_rolls_back_between_audit_rows(wms):
    run_id, database, service = wms
    item_id, source_id, destination_id = _item_locations(database)
    operator_id = _row(
        database,
        "SELECT operator_id FROM operator WHERE role = 'REPLENISHMENT' LIMIT 1",
    )[0]
    task = service.create_replenishment(
        CreateReplenishmentTask(
            **_command(
                run_id,
                "rollback-create",
                item_id=item_id,
                source_location_id=source_id,
                destination_location_id=destination_id,
                requested_qty_cases=1,
                operator_id=operator_id,
            )
        )
    )
    service.start_replenishment(
        StartReplenishmentTask(
            **_command(
                run_id,
                "rollback-start",
                replenishment_task_id=task.result_record_id,
                operator_id=operator_id,
            )
        )
    )
    source_before = _quantity(database, source_id)
    destination_before = _quantity(database, destination_id)
    transaction_count = database.execute("SELECT COUNT(*) FROM inventory_transaction").fetchone()[0]
    event_count = database.execute("SELECT COUNT(*) FROM event_sequence_registry").fetchone()[0]
    database.execute(
        """
        CREATE TRIGGER fail_second_transfer_line
        BEFORE INSERT ON inventory_transaction
        WHEN NEW.line_number = 2
        BEGIN
            SELECT RAISE(ABORT, 'test paired-row rollback');
        END
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        service.confirm_replenishment(
            ConfirmReplenishmentTask(
                **_command(
                    run_id,
                    "rollback-confirm",
                    replenishment_task_id=task.result_record_id,
                    confirmed_qty_cases=1,
                    operator_id=operator_id,
                )
            )
        )

    assert _quantity(database, source_id) == source_before
    assert _quantity(database, destination_id) == destination_before
    assert (
        database.execute("SELECT COUNT(*) FROM inventory_transaction").fetchone()[0]
        == transaction_count
    )
    assert (
        database.execute("SELECT COUNT(*) FROM event_sequence_registry").fetchone()[0]
        == event_count
    )
    assert (
        database.execute(
            "SELECT status FROM replenishment_task WHERE replenishment_task_id = ?",
            (task.result_record_id,),
        ).fetchone()[0]
        == "STARTED"
    )
    assert (
        database.execute(
            "SELECT COUNT(*) FROM wms_command WHERE command_id = 'rollback-confirm'"
        ).fetchone()[0]
        == 0
    )


def test_wms_package_has_no_simulator_scenario_or_analysis_imports():
    package = Path(__file__).parents[1] / "src" / "operational_variance_toolkit" / "wms"
    forbidden = (
        "operational_variance_toolkit.analysis",
        "operational_variance_toolkit.scenario",
        "operational_variance_toolkit.simulation",
        "operational_variance_toolkit.ground_truth",
    )
    sources = "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py"))
    assert not any(module in sources for module in forbidden)
