"""Independent atomic command service for the schema-3 WMS."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

from operational_variance_toolkit.errors import (
    DataValidationError,
    DuplicateCommandError,
)
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
    WmsCommand,
    WmsCommandResult,
    command_payload_hash,
)
from operational_variance_toolkit.wms.domain.inventory import (
    InventoryMasterRecord,
    calculate_location_maximum_cases,
)
from operational_variance_toolkit.wms.domain.records import (
    EventSequenceRecord,
    InventoryAdjustmentRecord,
    InventoryPosition,
    InventoryTransactionRecord,
    PickEventRecord,
    QaEventRecord,
    ReplenishmentTaskRecord,
    ReplenishmentTaskState,
    SnapshotLineRecord,
    SystemEventRecord,
    TripRecord,
)
from operational_variance_toolkit.wms.storage.commands import WmsCommandRepository

_ADJUSTMENT_REASONS = {
    "COUNT_CORRECTION",
    "DAMAGE",
    "FOUND_PRODUCT",
    "RECEIVING_VARIANCE",
    "TRANSACTION_CORRECTION",
    "OTHER",
}
_QA_EVENT_TYPES = {
    "DAMAGE_FOUND",
    "HOLD_PLACED",
    "RESTACK",
    "RELEASED",
    "DISPOSED",
    "COUNT_VERIFICATION",
}
_QA_DISPOSITIONS = {
    "NO_ACTION",
    "HOLD",
    "RESTACK",
    "RETURN_TO_STOCK",
    "DISPOSE",
    "RELEASE",
}
_SYSTEM_EVENT_TYPES = {
    "SCANNER_INTERRUPTION",
    "SYSTEM_LAG",
    "EQUIPMENT_DELAY",
    "BLOCKED_LOCATION",
    "NETWORK_INTERRUPTION",
}
_SNAPSHOT_TYPES = {
    "OPENING_SYSTEM",
    "CLOSING_SYSTEM",
    "SHIFT_END",
    "CYCLE_COUNT",
    "VERIFIED_COUNT",
}


class WmsService:
    """Execute public WMS commands without simulator or scenario dependencies."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._repository = WmsCommandRepository(connection)

    def create_trip(self, command: CreateTrip) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            self._require_role(command.run_id, command.selector_id, {"SELECTOR"})
            shift = self._repository.shift_state(command.run_id, command.shift_id)
            if shift is None:
                raise DataValidationError(f"Unknown shift: {command.shift_id}")
            if not self._repository.zone_exists(command.run_id, command.assigned_zone_id):
                raise DataValidationError(f"Unknown active zone: {command.assigned_zone_id}")
            self._require_aware(command.end_utc, "Trip end")
            if command.event_utc >= command.end_utc:
                raise DataValidationError("Trip start must be before trip end")
            shift_start = _parse_utc(shift.start_utc)
            shift_end = _parse_utc(shift.end_utc)
            if not shift_start <= command.event_utc < command.end_utc:
                raise DataValidationError("Trip must start inside its shift")
            if command.end_utc > shift_end:
                raise DataValidationError("Trip must end inside its shift")
            if command.planned_pick_lines <= 0 or command.planned_cases <= 0:
                raise DataValidationError("Trip plans must be positive")
            if command.continuation_flag not in {0, 1}:
                raise DataValidationError("continuation_flag must be zero or one")
            trip_id = _record_id("TRIP", sequence)
            self._insert_event(command, sequence, "TRIP", trip_id)
            self._repository.insert_trip(
                TripRecord(
                    run_id=command.run_id,
                    trip_id=trip_id,
                    shift_id=command.shift_id,
                    selector_id=command.selector_id,
                    assigned_zone_id=command.assigned_zone_id,
                    start_utc=command.event_utc,
                    end_utc=command.end_utc,
                    continuation_flag=command.continuation_flag,
                    planned_pick_lines=command.planned_pick_lines,
                    planned_cases=command.planned_cases,
                )
            )
            return self._accept(command, sequence, "TRIP", trip_id)

    def assign_item(self, command: AssignItemToLocation) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            position = self._require_position(command.run_id, command.location_id)
            item_zone, cases_per_pallet = self._require_item(command.run_id, command.item_id)
            self._require_inventory_location(position)
            if position.qty_on_hand_cases != 0:
                raise DataValidationError("Location must be empty before assignment")
            if position.item_id not in {None, command.item_id}:
                raise DataValidationError("Location must be explicitly cleared before reassignment")
            if position.zone_code != item_zone:
                raise DataValidationError("Item storage zone does not match location zone")
            controls = self._assignment_controls(command, position, cases_per_pallet)
            transaction_id = _transaction_id(sequence, 1)
            assignment_id = _record_id("ASSIGN", sequence)
            self._insert_event(command, sequence, "ASSIGNMENT", assignment_id)
            self._repository.insert_inventory_transaction(
                InventoryTransactionRecord(
                    run_id=command.run_id,
                    transaction_id=transaction_id,
                    transaction_group_id=_transaction_group_id(sequence),
                    command_id=command.command_id,
                    event_sequence=sequence,
                    line_number=1,
                    transaction_type="ASSIGNMENT",
                    location_id=command.location_id,
                    related_location_id=None,
                    item_id=command.item_id,
                    qty_delta_cases=0,
                    balance_before_cases=0,
                    balance_after_cases=0,
                    operator_id=None,
                    event_utc=command.event_utc,
                    recorded_utc=command.recorded_utc,
                    reason_code="EXPLICIT_ASSIGNMENT",
                    source_record_type="ASSIGNMENT",
                    source_record_id=assignment_id,
                )
            )
            self._repository.update_inventory(
                InventoryMasterRecord(
                    run_id=command.run_id,
                    location_id=command.location_id,
                    item_id=command.item_id,
                    qty_on_hand_cases=0,
                    code_date=command.code_date.isoformat() if command.code_date else None,
                    reorder_trigger_cases=controls[1],
                    minimum_qty_cases=controls[0],
                    target_qty_cases=controls[2],
                    maximum_qty_cases=controls[3],
                    last_transaction_id=transaction_id,
                    last_updated_utc=_stored_utc(command.recorded_utc),
                )
            )
            return self._accept(
                command,
                sequence,
                "ASSIGNMENT",
                assignment_id,
                (transaction_id,),
            )

    def clear_location(self, command: ClearLocation) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            position = self._require_position(command.run_id, command.location_id)
            if position.location_type == "PICK":
                raise DataValidationError("Pick location assignments cannot be cleared")
            if position.qty_on_hand_cases != 0:
                raise DataValidationError("Location must be empty before clearing assignment")
            if position.item_id is None:
                raise DataValidationError("Location has no assignment to clear")
            transaction_id = _transaction_id(sequence, 1)
            clear_id = _record_id("CLEAR", sequence)
            self._insert_event(command, sequence, "CLEAR_LOCATION", clear_id)
            self._repository.insert_inventory_transaction(
                InventoryTransactionRecord(
                    run_id=command.run_id,
                    transaction_id=transaction_id,
                    transaction_group_id=_transaction_group_id(sequence),
                    command_id=command.command_id,
                    event_sequence=sequence,
                    line_number=1,
                    transaction_type="CLEAR_LOCATION",
                    location_id=command.location_id,
                    related_location_id=None,
                    item_id=position.item_id,
                    qty_delta_cases=0,
                    balance_before_cases=0,
                    balance_after_cases=0,
                    operator_id=None,
                    event_utc=command.event_utc,
                    recorded_utc=command.recorded_utc,
                    reason_code="EXPLICIT_CLEAR",
                    source_record_type="ASSIGNMENT",
                    source_record_id=clear_id,
                )
            )
            self._repository.update_inventory(
                InventoryMasterRecord(
                    run_id=command.run_id,
                    location_id=command.location_id,
                    item_id=None,
                    qty_on_hand_cases=0,
                    code_date=None,
                    reorder_trigger_cases=None,
                    minimum_qty_cases=None,
                    target_qty_cases=None,
                    maximum_qty_cases=None,
                    last_transaction_id=transaction_id,
                    last_updated_utc=_stored_utc(command.recorded_utc),
                )
            )
            return self._accept(
                command,
                sequence,
                "CLEAR_LOCATION",
                clear_id,
                (transaction_id,),
            )

    def record_pick(self, command: RecordPickAttempt) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            self._require_role(command.run_id, command.selector_id, {"SELECTOR"})
            trip = self._repository.trip_state(command.run_id, command.trip_id)
            if trip is None:
                raise DataValidationError(f"Unknown trip: {command.trip_id}")
            if trip.selector_id != command.selector_id:
                raise DataValidationError("Pick selector does not match trip selector")
            if not _parse_utc(trip.start_utc) <= command.event_utc <= _parse_utc(trip.end_utc):
                raise DataValidationError("Pick event must occur inside its trip")
            position = self._require_position(command.run_id, command.location_id)
            if position.location_type != "PICK" or position.pickable_flag != 1:
                raise DataValidationError("Picks require an active pick location")
            if position.item_id != command.item_id:
                raise DataValidationError("Pick item does not match location assignment")
            self._validate_pick_quantities(command, position)
            pick_id = _record_id("PICK", sequence)
            self._insert_event(command, sequence, "PICK", pick_id)
            after = position.qty_on_hand_cases - command.picked_qty_cases
            self._repository.insert_pick_event(
                PickEventRecord(
                    run_id=command.run_id,
                    pick_event_id=pick_id,
                    command_id=command.command_id,
                    event_sequence=sequence,
                    trip_id=command.trip_id,
                    selector_id=command.selector_id,
                    item_id=command.item_id,
                    pick_location_id=command.location_id,
                    event_utc=command.event_utc,
                    recorded_utc=command.recorded_utc,
                    requested_qty_cases=command.requested_qty_cases,
                    picked_qty_cases=command.picked_qty_cases,
                    short_qty_cases=command.short_qty_cases,
                    short_reason_code=command.short_reason_code,
                    system_qty_before_cases=position.qty_on_hand_cases,
                    system_qty_after_cases=after,
                    eligible_pick_flag=command.eligible_pick_flag,
                )
            )
            transaction_ids: tuple[str, ...] = ()
            if command.picked_qty_cases > 0:
                transaction_id = _transaction_id(sequence, 1)
                self._repository.insert_inventory_transaction(
                    self._quantity_transaction(
                        command=command,
                        sequence=sequence,
                        line_number=1,
                        transaction_id=transaction_id,
                        transaction_type="PICK",
                        location_id=command.location_id,
                        related_location_id=None,
                        item_id=command.item_id,
                        delta=-command.picked_qty_cases,
                        before=position.qty_on_hand_cases,
                        operator_id=command.selector_id,
                        reason_code=command.short_reason_code,
                        source_record_type="PICK",
                        source_record_id=pick_id,
                    )
                )
                self._repository.update_inventory(
                    self._updated_position(
                        position,
                        qty=after,
                        item_id=position.item_id,
                        code_date=position.code_date,
                        transaction_id=transaction_id,
                        recorded_utc=command.recorded_utc,
                    )
                )
                transaction_ids = (transaction_id,)
            return self._accept(command, sequence, "PICK", pick_id, transaction_ids)

    def create_replenishment(self, command: CreateReplenishmentTask) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            if command.operator_id is not None:
                self._require_role(command.run_id, command.operator_id, {"REPLENISHMENT"})
            if command.requested_qty_cases <= 0:
                raise DataValidationError("Replenishment requested quantity must be positive")
            source, destination = self._validate_transfer_positions(
                command.run_id,
                command.item_id,
                command.source_location_id,
                command.destination_location_id,
                destination_must_be_pick=True,
            )
            if source.location_type not in {"RESERVE", "STAGING"}:
                raise DataValidationError("Replenishment source must be reserve or staging")
            task_id = _record_id("REPL", sequence)
            self._insert_event(command, sequence, "REPLENISHMENT_CREATE", task_id)
            self._repository.insert_replenishment_task(
                ReplenishmentTaskRecord(
                    run_id=command.run_id,
                    replenishment_task_id=task_id,
                    create_command_id=command.command_id,
                    confirm_command_id=None,
                    event_sequence=None,
                    item_id=command.item_id,
                    source_location_id=source.location_id,
                    destination_location_id=destination.location_id,
                    operator_id=command.operator_id,
                    created_utc=command.event_utc,
                    started_utc=None,
                    confirmed_utc=None,
                    recorded_utc=command.recorded_utc,
                    requested_qty_cases=command.requested_qty_cases,
                    confirmed_qty_cases=0,
                    status="CREATED",
                    delay_reason_code=None,
                )
            )
            return self._accept(command, sequence, "REPLENISHMENT_TASK", task_id)

    def start_replenishment(self, command: StartReplenishmentTask) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            self._require_role(command.run_id, command.operator_id, {"REPLENISHMENT"})
            task = self._require_replenishment(command.run_id, command.replenishment_task_id)
            if task.status != "CREATED":
                raise DataValidationError("Only a CREATED replenishment can be started")
            if command.event_utc < _parse_utc(task.created_utc):
                raise DataValidationError("Replenishment start cannot precede creation")
            self._insert_event(
                command,
                sequence,
                "REPLENISHMENT_START",
                command.replenishment_task_id,
            )
            self._repository.start_replenishment_task(
                run_id=command.run_id,
                replenishment_task_id=command.replenishment_task_id,
                operator_id=command.operator_id,
                started_utc=command.event_utc,
                recorded_utc=command.recorded_utc,
            )
            return self._accept(
                command,
                sequence,
                "REPLENISHMENT_TASK",
                command.replenishment_task_id,
            )

    def confirm_replenishment(self, command: ConfirmReplenishmentTask) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            self._require_role(command.run_id, command.operator_id, {"REPLENISHMENT"})
            task = self._require_replenishment(command.run_id, command.replenishment_task_id)
            if task.status != "STARTED" or task.started_utc is None:
                raise DataValidationError("Only a STARTED replenishment can be confirmed")
            if command.event_utc < _parse_utc(task.started_utc):
                raise DataValidationError("Confirmation cannot precede task start")
            if not 0 < command.confirmed_qty_cases <= task.requested_qty_cases:
                raise DataValidationError(
                    "Confirmed quantity must be within the requested quantity"
                )
            source, destination = self._validate_transfer_positions(
                command.run_id,
                task.item_id,
                task.source_location_id,
                task.destination_location_id,
                destination_must_be_pick=True,
            )
            self._validate_transfer_quantity(
                source,
                destination,
                command.confirmed_qty_cases,
            )
            self._insert_event(
                command,
                sequence,
                "REPLENISHMENT_CONFIRM",
                command.replenishment_task_id,
            )
            transaction_ids = self._write_transfer(
                command=command,
                sequence=sequence,
                item_id=task.item_id,
                source=source,
                destination=destination,
                qty_cases=command.confirmed_qty_cases,
                operator_id=command.operator_id,
                source_record_type="REPLENISHMENT",
                source_record_id=command.replenishment_task_id,
                reason_code=None,
            )
            self._repository.confirm_replenishment_task(
                run_id=command.run_id,
                replenishment_task_id=command.replenishment_task_id,
                command_id=command.command_id,
                event_sequence=sequence,
                operator_id=command.operator_id,
                confirmed_utc=command.event_utc,
                recorded_utc=command.recorded_utc,
                confirmed_qty_cases=command.confirmed_qty_cases,
            )
            return self._accept(
                command,
                sequence,
                "REPLENISHMENT_TASK",
                command.replenishment_task_id,
                transaction_ids,
            )

    def transfer_inventory(self, command: TransferInventory) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            if command.operator_id is not None:
                self._require_role(
                    command.run_id,
                    command.operator_id,
                    {"REPLENISHMENT", "INVENTORY_CONTROL"},
                )
            source, destination = self._validate_transfer_positions(
                command.run_id,
                command.item_id,
                command.source_location_id,
                command.destination_location_id,
                destination_must_be_pick=False,
            )
            self._validate_transfer_quantity(source, destination, command.qty_cases)
            transfer_id = _record_id("MOVE", sequence)
            self._insert_event(command, sequence, "DIRECT_TRANSFER", transfer_id)
            transaction_ids = self._write_transfer(
                command=command,
                sequence=sequence,
                item_id=command.item_id,
                source=source,
                destination=destination,
                qty_cases=command.qty_cases,
                operator_id=command.operator_id,
                source_record_type="DIRECT_TRANSFER",
                source_record_id=transfer_id,
                reason_code=command.reason_code,
            )
            return self._accept(
                command,
                sequence,
                "DIRECT_TRANSFER",
                transfer_id,
                transaction_ids,
            )

    def adjust_inventory(self, command: AdjustInventory) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            self._require_role(
                command.run_id,
                command.operator_id,
                {"INVENTORY_CONTROL", "QA", "SYSTEM"},
            )
            if command.reason_code not in _ADJUSTMENT_REASONS:
                raise DataValidationError(f"Unsupported adjustment reason: {command.reason_code}")
            if command.qty_delta_cases == 0:
                raise DataValidationError("Inventory adjustment must be nonzero")
            position = self._require_position(command.run_id, command.location_id)
            if position.item_id != command.item_id:
                raise DataValidationError("Adjustment item does not match location assignment")
            after = position.qty_on_hand_cases + command.qty_delta_cases
            if after < 0:
                raise DataValidationError("Inventory adjustment would make quantity negative")
            self._require_within_maximum(position, after)
            adjustment_id = _record_id("ADJ", sequence)
            transaction_id = _transaction_id(sequence, 1)
            self._insert_event(command, sequence, "ADJUSTMENT", adjustment_id)
            self._repository.insert_adjustment(
                InventoryAdjustmentRecord(
                    run_id=command.run_id,
                    adjustment_id=adjustment_id,
                    command_id=command.command_id,
                    event_sequence=sequence,
                    item_id=command.item_id,
                    location_id=command.location_id,
                    operator_id=command.operator_id,
                    effective_utc=command.event_utc,
                    recorded_utc=command.recorded_utc,
                    qty_delta_cases=command.qty_delta_cases,
                    reason_code=command.reason_code,
                    reference_code=command.reference_code,
                )
            )
            self._repository.insert_inventory_transaction(
                self._quantity_transaction(
                    command=command,
                    sequence=sequence,
                    line_number=1,
                    transaction_id=transaction_id,
                    transaction_type=_adjustment_transaction_type(command.reason_code),
                    location_id=command.location_id,
                    related_location_id=None,
                    item_id=command.item_id,
                    delta=command.qty_delta_cases,
                    before=position.qty_on_hand_cases,
                    operator_id=command.operator_id,
                    reason_code=command.reason_code,
                    source_record_type="ADJUSTMENT",
                    source_record_id=adjustment_id,
                )
            )
            self._repository.update_inventory(
                self._updated_position(
                    position,
                    qty=after,
                    item_id=position.item_id,
                    code_date=position.code_date,
                    transaction_id=transaction_id,
                    recorded_utc=command.recorded_utc,
                )
            )
            return self._accept(
                command,
                sequence,
                "INVENTORY_ADJUSTMENT",
                adjustment_id,
                (transaction_id,),
            )

    def record_qa_event(self, command: RecordQaEvent) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            self._require_role(command.run_id, command.operator_id, {"QA", "SYSTEM"})
            if command.event_type not in _QA_EVENT_TYPES:
                raise DataValidationError(f"Unsupported QA event type: {command.event_type}")
            if command.disposition_code not in _QA_DISPOSITIONS:
                raise DataValidationError(f"Unsupported QA disposition: {command.disposition_code}")
            if command.qty_affected_cases <= 0:
                raise DataValidationError("QA affected quantity must be positive")
            position = self._require_position(command.run_id, command.location_id)
            if position.item_id != command.item_id:
                raise DataValidationError("QA item does not match location assignment")
            qa_event_id = _record_id("QA", sequence)
            self._insert_event(command, sequence, "QA", qa_event_id)
            self._repository.insert_qa_event(
                QaEventRecord(
                    run_id=command.run_id,
                    qa_event_id=qa_event_id,
                    command_id=command.command_id,
                    event_sequence=sequence,
                    item_id=command.item_id,
                    location_id=command.location_id,
                    operator_id=command.operator_id,
                    event_type=command.event_type,
                    occurred_utc=command.event_utc,
                    recorded_utc=command.recorded_utc,
                    qty_affected_cases=command.qty_affected_cases,
                    reason_code=command.reason_code,
                    disposition_code=command.disposition_code,
                )
            )
            return self._accept(command, sequence, "QA_EVENT", qa_event_id)

    def record_system_event(self, command: RecordSystemEvent) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            if command.event_type not in _SYSTEM_EVENT_TYPES:
                raise DataValidationError(f"Unsupported system event type: {command.event_type}")
            if command.severity_code not in {"LOW", "MEDIUM", "HIGH"}:
                raise DataValidationError("Unsupported system-event severity")
            self._require_aware(command.end_utc, "System event end")
            if command.event_utc >= command.end_utc:
                raise DataValidationError("System event start must precede end")
            if (
                command.zone_id is None
                and command.location_id is None
                and command.aisle_code is None
            ):
                raise DataValidationError("System event requires zone, location, or aisle scope")
            if command.zone_id is not None and not self._repository.zone_exists(
                command.run_id, command.zone_id
            ):
                raise DataValidationError(f"Unknown active zone: {command.zone_id}")
            if command.location_id is not None:
                self._require_position(command.run_id, command.location_id)
            system_event_id = _record_id("SYS", sequence)
            self._insert_event(command, sequence, "SYSTEM_EVENT", system_event_id)
            self._repository.insert_system_event(
                SystemEventRecord(
                    run_id=command.run_id,
                    system_event_id=system_event_id,
                    command_id=command.command_id,
                    event_sequence=sequence,
                    event_type=command.event_type,
                    zone_id=command.zone_id,
                    location_id=command.location_id,
                    aisle_code=command.aisle_code,
                    start_utc=command.event_utc,
                    end_utc=command.end_utc,
                    severity_code=command.severity_code,
                    recorded_utc=command.recorded_utc,
                )
            )
            return self._accept(command, sequence, "SYSTEM_EVENT", system_event_id)

    def capture_snapshot(self, command: CaptureInventorySnapshot) -> WmsCommandResult:
        with self._repository.unit_of_work():
            sequence = self._begin(command)
            if command.snapshot_type not in _SNAPSHOT_TYPES:
                raise DataValidationError(f"Unsupported snapshot type: {command.snapshot_type}")
            batch_id = _record_id("SNAPSHOT", sequence)
            self._insert_event(command, sequence, "INVENTORY_SNAPSHOT", batch_id)
            positions = self._repository.all_inventory_positions(command.run_id)
            lines = [
                SnapshotLineRecord(
                    run_id=command.run_id,
                    snapshot_batch_id=batch_id,
                    snapshot_line_id=f"SNAPLINE-{sequence:06d}-{line_number:04d}",
                    snapshot_utc=command.event_utc,
                    snapshot_type=command.snapshot_type,
                    location_id=position.location_id,
                    item_id=position.item_id,
                    qty_on_hand_cases=position.qty_on_hand_cases,
                    code_date=date.fromisoformat(position.code_date)
                    if position.code_date
                    else None,
                    last_transaction_id=position.last_transaction_id,
                    source_code=command.source_code,
                )
                for line_number, position in enumerate(positions, start=1)
            ]
            self._repository.insert_snapshot_lines(lines)
            return self._accept(command, sequence, "INVENTORY_SNAPSHOT", batch_id)

    def _begin(self, command: WmsCommand) -> int:
        self._validate_command_context(command)
        if self._repository.command_exists(command.run_id, command.command_id):
            raise DuplicateCommandError(
                f"WMS command_id has already been accepted: {command.command_id}"
            )
        return self._repository.next_event_sequence(command.run_id)

    def _validate_command_context(self, command: WmsCommand) -> None:
        if command.run_id != self._repository.run_id():
            raise DataValidationError("Command run_id does not match the WMS database")
        if not command.command_id.strip():
            raise DataValidationError("command_id must be nonempty")
        if command.event_utc.tzinfo is None or command.recorded_utc.tzinfo is None:
            raise DataValidationError("WMS command timestamps must be timezone-aware")
        if command.recorded_utc < command.event_utc:
            raise DataValidationError("recorded_utc cannot precede event_utc")

    def _require_aware(self, value: datetime, label: str) -> None:
        if value.tzinfo is None:
            raise DataValidationError(f"{label} must be timezone-aware")

    def _insert_event(
        self,
        command: WmsCommand,
        sequence: int,
        event_type: str,
        source_record_id: str,
    ) -> None:
        self._repository.insert_event_sequence(
            EventSequenceRecord(
                run_id=command.run_id,
                event_sequence=sequence,
                event_type=event_type,
                source_record_id=source_record_id,
                event_utc=command.event_utc,
                recorded_utc=command.recorded_utc,
            )
        )

    def _accept(
        self,
        command: WmsCommand,
        sequence: int,
        result_record_type: str,
        result_record_id: str,
        transaction_ids: tuple[str, ...] = (),
    ) -> WmsCommandResult:
        self._repository.record_command(
            run_id=command.run_id,
            command_id=command.command_id,
            command_type=type(command).__name__,
            payload_hash=command_payload_hash(command),
            accepted_utc=command.recorded_utc,
            result_record_type=result_record_type,
            result_record_id=result_record_id,
            event_sequence=sequence,
        )
        return WmsCommandResult(
            command_id=command.command_id,
            result_record_type=result_record_type,
            result_record_id=result_record_id,
            event_sequence=sequence,
            transaction_ids=transaction_ids,
        )

    def _require_position(self, run_id: str, location_id: str) -> InventoryPosition:
        position = self._repository.inventory_position(run_id, location_id)
        if position is None:
            raise DataValidationError(f"Unknown inventory location: {location_id}")
        return position

    def _require_item(self, run_id: str, item_id: str) -> tuple[str, int]:
        item = self._repository.item_profile(run_id, item_id)
        if item is None:
            raise DataValidationError(f"Unknown active item: {item_id}")
        return item

    def _require_role(self, run_id: str, operator_id: str, allowed: set[str]) -> None:
        role = self._repository.operator_role(run_id, operator_id)
        if role not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise DataValidationError(f"Operator {operator_id} requires role in: {allowed_text}")

    def _require_inventory_location(self, position: InventoryPosition) -> None:
        if position.active_flag != 1 or position.location_type in {"DOCK", "INACTIVE"}:
            raise DataValidationError("Location does not permit recorded inventory")

    def _assignment_controls(
        self,
        command: AssignItemToLocation,
        position: InventoryPosition,
        cases_per_pallet: int,
    ) -> tuple[int | None, int | None, int | None, int | None]:
        controls = (
            command.minimum_qty_cases,
            command.reorder_trigger_cases,
            command.target_qty_cases,
            command.maximum_qty_cases,
        )
        if position.location_type != "PICK":
            if any(value is not None for value in controls):
                raise DataValidationError("Only pick locations use replenishment controls")
            return (None, None, None, None)
        if any(value is None for value in controls):
            raise DataValidationError("Pick assignments require all replenishment controls")
        minimum, trigger, target, maximum = controls
        assert minimum is not None
        assert trigger is not None
        assert target is not None
        assert maximum is not None
        if min(minimum, trigger, target, maximum) < 0:
            raise DataValidationError("Replenishment controls cannot be negative")
        if not minimum <= trigger <= target <= maximum:
            raise DataValidationError("Replenishment controls must be ordered")
        if position.pallet_capacity is None:
            raise DataValidationError("Pick location has no pallet capacity")
        dynamic_maximum = calculate_location_maximum_cases(
            position.pallet_capacity,
            cases_per_pallet,
        )
        if maximum > dynamic_maximum:
            raise DataValidationError("Pick maximum exceeds dynamic physical capacity")
        return controls

    def _validate_pick_quantities(
        self,
        command: RecordPickAttempt,
        position: InventoryPosition,
    ) -> None:
        if command.requested_qty_cases <= 0:
            raise DataValidationError("Requested pick quantity must be positive")
        if command.picked_qty_cases < 0 or command.short_qty_cases < 0:
            raise DataValidationError("Pick and short quantities cannot be negative")
        if command.picked_qty_cases + command.short_qty_cases != command.requested_qty_cases:
            raise DataValidationError("Picked and short quantities must equal requested quantity")
        if command.picked_qty_cases > position.qty_on_hand_cases:
            raise DataValidationError("Picked quantity exceeds recorded inventory")
        if (command.short_qty_cases > 0) != (command.short_reason_code is not None):
            raise DataValidationError(
                "Short reason is required exactly when short quantity is positive"
            )
        if command.eligible_pick_flag not in {0, 1}:
            raise DataValidationError("eligible_pick_flag must be zero or one")

    def _validate_transfer_positions(
        self,
        run_id: str,
        item_id: str,
        source_location_id: str,
        destination_location_id: str,
        *,
        destination_must_be_pick: bool,
    ) -> tuple[InventoryPosition, InventoryPosition]:
        if source_location_id == destination_location_id:
            raise DataValidationError("Transfer source and destination must differ")
        item_zone, item_cases_per_pallet = self._require_item(run_id, item_id)
        source = self._require_position(run_id, source_location_id)
        destination = self._require_position(run_id, destination_location_id)
        self._require_inventory_location(source)
        self._require_inventory_location(destination)
        if source.item_id != item_id:
            raise DataValidationError("Transfer item does not match source inventory")
        if destination.item_id not in {None, item_id}:
            raise DataValidationError("Destination contains a different item")
        if destination.zone_code != item_zone:
            raise DataValidationError("Item storage zone does not match destination zone")
        if destination.item_id is None:
            destination = replace(
                destination,
                item_required_zone_code=item_zone,
                cases_per_pallet=item_cases_per_pallet,
            )
        if destination_must_be_pick and destination.location_type != "PICK":
            raise DataValidationError("Replenishment destination must be a pick location")
        return source, destination

    def _validate_transfer_quantity(
        self,
        source: InventoryPosition,
        destination: InventoryPosition,
        qty_cases: int,
    ) -> None:
        if qty_cases <= 0:
            raise DataValidationError("Transfer quantity must be positive")
        if qty_cases > source.qty_on_hand_cases:
            raise DataValidationError("Transfer exceeds source inventory")
        self._require_within_maximum(destination, destination.qty_on_hand_cases + qty_cases)

    def _require_within_maximum(self, position: InventoryPosition, qty: int) -> None:
        if position.location_type == "PICK":
            if position.maximum_qty_cases is None:
                raise DataValidationError("Pick location has no operational maximum")
            if qty > position.maximum_qty_cases:
                raise DataValidationError("Quantity exceeds pick-location maximum")
            return
        if position.pallet_capacity is not None and position.cases_per_pallet is not None:
            dynamic_maximum = calculate_location_maximum_cases(
                position.pallet_capacity,
                position.cases_per_pallet,
            )
            if qty > dynamic_maximum:
                raise DataValidationError("Quantity exceeds dynamic physical capacity")

    def _write_transfer(
        self,
        *,
        command: WmsCommand,
        sequence: int,
        item_id: str,
        source: InventoryPosition,
        destination: InventoryPosition,
        qty_cases: int,
        operator_id: str | None,
        source_record_type: str,
        source_record_id: str,
        reason_code: str | None,
    ) -> tuple[str, str]:
        source_transaction_id = _transaction_id(sequence, 1)
        destination_transaction_id = _transaction_id(sequence, 2)
        self._repository.insert_inventory_transaction(
            self._quantity_transaction(
                command=command,
                sequence=sequence,
                line_number=1,
                transaction_id=source_transaction_id,
                transaction_type="TRANSFER_OUT",
                location_id=source.location_id,
                related_location_id=destination.location_id,
                item_id=item_id,
                delta=-qty_cases,
                before=source.qty_on_hand_cases,
                operator_id=operator_id,
                reason_code=reason_code,
                source_record_type=source_record_type,
                source_record_id=source_record_id,
            )
        )
        self._repository.insert_inventory_transaction(
            self._quantity_transaction(
                command=command,
                sequence=sequence,
                line_number=2,
                transaction_id=destination_transaction_id,
                transaction_type="TRANSFER_IN",
                location_id=destination.location_id,
                related_location_id=source.location_id,
                item_id=item_id,
                delta=qty_cases,
                before=destination.qty_on_hand_cases,
                operator_id=operator_id,
                reason_code=reason_code,
                source_record_type=source_record_type,
                source_record_id=source_record_id,
            )
        )
        source_after = source.qty_on_hand_cases - qty_cases
        clear_source = source_after == 0 and source.location_type != "PICK"
        self._repository.update_inventory(
            self._updated_position(
                source,
                qty=source_after,
                item_id=None if clear_source else source.item_id,
                code_date=None if clear_source else source.code_date,
                transaction_id=source_transaction_id,
                recorded_utc=command.recorded_utc,
            )
        )
        destination_code_date = destination.code_date or source.code_date
        self._repository.update_inventory(
            self._updated_position(
                destination,
                qty=destination.qty_on_hand_cases + qty_cases,
                item_id=item_id,
                code_date=destination_code_date,
                transaction_id=destination_transaction_id,
                recorded_utc=command.recorded_utc,
            )
        )
        return source_transaction_id, destination_transaction_id

    def _quantity_transaction(
        self,
        *,
        command: WmsCommand,
        sequence: int,
        line_number: int,
        transaction_id: str,
        transaction_type: str,
        location_id: str,
        related_location_id: str | None,
        item_id: str,
        delta: int,
        before: int,
        operator_id: str | None,
        reason_code: str | None,
        source_record_type: str,
        source_record_id: str,
    ) -> InventoryTransactionRecord:
        return InventoryTransactionRecord(
            run_id=command.run_id,
            transaction_id=transaction_id,
            transaction_group_id=_transaction_group_id(sequence),
            command_id=command.command_id,
            event_sequence=sequence,
            line_number=line_number,
            transaction_type=transaction_type,
            location_id=location_id,
            related_location_id=related_location_id,
            item_id=item_id,
            qty_delta_cases=delta,
            balance_before_cases=before,
            balance_after_cases=before + delta,
            operator_id=operator_id,
            event_utc=command.event_utc,
            recorded_utc=command.recorded_utc,
            reason_code=reason_code,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
        )

    def _updated_position(
        self,
        position: InventoryPosition,
        *,
        qty: int,
        item_id: str | None,
        code_date: str | None,
        transaction_id: str,
        recorded_utc: datetime,
    ) -> InventoryMasterRecord:
        clear_controls = item_id is None
        return InventoryMasterRecord(
            run_id=position.run_id,
            location_id=position.location_id,
            item_id=item_id,
            qty_on_hand_cases=qty,
            code_date=code_date,
            reorder_trigger_cases=None if clear_controls else position.reorder_trigger_cases,
            minimum_qty_cases=None if clear_controls else position.minimum_qty_cases,
            target_qty_cases=None if clear_controls else position.target_qty_cases,
            maximum_qty_cases=None if clear_controls else position.maximum_qty_cases,
            last_transaction_id=transaction_id,
            last_updated_utc=_stored_utc(recorded_utc),
        )

    def _require_replenishment(self, run_id: str, task_id: str) -> ReplenishmentTaskState:
        task = self._repository.replenishment_task(run_id, task_id)
        if task is None:
            raise DataValidationError(f"Unknown replenishment task: {task_id}")
        return task


def _record_id(prefix: str, sequence: int) -> str:
    return f"{prefix}-{sequence:06d}"


def _transaction_group_id(sequence: int) -> str:
    return f"TXG-{sequence:06d}"


def _transaction_id(sequence: int, line_number: int) -> str:
    return f"TXN-{sequence:06d}-{line_number:02d}"


def _adjustment_transaction_type(reason_code: str) -> str:
    if reason_code == "DAMAGE":
        return "DAMAGE"
    if reason_code == "FOUND_PRODUCT":
        return "FOUND_PRODUCT"
    if reason_code == "COUNT_CORRECTION":
        return "COUNT_CORRECTION"
    return "ADJUSTMENT"


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _stored_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
