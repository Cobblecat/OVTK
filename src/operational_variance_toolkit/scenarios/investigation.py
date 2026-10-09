"""Controlled investigation policy layered over the ordinary baseline protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.generation.random_source import create_named_random_streams
from operational_variance_toolkit.simulation.physical import PhysicalPickResult
from operational_variance_toolkit.simulation.policy import (
    PolicyAdjustment,
    PostPickPolicy,
    QaPolicy,
    StandardDriverPolicy,
)
from operational_variance_toolkit.simulation.read_model import BaselineInputs, SlotPlan


@dataclass(slots=True)
class InvestigationPolicy(StandardDriverPolicy):
    """Schedule controlled mechanisms without changing WMS behavior."""

    config: ProjectConfig
    inputs: BaselineInputs
    target_zone_id: str | None = None
    target_zone_code: str | None = None
    target_slots: tuple[SlotPlan, ...] = ()
    target_selector_id: str | None = None
    exposed_peer_selector_ids: tuple[str, ...] = ()
    affected_pick_event_ids: list[str] = field(default_factory=list)
    delayed_replenishment_task_ids: list[str] = field(default_factory=list)
    recovery_adjustment_ids: list[str] = field(default_factory=list)
    masked_qa_event_ids: list[str] = field(default_factory=list)
    masked_adjustment_ids: list[str] = field(default_factory=list)
    target_trip_ids: list[str] = field(default_factory=list)
    target_pick_event_ids: list[str] = field(default_factory=list)
    _delayed_timing: dict[str, dict[str, str | None]] = field(default_factory=dict)
    _target_exposure_active: bool = False
    _pattern_a_recovered: bool = False

    def __post_init__(self) -> None:
        streams = create_named_random_streams(
            self.config.run.seed,
            ("failure_replenishment_gap", "failure_selector_exposure"),
        )
        if self.config.failures.replenishment_gap.enabled:
            zone_index = int(
                streams["failure_replenishment_gap"].integers(0, len(self.inputs.zone_ids))
            )
            self.target_zone_id = self.inputs.zone_ids[zone_index]
            candidates = tuple(
                slot
                for slot in self.inputs.slots
                if slot.zone_id == self.target_zone_id and slot.velocity_class == "A"
            )
            if not candidates:
                candidates = tuple(
                    slot for slot in self.inputs.slots if slot.zone_id == self.target_zone_id
                )
            target_count = min(
                self.config.failures.replenishment_gap.target_item_count,
                len(candidates),
            )
            self.target_slots = tuple(sorted(candidates, key=lambda slot: slot.item_id))[
                :target_count
            ]
            if not self.target_slots:
                raise DataValidationError("Investigation requires targetable pick slots")
            self.target_zone_code = self.target_slots[0].zone_code

        if self.config.failures.selector_false_lead.enabled:
            selector_index = int(
                streams["failure_selector_exposure"].integers(0, len(self.inputs.selectors))
            )
            self.target_selector_id = self.inputs.selectors[selector_index]
            peers = tuple(
                selector
                for selector in self.inputs.selectors
                if selector != self.target_selector_id
            )
            self.exposed_peer_selector_ids = peers[:3]

    def trip_zone(self, trip_index: int, default_zone_id: str) -> str:
        del trip_index
        if self._pattern_a_active and self.target_zone_id is not None:
            return self.target_zone_id
        return default_zone_id

    def trip_selector(self, trip_index: int, default_selector_id: str) -> str:
        exposure_count = self.config.failures.selector_false_lead.exposure_trip_count
        if self.target_selector_id is not None and trip_index <= exposure_count:
            self._target_exposure_active = True
            return self.target_selector_id
        self._target_exposure_active = False
        if self.exposed_peer_selector_ids and exposure_count < trip_index <= exposure_count + len(
            self.exposed_peer_selector_ids
        ):
            return self.exposed_peer_selector_ids[trip_index - exposure_count - 1]
        return default_selector_id

    def slot(self, trip_index: int, line_index: int, default_slot: SlotPlan) -> SlotPlan:
        if self._pattern_a_active and self.target_slots:
            return self.target_slots[(trip_index + line_index - 2) % len(self.target_slots)]
        return default_slot

    def requested_quantity(self, slot: SlotPlan, default_quantity: int) -> int:
        if self._pattern_a_active and slot in self.target_slots:
            return max(4, default_quantity)
        return default_quantity

    def force_short(self, slot: SlotPlan, default_force_short: bool) -> bool:
        if self._pattern_a_active and slot in self.target_slots:
            return True
        return default_force_short

    def movement_mode(self, slot: SlotPlan) -> str:
        if self._pattern_a_active and slot in self.target_slots:
            return "recorded_before_physical"
        return "coordinated"

    def after_replenishment(
        self,
        task_id: str,
        slot: SlotPlan,
        movement_mode: str,
        confirmed_utc: datetime,
    ) -> None:
        if movement_mode == "recorded_before_physical" and slot in self.target_slots:
            self.delayed_replenishment_task_ids.append(task_id)
            self._delayed_timing[task_id] = {
                "physical_completed_utc": None,
                "replenishment_task_id": task_id,
                "wms_confirmed_utc": _iso_utc(confirmed_utc),
            }

    def after_physical_movement(self, task_id: str, completed_utc: datetime) -> None:
        try:
            evidence = self._delayed_timing[task_id]
        except KeyError as exc:
            raise DataValidationError(
                f"Unknown delayed replenishment physical completion: {task_id}"
            ) from exc
        evidence["physical_completed_utc"] = _iso_utc(completed_utc)

    def after_trip(self, trip_id: str, selector_id: str) -> None:
        if self._target_exposure_active and selector_id == self.target_selector_id:
            self.target_trip_ids.append(trip_id)

    def after_pick(
        self,
        pick_id: str,
        selector_id: str,
        slot: SlotPlan,
        result: PhysicalPickResult,
    ) -> PostPickPolicy:
        if self._target_exposure_active and selector_id == self.target_selector_id:
            self.target_pick_event_ids.append(pick_id)
        if self._pattern_a_active and slot in self.target_slots and result.short_qty_cases > 0:
            self.affected_pick_event_ids.append(pick_id)
        target = self.config.failures.replenishment_gap.forced_short_count
        if self._pattern_a_active and len(self.affected_pick_event_ids) >= target:
            self._pattern_a_recovered = True
            recoveries = tuple(
                PolicyAdjustment(
                    slot=self.target_slots[index % len(self.target_slots)],
                    qty_delta_cases=1,
                    reason_code="FOUND_PRODUCT",
                    tracking_key=f"pattern-a-recovery-{index + 1}",
                )
                for index in range(self.config.failures.replenishment_gap.recovery_adjustment_count)
            )
            return PostPickPolicy(True, recoveries)
        return PostPickPolicy()

    def qa_target_count(self, default_count: int) -> int:
        if not self.config.failures.qa_masking.enabled:
            return default_count
        return default_count + self.config.failures.qa_masking.event_count

    def adjustment_target_count(self, default_count: int) -> int:
        target = default_count
        if self.config.failures.replenishment_gap.enabled:
            target += self.config.failures.replenishment_gap.recovery_adjustment_count
        if self.config.failures.qa_masking.enabled:
            target += min(
                self.config.failures.qa_masking.event_count,
                self.config.failures.qa_masking.generic_adjustment_count,
            )
        return target

    def qa_policy(self, qa_index: int, default_damage: bool, slot: SlotPlan) -> QaPolicy:
        if not self.config.failures.qa_masking.enabled:
            return StandardDriverPolicy.qa_policy(self, qa_index, default_damage, slot)
        masked_count = min(
            self.config.failures.qa_masking.event_count,
            self.config.failures.qa_masking.generic_adjustment_count,
        )
        if qa_index <= masked_count:
            return QaPolicy(
                physical_damage=True,
                event_type="DAMAGE_FOUND",
                reason_code="DAMAGED_CASE",
                disposition_code="DISPOSE",
                adjustment_reason_code="COUNT_CORRECTION",
                tracking_key=f"pattern-b-{qa_index}",
            )
        baseline_index = qa_index - masked_count
        baseline_damage = baseline_index <= self.config.operations.damage_event_count
        return StandardDriverPolicy.qa_policy(self, baseline_index, baseline_damage, slot)

    def after_qa(
        self, tracking_key: str | None, qa_event_id: str, adjustment_id: str | None
    ) -> None:
        if tracking_key is None:
            return
        self.masked_qa_event_ids.append(qa_event_id)
        if adjustment_id is None:
            raise DataValidationError("Masked QA event requires a generic adjustment")
        self.masked_adjustment_ids.append(adjustment_id)

    def after_adjustment(self, tracking_key: str | None, adjustment_id: str) -> None:
        if tracking_key is not None and tracking_key.startswith("pattern-a-recovery-"):
            self.recovery_adjustment_ids.append(adjustment_id)

    def ground_truth(self, run_id: str, config_hash: str) -> dict[str, Any]:
        return {
            "artifact_type": "restricted_ground_truth",
            "config_hash": config_hash,
            "enabled_patterns": {
                "qa_masking": self.config.failures.qa_masking.enabled,
                "replenishment_gap": self.config.failures.replenishment_gap.enabled,
                "selector_false_lead": self.config.failures.selector_false_lead.enabled,
            },
            "ground_truth_schema_version": "2.0.0",
            "patterns": {
                "qa_masking": {
                    "adjustment_ids": self.masked_adjustment_ids,
                    "qa_event_ids": self.masked_qa_event_ids,
                },
                "replenishment_gap": {
                    "affected_pick_event_ids": self.affected_pick_event_ids,
                    "delayed_replenishment_task_ids": self.delayed_replenishment_task_ids,
                    "timing_evidence": list(self._delayed_timing.values()),
                    "recovery_adjustment_ids": self.recovery_adjustment_ids,
                    "target_item_ids": [slot.item_id for slot in self.target_slots],
                    "target_zone_code": self.target_zone_code,
                    "target_zone_id": self.target_zone_id,
                },
                "selector_false_lead": {
                    "exposed_peer_selector_ids": list(self.exposed_peer_selector_ids),
                    "target_pick_event_ids": self.target_pick_event_ids,
                    "target_selector_id": self.target_selector_id,
                    "target_trip_ids": self.target_trip_ids,
                },
            },
            "run_id": run_id,
            "scenario_name": self.config.run.scenario_name,
            "scenario_version": self.config.run.scenario_version,
            "seed": self.config.run.seed,
        }

    @property
    def _pattern_a_active(self) -> bool:
        return self.config.failures.replenishment_gap.enabled and not self._pattern_a_recovered


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
