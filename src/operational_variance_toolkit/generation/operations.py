"""Deterministic Phase 2 normal-operation generation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.domain.identifiers import generate_identifier
from operational_variance_toolkit.domain.operations import (
    InventorySnapshotRecord,
    SimulatorInventoryState,
    StateTransitionProcessor,
    TripRecord,
)
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.generation.random_source import create_named_random_streams
from operational_variance_toolkit.storage.repositories import OperationsRepository


@dataclass(frozen=True, slots=True)
class OperationGenerationCounts:
    trips: int
    pick_events: int
    replenishment_tasks: int
    qa_events: int
    inventory_adjustments: int
    system_events: int
    closing_snapshots: int
    scenario_ground_truth: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _SlotPlan:
    item_id: str
    pick_location_id: str
    reorder_trigger_cases: int
    target_cases: int
    maximum_cases: int
    velocity_class: str
    fragility_score: float
    zone_id: str
    zone_code: str


@dataclass(slots=True)
class _ScenarioOverlay:
    config: ProjectConfig
    slots: list[_SlotPlan]
    zones: list[Any]
    selectors: list[Any]
    streams: dict[str, Any]
    target_zone_id: str | None = None
    target_zone_code: str | None = None
    target_slots: list[_SlotPlan] = field(default_factory=list)
    target_selector_id: str | None = None
    exposed_peer_selector_ids: list[str] = field(default_factory=list)
    pattern_a_pick_ids: list[str] = field(default_factory=list)
    pattern_a_recovery_adjustment_ids: list[str] = field(default_factory=list)
    pattern_b_qa_ids: list[str] = field(default_factory=list)
    pattern_b_adjustment_ids: list[str] = field(default_factory=list)
    pattern_c_trip_ids: list[str] = field(default_factory=list)
    pattern_c_pick_ids: list[str] = field(default_factory=list)
    pattern_a_short_count: int = 0
    pattern_a_recovery_count: int = 0
    pattern_b_count: int = 0

    def __post_init__(self) -> None:
        if self.config.failures.replenishment_gap.enabled:
            zone_index = int(self.streams["failure_replenishment_gap"].integers(0, len(self.zones)))
            target_zone = self.zones[zone_index]
            self.target_zone_id = str(target_zone["zone_id"])
            self.target_zone_code = str(target_zone["zone_code"])
            zone_slots = [
                slot
                for slot in self.slots
                if slot.zone_id == self.target_zone_id and slot.velocity_class == "A"
            ]
            if not zone_slots:
                zone_slots = [slot for slot in self.slots if slot.zone_id == self.target_zone_id]
            target_count = min(
                self.config.failures.replenishment_gap.target_item_count,
                len(zone_slots),
            )
            self.target_slots = sorted(zone_slots, key=lambda slot: slot.item_id)[:target_count]

        if self.config.failures.selector_false_lead.enabled:
            selector_index = int(
                self.streams["failure_selector_exposure"].integers(0, len(self.selectors))
            )
            self.target_selector_id = str(self.selectors[selector_index]["operator_id"])
            peer_ids = [
                str(selector["operator_id"])
                for selector in self.selectors
                if str(selector["operator_id"]) != self.target_selector_id
            ]
            self.exposed_peer_selector_ids = peer_ids[:3]

    @property
    def enabled(self) -> bool:
        return self.config.failures.any_enabled

    def choose_trip_zone(self, trip_index: int, normal_zone: Any) -> Any:
        if (
            self.config.failures.replenishment_gap.enabled
            and self.target_zone_id is not None
            and trip_index <= self.config.failures.selector_false_lead.exposure_trip_count
        ):
            for zone in self.zones:
                if str(zone["zone_id"]) == self.target_zone_id:
                    return zone
        return normal_zone

    def choose_selector(self, trip_index: int, normal_selector: Any) -> Any:
        if (
            self.config.failures.selector_false_lead.enabled
            and self.target_selector_id is not None
            and trip_index <= self.config.failures.selector_false_lead.exposure_trip_count
        ):
            for selector in self.selectors:
                if str(selector["operator_id"]) == self.target_selector_id:
                    return selector
        if (
            self.config.failures.selector_false_lead.enabled
            and self.exposed_peer_selector_ids
            and trip_index
            <= self.config.failures.selector_false_lead.exposure_trip_count
            + len(self.exposed_peer_selector_ids)
        ):
            peer_id = self.exposed_peer_selector_ids[
                (trip_index - self.config.failures.selector_false_lead.exposure_trip_count - 1)
                % len(self.exposed_peer_selector_ids)
            ]
            for selector in self.selectors:
                if str(selector["operator_id"]) == peer_id:
                    return selector
        return normal_selector

    def choose_slot(
        self,
        *,
        trip_index: int,
        line_index: int,
        normal_slot: _SlotPlan,
    ) -> _SlotPlan:
        if (
            self.config.failures.replenishment_gap.enabled
            and self.target_slots
            and trip_index <= self.config.failures.selector_false_lead.exposure_trip_count
        ):
            return self.target_slots[(trip_index + line_index - 2) % len(self.target_slots)]
        return normal_slot

    def skip_pre_pick_replenishment(self, slot: _SlotPlan) -> bool:
        return (
            self.config.failures.replenishment_gap.enabled
            and slot in self.target_slots
            and self.pattern_a_short_count
            < self.config.failures.replenishment_gap.forced_short_count
        )

    def should_force_short(self, slot: _SlotPlan) -> bool:
        return (
            self.config.failures.replenishment_gap.enabled
            and slot in self.target_slots
            and self.pattern_a_short_count
            < self.config.failures.replenishment_gap.forced_short_count
        )

    def record_pick(self, pick_id: str, selector_id: str, slot: _SlotPlan, short_qty: int) -> None:
        if slot in self.target_slots and short_qty > 0:
            if (
                self.pattern_a_short_count
                < self.config.failures.replenishment_gap.forced_short_count
            ):
                self.pattern_a_short_count += 1
                self.pattern_a_pick_ids.append(pick_id)
            if selector_id == self.target_selector_id:
                self.pattern_c_pick_ids.append(pick_id)

    def record_trip(self, trip_id: str, selector_id: str) -> None:
        if selector_id == self.target_selector_id:
            self.pattern_c_trip_ids.append(trip_id)

    def should_record_masked_damage(self, slot: _SlotPlan, pick_count: int) -> bool:
        return (
            self.config.failures.qa_masking.enabled
            and self.pattern_b_count < self.config.failures.qa_masking.event_count
            and slot.fragility_score >= 0.5
            and pick_count % 11 == 0
        )

    def ground_truth(self, run_id: str, config_hash: str) -> dict[str, Any]:
        return {
            "config_hash": config_hash,
            "enabled_patterns": {
                "qa_masking": self.config.failures.qa_masking.enabled,
                "replenishment_gap": self.config.failures.replenishment_gap.enabled,
                "selector_false_lead": self.config.failures.selector_false_lead.enabled,
            },
            "ground_truth_schema_version": "1.0.0",
            "patterns": {
                "qa_masking": {
                    "adjustment_ids": self.pattern_b_adjustment_ids,
                    "qa_event_ids": self.pattern_b_qa_ids,
                },
                "replenishment_gap": {
                    "affected_pick_event_ids": self.pattern_a_pick_ids,
                    "recovery_adjustment_ids": self.pattern_a_recovery_adjustment_ids,
                    "target_item_ids": [slot.item_id for slot in self.target_slots],
                    "target_zone_code": self.target_zone_code,
                    "target_zone_id": self.target_zone_id,
                },
                "selector_false_lead": {
                    "exposed_peer_selector_ids": self.exposed_peer_selector_ids,
                    "target_pick_event_ids": self.pattern_c_pick_ids,
                    "target_selector_id": self.target_selector_id,
                    "target_trip_ids": self.pattern_c_trip_ids,
                },
            },
            "run_id": run_id,
            "scenario_name": self.config.run.scenario_name,
            "scenario_version": self.config.run.scenario_version,
            "seed": self.config.run.seed,
        }


def generate_normal_operations(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    run_id: str,
) -> OperationGenerationCounts:
    """Generate deterministic normal Phase 2 transactions from opening state."""

    repository = OperationsRepository(connection)
    inputs = repository.trip_inputs(run_id)
    streams = create_named_random_streams(config.run.seed)
    state = SimulatorInventoryState(
        run_id=run_id,
        physical=repository.opening_system_state(run_id).copy(),
        system=repository.opening_system_state(run_id).copy(),
    )
    processor = StateTransitionProcessor(state)

    slots = [_slot_from_row(row) for row in inputs["slots"]]
    if not slots:
        raise DataValidationError("Phase 2 generation requires active slot assignments")

    reserve_by_item = _reserve_locations_by_item(slots, state.system)
    slots_by_zone = _slots_by_zone(slots)
    shifts = inputs["shifts"]
    selectors = inputs["selectors"]
    zones = inputs["zones"]
    replenishers = inputs["replenishers"]
    qa_operators = inputs["qa_operators"]
    inventory_control = inputs["inventory_control"]
    if not shifts or not selectors or not zones or not replenishers:
        raise DataValidationError(
            "Phase 2 generation requires shifts, selectors, zones, and replenishment operators"
        )
    overlay = _ScenarioOverlay(config, slots, zones, selectors, streams)

    system_events = _generate_system_events(repository, processor, config, zones)
    trip_count = config.operations.trip_count
    pick_count = 0
    replenishment_count = 0
    qa_count = 0
    adjustment_count = 0
    trip_spacing = (config.run.end_utc - config.run.start_utc) / (trip_count + 1)
    slot_offsets_by_zone = {str(row["zone_id"]): 0 for row in zones}

    for trip_index in range(1, trip_count + 1):
        zone = overlay.choose_trip_zone(trip_index, zones[(trip_index - 1) % len(zones)])
        zone_id = str(zone["zone_id"])
        zone_slots = slots_by_zone[zone_id]
        selector = overlay.choose_selector(trip_index, selectors[(trip_index - 1) % len(selectors)])
        shift = shifts[(trip_index - 1) % len(shifts)]
        planned_lines = _planned_lines(config, streams["operations_trips"])
        start_utc = config.run.start_utc + trip_spacing * trip_index
        end_utc = min(start_utc + timedelta(minutes=max(20, planned_lines * 4)), config.run.end_utc)
        trip = TripRecord(
            run_id=run_id,
            trip_id=generate_identifier("TRIP", trip_index),
            shift_id=str(shift["shift_id"]),
            selector_id=str(selector["operator_id"]),
            assigned_zone_id=zone_id,
            start_utc=_iso(start_utc),
            end_utc=_iso(end_utc),
            continuation_flag=0,
            planned_pick_lines=planned_lines,
            planned_cases=planned_lines * 2,
        )
        repository.insert_trip(trip)
        overlay.record_trip(trip.trip_id, trip.selector_id)

        for line_index in range(1, planned_lines + 1):
            slot_offset = slot_offsets_by_zone[zone_id]
            normal_slot = zone_slots[slot_offset % len(zone_slots)]
            slot_offsets_by_zone[zone_id] = slot_offset + 1
            slot = overlay.choose_slot(
                trip_index=trip_index,
                line_index=line_index,
                normal_slot=normal_slot,
            )
            event_utc = start_utc + timedelta(minutes=line_index * 3)
            if event_utc >= end_utc:
                event_utc = end_utc - timedelta(minutes=1)
            if not overlay.skip_pre_pick_replenishment(slot):
                replenishment_count += _replenish_if_needed(
                    repository,
                    processor,
                    slot,
                    reserve_by_item,
                    replenishers,
                    event_utc,
                    replenishment_count,
                )
            requested_qty = 1 + int(streams["operations_picks"].integers(0, 2))
            force_short = streams[
                "operations_picks"
            ].random() < config.operations.short_probability or overlay.should_force_short(slot)
            pick_count += 1
            pick = processor.apply_pick(
                pick_event_id=generate_identifier("PICK", pick_count),
                trip_id=trip.trip_id,
                selector_id=trip.selector_id,
                item_id=slot.item_id,
                location_id=slot.pick_location_id,
                event_utc=event_utc,
                requested_qty_cases=requested_qty,
                force_short=force_short,
            )
            repository.insert_pick_event(pick)
            overlay.record_pick(
                pick.pick_event_id,
                pick.selector_id,
                slot,
                pick.short_qty_cases,
            )
            if (
                pick.short_qty_cases > 0
                and slot in overlay.target_slots
                and overlay.pattern_a_recovery_count
                < config.failures.replenishment_gap.recovery_adjustment_count
            ):
                adjustment_count += _record_scenario_recovery_adjustment(
                    repository,
                    processor,
                    slot,
                    inventory_control,
                    event_utc + timedelta(seconds=45),
                    adjustment_count,
                    overlay,
                )

            if qa_count < config.operations.qa_event_count and pick_count % 17 == 0:
                qa_count += _record_quality_event(
                    repository,
                    processor,
                    slot,
                    qa_operators,
                    event_utc + timedelta(minutes=1),
                    qa_count,
                    damage=False,
                )
            if overlay.should_record_masked_damage(slot, pick_count):
                qa_added = _record_quality_event(
                    repository,
                    processor,
                    slot,
                    qa_operators,
                    event_utc + timedelta(minutes=1),
                    qa_count,
                    damage=True,
                )
                if qa_added:
                    qa_count += qa_added
                    overlay.pattern_b_count += 1
                    overlay.pattern_b_qa_ids.append(generate_identifier("QA", qa_count))
                    adjustment_added = _record_masked_damage_adjustment(
                        repository,
                        processor,
                        slot,
                        inventory_control,
                        event_utc + timedelta(minutes=2),
                        adjustment_count,
                    )
                    if adjustment_added:
                        adjustment_count += adjustment_added
                        overlay.pattern_b_adjustment_ids.append(
                            generate_identifier("ADJ", adjustment_count)
                        )
            if adjustment_count < config.operations.adjustment_count and pick_count % 29 == 0:
                adjustment_count += _record_count_adjustment(
                    repository,
                    processor,
                    slot,
                    inventory_control,
                    event_utc + timedelta(minutes=2),
                    adjustment_count,
                )
            if qa_count < config.operations.qa_event_count and pick_count % 43 == 0:
                qa_count += _record_quality_event(
                    repository,
                    processor,
                    slot,
                    qa_operators,
                    event_utc + timedelta(minutes=1),
                    qa_count,
                    damage=True,
                )
                adjustment_count += _record_damage_adjustment(
                    repository,
                    processor,
                    slot,
                    inventory_control,
                    event_utc + timedelta(minutes=3),
                    adjustment_count,
                )

    while qa_count < config.operations.qa_event_count:
        slot = slots[qa_count % len(slots)]
        occurred_utc = config.run.end_utc - timedelta(minutes=60 - qa_count)
        qa_count += _record_quality_event(
            repository,
            processor,
            slot,
            qa_operators,
            occurred_utc,
            qa_count,
            damage=qa_count < config.operations.damage_event_count,
        )
        if adjustment_count < config.operations.adjustment_count:
            adjustment_count += _record_damage_adjustment(
                repository,
                processor,
                slot,
                inventory_control,
                occurred_utc + timedelta(minutes=2),
                adjustment_count,
            )

    while adjustment_count < config.operations.adjustment_count:
        slot = slots[adjustment_count % len(slots)]
        adjustment_count += _record_count_adjustment(
            repository,
            processor,
            slot,
            inventory_control,
            config.run.end_utc - timedelta(minutes=30 - adjustment_count),
            adjustment_count,
        )

    closing_snapshots = _write_closing_snapshots(repository, config, run_id, state.system)
    return OperationGenerationCounts(
        trips=trip_count,
        pick_events=pick_count,
        replenishment_tasks=replenishment_count,
        qa_events=qa_count,
        inventory_adjustments=adjustment_count,
        system_events=system_events,
        closing_snapshots=closing_snapshots,
        scenario_ground_truth=overlay.ground_truth(run_id, config.configuration_hash),
    )


def _generate_system_events(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    config: ProjectConfig,
    zones: list[Any],
) -> int:
    count = min(config.operations.system_event_count, max(0, len(zones) * 2))
    for index in range(1, count + 1):
        zone = zones[(index - 1) % len(zones)]
        start_utc = config.run.start_utc + timedelta(minutes=15 * index)
        event = processor.record_system_event(
            system_event_id=generate_identifier("SYS", index),
            event_type="RF_DELAY" if index % 2 else "EQUIPMENT_DELAY",
            zone_id=str(zone["zone_id"]),
            location_id=None,
            equipment_area=f"{str(zone['zone_code']).lower()}-area",
            start_utc=start_utc,
            end_utc=start_utc + timedelta(minutes=8 + index),
            severity_code="LOW" if index % 3 else "MEDIUM",
        )
        repository.insert_system_event(event)
    return count


def _replenish_if_needed(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    slot: _SlotPlan,
    reserve_by_item: dict[str, str],
    replenishers: list[Any],
    pick_utc: datetime,
    replenishment_count: int,
) -> int:
    current_system = processor.state.system_quantity(slot.item_id, slot.pick_location_id)
    if current_system > slot.reorder_trigger_cases:
        return 0
    source_location_id = reserve_by_item.get(slot.item_id)
    if source_location_id is None:
        return 0
    source_qty = processor.state.system_quantity(slot.item_id, source_location_id)
    if source_qty <= 0:
        return 0
    requested = min(slot.target_cases - current_system, source_qty)
    if requested <= 0:
        return 0
    index = replenishment_count + 1
    event = processor.apply_replenishment(
        replenishment_task_id=generate_identifier("REPL", index),
        item_id=slot.item_id,
        source_location_id=source_location_id,
        destination_location_id=slot.pick_location_id,
        operator_id=str(replenishers[(index - 1) % len(replenishers)]["operator_id"]),
        created_utc=pick_utc - timedelta(minutes=3),
        requested_qty_cases=requested,
    )
    repository.insert_replenishment_task(event)
    return 1


def _record_quality_event(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    slot: _SlotPlan,
    qa_operators: list[Any],
    occurred_utc: datetime,
    qa_count: int,
    *,
    damage: bool,
) -> int:
    if not qa_operators:
        return 0
    physical_quantity = processor.state.physical_quantity(slot.item_id, slot.pick_location_id)
    if physical_quantity <= 0:
        return 0
    quantity = max(1, min(1 + int(slot.fragility_score * 2), physical_quantity))
    index = qa_count + 1
    event = processor.apply_qa_event(
        qa_event_id=generate_identifier("QA", index),
        item_id=slot.item_id,
        location_id=slot.pick_location_id,
        operator_id=str(qa_operators[(index - 1) % len(qa_operators)]["operator_id"]),
        occurred_utc=occurred_utc,
        qty_affected_cases=quantity,
        damage=damage,
    )
    repository.insert_qa_event(event)
    return 1


def _record_damage_adjustment(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    slot: _SlotPlan,
    inventory_control: list[Any],
    effective_utc: datetime,
    adjustment_count: int,
) -> int:
    if processor.state.system_quantity(slot.item_id, slot.pick_location_id) <= 0:
        return 0
    index = adjustment_count + 1
    event = processor.apply_adjustment(
        adjustment_id=generate_identifier("ADJ", index),
        item_id=slot.item_id,
        location_id=slot.pick_location_id,
        operator_id=_optional_operator(inventory_control, index),
        effective_utc=effective_utc,
        qty_delta_cases=-1,
        reason_code="DAMAGE_DISPOSAL",
        reference_code=f"QA-{index:04d}",
    )
    repository.insert_inventory_adjustment(event)
    return 1


def _record_masked_damage_adjustment(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    slot: _SlotPlan,
    inventory_control: list[Any],
    effective_utc: datetime,
    adjustment_count: int,
) -> int:
    if processor.state.system_quantity(slot.item_id, slot.pick_location_id) <= 0:
        return 0
    index = adjustment_count + 1
    event = processor.apply_adjustment(
        adjustment_id=generate_identifier("ADJ", index),
        item_id=slot.item_id,
        location_id=slot.pick_location_id,
        operator_id=_optional_operator(inventory_control, index),
        effective_utc=effective_utc,
        qty_delta_cases=-1,
        reason_code="COUNT_CORRECTION",
        reference_code="variance_review",
    )
    repository.insert_inventory_adjustment(event)
    return 1


def _record_scenario_recovery_adjustment(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    slot: _SlotPlan,
    inventory_control: list[Any],
    effective_utc: datetime,
    adjustment_count: int,
    overlay: _ScenarioOverlay,
) -> int:
    index = adjustment_count + 1
    event = processor.apply_adjustment(
        adjustment_id=generate_identifier("ADJ", index),
        item_id=slot.item_id,
        location_id=slot.pick_location_id,
        operator_id=_optional_operator(inventory_control, index),
        effective_utc=effective_utc,
        qty_delta_cases=1,
        reason_code="FOUND_PRODUCT",
        reference_code="slot_recount",
    )
    repository.insert_inventory_adjustment(event)
    overlay.pattern_a_recovery_count += 1
    overlay.pattern_a_recovery_adjustment_ids.append(event.adjustment_id)
    return 1


def _record_count_adjustment(
    repository: OperationsRepository,
    processor: StateTransitionProcessor,
    slot: _SlotPlan,
    inventory_control: list[Any],
    effective_utc: datetime,
    adjustment_count: int,
) -> int:
    index = adjustment_count + 1
    delta = 1 if index % 2 else -1
    if delta < 0 and processor.state.system_quantity(slot.item_id, slot.pick_location_id) <= 0:
        delta = 1
    event = processor.apply_adjustment(
        adjustment_id=generate_identifier("ADJ", index),
        item_id=slot.item_id,
        location_id=slot.pick_location_id,
        operator_id=_optional_operator(inventory_control, index),
        effective_utc=effective_utc,
        qty_delta_cases=delta,
        reason_code="FOUND_PRODUCT" if delta > 0 else "COUNT_CORRECTION",
        reference_code="baseline_count",
    )
    repository.insert_inventory_adjustment(event)
    return 1


def _write_closing_snapshots(
    repository: OperationsRepository,
    config: ProjectConfig,
    run_id: str,
    system_state: dict[tuple[str, str], int],
) -> int:
    index = 1
    for (item_id, location_id), quantity in sorted(system_state.items()):
        repository.insert_inventory_snapshot(
            InventorySnapshotRecord(
                run_id=run_id,
                snapshot_id=generate_identifier("CLOSE", index),
                snapshot_utc=_iso(config.run.end_utc),
                snapshot_type="CLOSING_SYSTEM",
                item_id=item_id,
                location_id=location_id,
                handling_unit_id=None,
                qty_cases=quantity,
                source_code="phase2_closing",
            )
        )
        index += 1
    return index - 1


def _planned_lines(config: ProjectConfig, rng: Any) -> int:
    low = config.operations.pick_lines_per_trip_min
    high = config.operations.pick_lines_per_trip_max
    return int(rng.integers(low, high + 1))


def _slot_from_row(row: Any) -> _SlotPlan:
    return _SlotPlan(
        item_id=str(row["item_id"]),
        pick_location_id=str(row["pick_location_id"]),
        reorder_trigger_cases=int(row["reorder_trigger_cases"]),
        target_cases=int(row["target_cases"]),
        maximum_cases=int(row["maximum_cases"]),
        velocity_class=str(row["velocity_class"]),
        fragility_score=float(row["fragility_score"]),
        zone_id=str(row["zone_id"]),
        zone_code=str(row["zone_code"]),
    )


def _reserve_locations_by_item(
    slots: list[_SlotPlan], system_state: dict[tuple[str, str], int]
) -> dict[str, str]:
    pick_locations = {slot.pick_location_id for slot in slots}
    reserve_by_item: dict[str, str] = {}
    for item_id, location_id in sorted(system_state):
        if location_id not in pick_locations and system_state[(item_id, location_id)] > 0:
            reserve_by_item.setdefault(item_id, location_id)
    return reserve_by_item


def _slots_by_zone(slots: list[_SlotPlan]) -> dict[str, list[_SlotPlan]]:
    by_zone: dict[str, list[_SlotPlan]] = {}
    velocity_order = {"A": 0, "B": 1, "C": 2}
    for slot in slots:
        by_zone.setdefault(slot.zone_id, []).append(slot)
    for zone_slots in by_zone.values():
        zone_slots.sort(key=lambda slot: (velocity_order.get(slot.velocity_class, 9), slot.item_id))
    return by_zone


def _optional_operator(operators: list[Any], index: int) -> str | None:
    if not operators:
        return None
    return str(operators[(index - 1) % len(operators)]["operator_id"])


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
