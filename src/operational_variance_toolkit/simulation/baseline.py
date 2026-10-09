"""Scenario-free baseline protocol over physical actions and public WMS commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.generation.random_source import create_named_random_streams
from operational_variance_toolkit.simulation.physical import (
    ChronologicalActionRunner,
    PhysicalInventoryState,
    PhysicalPick,
    PhysicalPickResult,
    PhysicalQuantityChange,
    PhysicalTransfer,
)
from operational_variance_toolkit.simulation.policy import (
    DriverPolicy,
    PolicyAdjustment,
    StandardDriverPolicy,
)
from operational_variance_toolkit.simulation.read_model import (
    BaselineInputs,
    ShiftPlan,
    SlotPlan,
)
from operational_variance_toolkit.wms.domain.commands import (
    AdjustInventory,
    CaptureInventorySnapshot,
    ConfirmReplenishmentTask,
    CreateReplenishmentTask,
    CreateTrip,
    RecordPickAttempt,
    RecordQaEvent,
    RecordSystemEvent,
    StartReplenishmentTask,
    WmsCommandResult,
)


@dataclass(frozen=True, slots=True)
class BaselineGenerationCounts:
    trips: int
    pick_events: int
    replenishment_tasks: int
    qa_events: int
    inventory_adjustments: int
    system_events: int
    closing_snapshots: int


@dataclass(frozen=True, slots=True)
class BaselineDriverResult:
    counts: BaselineGenerationCounts
    physical_quantities: dict[str, int]


@dataclass(frozen=True, slots=True)
class _PendingMovement:
    task_id: str
    item_id: str
    source_location_id: str
    destination_location_id: str
    qty_cases: int


class WmsCommandGateway(Protocol):
    """Narrow public WMS surface available to external drivers."""

    def create_trip(self, command: CreateTrip) -> WmsCommandResult: ...
    def record_pick(self, command: RecordPickAttempt) -> WmsCommandResult: ...
    def create_replenishment(self, command: CreateReplenishmentTask) -> WmsCommandResult: ...
    def start_replenishment(self, command: StartReplenishmentTask) -> WmsCommandResult: ...
    def confirm_replenishment(self, command: ConfirmReplenishmentTask) -> WmsCommandResult: ...
    def adjust_inventory(self, command: AdjustInventory) -> WmsCommandResult: ...
    def record_qa_event(self, command: RecordQaEvent) -> WmsCommandResult: ...
    def record_system_event(self, command: RecordSystemEvent) -> WmsCommandResult: ...
    def capture_snapshot(self, command: CaptureInventorySnapshot) -> WmsCommandResult: ...


def run_baseline_protocol(
    config: ProjectConfig,
    run_id: str,
    inputs: BaselineInputs,
    wms: WmsCommandGateway,
    policy: DriverPolicy | None = None,
) -> BaselineDriverResult:
    """Run ordinary baseline work with separate physical and recorded state."""

    if config.failures.any_enabled and policy is None:
        raise DataValidationError("Baseline protocol does not accept enabled failure controls")
    active_policy: DriverPolicy = policy or StandardDriverPolicy()
    _require_inputs(inputs)
    physical = PhysicalInventoryState(inputs.positions)
    runner = ChronologicalActionRunner()
    streams = create_named_random_streams(
        config.run.seed,
        ("operations_trips", "operations_picks"),
    )
    slots_by_zone = _slots_by_zone(inputs.slots)
    slot_offsets = {zone_id: 0 for zone_id in inputs.zone_ids}
    trip_spacing = (config.run.end_utc - config.run.start_utc) / (config.operations.trip_count + 1)
    pick_count = 0
    replenishment_count = 0
    qa_count = 0
    adjustment_count = 0
    pending_movements: list[_PendingMovement] = []
    last_trip_end = config.run.start_utc

    system_count = _record_system_events(wms, config, run_id, inputs.zone_ids)
    qa_interval = max(
        1,
        config.operations.trip_count
        * (config.operations.pick_lines_per_trip_min + config.operations.pick_lines_per_trip_max)
        // 2
        // max(config.operations.qa_event_count, 1),
    )

    for trip_index in range(1, config.operations.trip_count + 1):
        default_zone_id = inputs.zone_ids[(trip_index - 1) % len(inputs.zone_ids)]
        zone_id = active_policy.trip_zone(trip_index, default_zone_id)
        zone_slots = slots_by_zone[zone_id]
        default_selector_id = inputs.selectors[(trip_index - 1) % len(inputs.selectors)]
        selector_id = active_policy.trip_selector(trip_index, default_selector_id)
        planned_lines = int(
            streams["operations_trips"].integers(
                config.operations.pick_lines_per_trip_min,
                config.operations.pick_lines_per_trip_max + 1,
            )
        )
        nominal_start = max(
            config.run.start_utc + trip_spacing * trip_index,
            last_trip_end + timedelta(minutes=1),
        )
        duration = timedelta(minutes=max(30, planned_lines * 11))
        shift, start_utc = _trip_window(inputs.shifts, nominal_start, duration)
        end_utc = min(
            start_utc + duration,
            _parse_utc(shift.end_utc),
        )
        if end_utc <= start_utc:
            raise DataValidationError("Baseline trip has no time inside its shift")
        last_trip_end = end_utc
        trip = wms.create_trip(
            CreateTrip(
                run_id=run_id,
                command_id=f"BASE-TRIP-{trip_index:06d}",
                event_utc=start_utc,
                recorded_utc=start_utc,
                shift_id=shift.shift_id,
                selector_id=selector_id,
                assigned_zone_id=zone_id,
                end_utc=end_utc,
                planned_pick_lines=planned_lines,
                planned_cases=planned_lines * 2,
            )
        )
        active_policy.after_trip(trip.result_record_id, selector_id)

        for line_index in range(1, planned_lines + 1):
            offset = slot_offsets[zone_id]
            default_slot = zone_slots[offset % len(zone_slots)]
            slot_offsets[zone_id] = offset + 1
            slot = active_policy.slot(trip_index, line_index, default_slot)
            pick_utc = min(
                start_utc + timedelta(minutes=line_index * 10),
                end_utc - timedelta(seconds=1),
            )
            replenishment_count += _replenish_if_needed(
                runner,
                physical,
                wms,
                run_id,
                slot,
                inputs.replenishers,
                pick_utc,
                replenishment_count,
                active_policy,
                pending_movements,
            )
            default_requested = 1 + int(streams["operations_picks"].integers(0, 2))
            requested = active_policy.requested_quantity(slot, default_requested)
            default_force_short = (
                float(streams["operations_picks"].random()) < config.operations.short_probability
            )
            force_short = active_policy.force_short(slot, default_force_short)
            pick_count += 1
            physical_result = runner.apply(
                physical,
                PhysicalPick(
                    action_id=f"PHYS-PICK-{pick_count:06d}",
                    scheduled_utc=pick_utc,
                    location_id=slot.pick_location_id,
                    item_id=slot.item_id,
                    requested_qty_cases=requested,
                    force_short=force_short,
                ),
            )
            assert isinstance(physical_result, PhysicalPickResult)
            pick = wms.record_pick(
                RecordPickAttempt(
                    run_id=run_id,
                    command_id=f"BASE-PICK-{pick_count:06d}",
                    event_utc=pick_utc,
                    recorded_utc=pick_utc + timedelta(seconds=30),
                    trip_id=trip.result_record_id,
                    selector_id=selector_id,
                    item_id=slot.item_id,
                    location_id=slot.pick_location_id,
                    requested_qty_cases=requested,
                    picked_qty_cases=physical_result.picked_qty_cases,
                    short_qty_cases=physical_result.short_qty_cases,
                    short_reason_code=(
                        "BASELINE_ACCESS" if physical_result.short_qty_cases else None
                    ),
                )
            )
            post_pick = active_policy.after_pick(
                pick.result_record_id,
                selector_id,
                slot,
                physical_result,
            )
            adjustment_count = _apply_post_pick(
                runner,
                physical,
                wms,
                run_id,
                inputs,
                active_policy,
                post_pick.adjustments,
                post_pick.release_pending_movements,
                pending_movements,
                pick_utc,
                adjustment_count,
            )
            qa_target = active_policy.qa_target_count(config.operations.qa_event_count)
            if qa_count < qa_target and pick_count % qa_interval == 0:
                damage = qa_count < config.operations.damage_event_count
                qa_count, adjustment_count = _record_qa(
                    runner,
                    physical,
                    wms,
                    run_id,
                    inputs,
                    slot,
                    pick_utc + timedelta(minutes=1),
                    qa_count,
                    adjustment_count,
                    damage,
                    active_policy,
                )

    _release_pending_movements(
        runner,
        physical,
        active_policy,
        pending_movements,
        max(last_trip_end, config.run.end_utc - timedelta(minutes=30)),
    )
    qa_target = active_policy.qa_target_count(config.operations.qa_event_count)
    while qa_count < qa_target:
        slot = _available_slot(inputs.slots, physical, qa_count)
        event_utc = config.run.end_utc - timedelta(minutes=20 - qa_count)
        damage = qa_count < config.operations.damage_event_count
        qa_count, adjustment_count = _record_qa(
            runner,
            physical,
            wms,
            run_id,
            inputs,
            slot,
            event_utc,
            qa_count,
            adjustment_count,
            damage,
            active_policy,
        )

    adjustment_target = active_policy.adjustment_target_count(config.operations.adjustment_count)
    while adjustment_count < adjustment_target:
        slot = _available_slot(inputs.slots, physical, adjustment_count)
        event_utc = config.run.end_utc - timedelta(seconds=30 - adjustment_count)
        adjustment_count += 1
        runner.apply(
            physical,
            PhysicalQuantityChange(
                action_id=f"PHYS-FOUND-{adjustment_count:06d}",
                scheduled_utc=event_utc,
                location_id=slot.pick_location_id,
                item_id=slot.item_id,
                qty_delta_cases=1,
            ),
        )
        adjustment = wms.adjust_inventory(
            AdjustInventory(
                run_id=run_id,
                command_id=f"BASE-ADJ-{adjustment_count:06d}",
                event_utc=event_utc,
                recorded_utc=event_utc,
                item_id=slot.item_id,
                location_id=slot.pick_location_id,
                operator_id=inputs.inventory_control_operator,
                qty_delta_cases=1,
                reason_code="FOUND_PRODUCT",
            )
        )
        active_policy.after_adjustment(None, adjustment.result_record_id)

    closing = wms.capture_snapshot(
        CaptureInventorySnapshot(
            run_id=run_id,
            command_id="BASE-CLOSING-SNAPSHOT",
            event_utc=config.run.end_utc,
            recorded_utc=config.run.end_utc,
            snapshot_type="CLOSING_SYSTEM",
            source_code="BASELINE_DRIVER",
        )
    )
    del closing
    return BaselineDriverResult(
        counts=BaselineGenerationCounts(
            trips=config.operations.trip_count,
            pick_events=pick_count,
            replenishment_tasks=replenishment_count,
            qa_events=qa_count,
            inventory_adjustments=adjustment_count,
            system_events=system_count,
            closing_snapshots=len(inputs.positions),
        ),
        physical_quantities=physical.quantities(),
    )


def _replenish_if_needed(
    runner: ChronologicalActionRunner,
    physical: PhysicalInventoryState,
    wms: WmsCommandGateway,
    run_id: str,
    slot: SlotPlan,
    replenishers: tuple[str, ...],
    pick_utc: datetime,
    count: int,
    policy: DriverPolicy,
    pending_movements: list[_PendingMovement],
) -> int:
    if any(
        movement.destination_location_id == slot.pick_location_id for movement in pending_movements
    ):
        return 0
    current = physical.quantity(slot.pick_location_id, slot.item_id)
    if current > slot.reorder_trigger_cases:
        return 0
    source = physical.quantity(slot.reserve_location_id, slot.item_id)
    quantity = min(slot.target_qty_cases - current, source)
    if quantity <= 0:
        return 0
    index = count + 1
    operator_id = replenishers[(index - 1) % len(replenishers)]
    created = pick_utc - timedelta(minutes=7)
    task = wms.create_replenishment(
        CreateReplenishmentTask(
            run_id=run_id,
            command_id=f"BASE-REPL-CREATE-{index:06d}",
            event_utc=created,
            recorded_utc=created,
            item_id=slot.item_id,
            source_location_id=slot.reserve_location_id,
            destination_location_id=slot.pick_location_id,
            requested_qty_cases=quantity,
            operator_id=operator_id,
        )
    )
    wms.start_replenishment(
        StartReplenishmentTask(
            run_id=run_id,
            command_id=f"BASE-REPL-START-{index:06d}",
            event_utc=created + timedelta(minutes=2),
            recorded_utc=created + timedelta(minutes=2),
            replenishment_task_id=task.result_record_id,
            operator_id=operator_id,
        )
    )
    transfer_utc = created + timedelta(minutes=7)
    movement_mode = policy.movement_mode(slot)
    if movement_mode == "coordinated":
        runner.apply(
            physical,
            PhysicalTransfer(
                action_id=f"PHYS-REPL-{index:06d}",
                scheduled_utc=transfer_utc,
                item_id=slot.item_id,
                source_location_id=slot.reserve_location_id,
                destination_location_id=slot.pick_location_id,
                qty_cases=quantity,
            ),
        )
    elif movement_mode == "recorded_before_physical":
        pending_movements.append(
            _PendingMovement(
                task.result_record_id,
                slot.item_id,
                slot.reserve_location_id,
                slot.pick_location_id,
                quantity,
            )
        )
    else:
        raise DataValidationError(f"Unsupported physical movement mode: {movement_mode}")
    wms.confirm_replenishment(
        ConfirmReplenishmentTask(
            run_id=run_id,
            command_id=f"BASE-REPL-CONFIRM-{index:06d}",
            event_utc=transfer_utc,
            recorded_utc=transfer_utc + timedelta(seconds=30),
            replenishment_task_id=task.result_record_id,
            confirmed_qty_cases=quantity,
            operator_id=operator_id,
        )
    )
    policy.after_replenishment(
        task.result_record_id,
        slot,
        movement_mode,
        transfer_utc,
    )
    return 1


def _record_qa(
    runner: ChronologicalActionRunner,
    physical: PhysicalInventoryState,
    wms: WmsCommandGateway,
    run_id: str,
    inputs: BaselineInputs,
    slot: SlotPlan,
    event_utc: datetime,
    qa_count: int,
    adjustment_count: int,
    damage: bool,
    policy: DriverPolicy,
) -> tuple[int, int]:
    if physical.quantity(slot.pick_location_id, slot.item_id) <= 0:
        slot = _available_slot(inputs.slots, physical, qa_count)
    qa_count += 1
    operator_id = inputs.qa_operators[(qa_count - 1) % len(inputs.qa_operators)]
    qa_policy = policy.qa_policy(qa_count, damage, slot)
    if qa_policy.physical_damage:
        runner.apply(
            physical,
            PhysicalQuantityChange(
                action_id=f"PHYS-DAMAGE-{qa_count:06d}",
                scheduled_utc=event_utc,
                location_id=slot.pick_location_id,
                item_id=slot.item_id,
                qty_delta_cases=-1,
            ),
        )
    qa_event = wms.record_qa_event(
        RecordQaEvent(
            run_id=run_id,
            command_id=f"BASE-QA-{qa_count:06d}",
            event_utc=event_utc,
            recorded_utc=event_utc,
            item_id=slot.item_id,
            location_id=slot.pick_location_id,
            operator_id=operator_id,
            event_type=qa_policy.event_type,
            qty_affected_cases=1,
            reason_code=qa_policy.reason_code,
            disposition_code=qa_policy.disposition_code,
        )
    )
    adjustment_id: str | None = None
    if qa_policy.adjustment_reason_code is not None:
        adjustment_count += 1
        adjustment = wms.adjust_inventory(
            AdjustInventory(
                run_id=run_id,
                command_id=f"BASE-ADJ-{adjustment_count:06d}",
                event_utc=event_utc + timedelta(seconds=1),
                recorded_utc=event_utc + timedelta(seconds=1),
                item_id=slot.item_id,
                location_id=slot.pick_location_id,
                operator_id=inputs.inventory_control_operator,
                qty_delta_cases=-1,
                reason_code=qa_policy.adjustment_reason_code,
                reference_code=(
                    None if qa_policy.tracking_key is not None else f"BASE-QA-{qa_count:06d}"
                ),
            )
        )
        adjustment_id = adjustment.result_record_id
    policy.after_qa(
        qa_policy.tracking_key,
        qa_event.result_record_id,
        adjustment_id,
    )
    return qa_count, adjustment_count


def _apply_post_pick(
    runner: ChronologicalActionRunner,
    physical: PhysicalInventoryState,
    wms: WmsCommandGateway,
    run_id: str,
    inputs: BaselineInputs,
    policy: DriverPolicy,
    adjustments: tuple[PolicyAdjustment, ...],
    release_pending: bool,
    pending_movements: list[_PendingMovement],
    pick_utc: datetime,
    adjustment_count: int,
) -> int:
    next_utc = pick_utc + timedelta(seconds=1)
    if release_pending:
        _release_pending_movements(
            runner,
            physical,
            policy,
            pending_movements,
            next_utc,
        )
        next_utc += timedelta(seconds=max(1, len(pending_movements)))
    for directive in adjustments:
        adjustment_count += 1
        runner.apply(
            physical,
            PhysicalQuantityChange(
                action_id=f"PHYS-POLICY-ADJ-{adjustment_count:06d}",
                scheduled_utc=next_utc,
                location_id=directive.slot.pick_location_id,
                item_id=directive.slot.item_id,
                qty_delta_cases=directive.qty_delta_cases,
            ),
        )
        result = wms.adjust_inventory(
            AdjustInventory(
                run_id=run_id,
                command_id=f"BASE-ADJ-{adjustment_count:06d}",
                event_utc=next_utc,
                recorded_utc=next_utc,
                item_id=directive.slot.item_id,
                location_id=directive.slot.pick_location_id,
                operator_id=inputs.inventory_control_operator,
                qty_delta_cases=directive.qty_delta_cases,
                reason_code=directive.reason_code,
            )
        )
        policy.after_adjustment(directive.tracking_key, result.result_record_id)
        next_utc += timedelta(seconds=1)
    return adjustment_count


def _release_pending_movements(
    runner: ChronologicalActionRunner,
    physical: PhysicalInventoryState,
    policy: DriverPolicy,
    pending_movements: list[_PendingMovement],
    event_utc: datetime,
) -> None:
    movements = tuple(pending_movements)
    pending_movements.clear()
    for index, movement in enumerate(movements, start=1):
        completed_utc = event_utc + timedelta(microseconds=index)
        runner.apply(
            physical,
            PhysicalTransfer(
                action_id=f"PHYS-DELAYED-REPL-{index:06d}",
                scheduled_utc=completed_utc,
                item_id=movement.item_id,
                source_location_id=movement.source_location_id,
                destination_location_id=movement.destination_location_id,
                qty_cases=movement.qty_cases,
            ),
        )
        policy.after_physical_movement(movement.task_id, completed_utc)


def _record_system_events(
    wms: WmsCommandGateway,
    config: ProjectConfig,
    run_id: str,
    zone_ids: tuple[str, ...],
) -> int:
    for index in range(1, config.operations.system_event_count + 1):
        start = config.run.start_utc + timedelta(minutes=15 * index)
        wms.record_system_event(
            RecordSystemEvent(
                run_id=run_id,
                command_id=f"BASE-SYSTEM-{index:06d}",
                event_utc=start,
                recorded_utc=start,
                event_type=("SCANNER_INTERRUPTION" if index % 2 else "EQUIPMENT_DELAY"),
                end_utc=start + timedelta(minutes=8 + index),
                severity_code="MEDIUM" if index % 3 == 0 else "LOW",
                zone_id=zone_ids[(index - 1) % len(zone_ids)],
            )
        )
    return config.operations.system_event_count


def _slots_by_zone(slots: tuple[SlotPlan, ...]) -> dict[str, tuple[SlotPlan, ...]]:
    return {
        zone_id: tuple(slot for slot in slots if slot.zone_id == zone_id)
        for zone_id in sorted({slot.zone_id for slot in slots})
    }


def _trip_window(
    shifts: tuple[ShiftPlan, ...],
    nominal_start: datetime,
    duration: timedelta,
) -> tuple[ShiftPlan, datetime]:
    for index, shift in enumerate(shifts):
        event_utc = nominal_start
        if _parse_utc(shift.start_utc) <= event_utc < _parse_utc(shift.end_utc):
            if event_utc + duration <= _parse_utc(shift.end_utc):
                return shift, event_utc
            if index + 1 < len(shifts):
                next_shift = shifts[index + 1]
                return next_shift, _parse_utc(next_shift.start_utc) + timedelta(minutes=1)
    raise DataValidationError(f"No shift covers baseline trip window: {nominal_start.isoformat()}")


def _available_slot(
    slots: tuple[SlotPlan, ...],
    physical: PhysicalInventoryState,
    offset: int,
) -> SlotPlan:
    for step in range(len(slots)):
        slot = slots[(offset + step) % len(slots)]
        if physical.quantity(slot.pick_location_id, slot.item_id) > 0:
            return slot
    raise DataValidationError("Baseline has no physical pick inventory available")


def _require_inputs(inputs: BaselineInputs) -> None:
    if not all(
        (
            inputs.positions,
            inputs.slots,
            inputs.shifts,
            inputs.selectors,
            inputs.replenishers,
            inputs.qa_operators,
            inputs.zone_ids,
        )
    ):
        raise DataValidationError("Baseline protocol requires complete WMS inputs")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
