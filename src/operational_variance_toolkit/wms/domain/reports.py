"""Stable schema-3 WMS report definitions and results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ReportSpec:
    code: str
    name: str
    columns: tuple[str, ...]
    parameters: frozenset[str] = frozenset()
    required_parameters: frozenset[str] = frozenset()

    @property
    def display_columns(self) -> tuple[str, ...]:
        """Return owner-facing headings without changing canonical field names."""

        return tuple(
            _REPORT_LABELS.get((self.code, column), _COMMON_LABELS.get(column, column))
            for column in self.columns
        )


@dataclass(frozen=True, slots=True)
class ReportResult:
    spec: ReportSpec
    database_path: Path
    run_id: str
    schema_version: str
    as_of_utc: str
    generated_at_utc: str
    parameters: Mapping[str, str]
    rows: tuple[tuple[object, ...], ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)


_COMMON_FILTERS = frozenset({"item", "location", "operator", "start_utc", "end_utc"})

_COMMON_LABELS = {
    "item_id": "Item ID",
}

_REPORT_LABELS = {
    ("location-profile", "occupied_flag"): "Recorded Occupied",
    ("empty-locations", "empty_location_classification"): "Empty Location Classification",
    (
        "replenishment-needs",
        "compatible_reserve_qty_cases",
    ): "Recorded Compatible Reserve Quantity",
    ("inventory-transaction-inquiry", "event_utc"): "Operational Event Time",
    ("inventory-transaction-inquiry", "recorded_utc"): "WMS Recorded Time",
    ("inventory-transaction-inquiry", "source_record_id"): "Source Reference",
    ("adjustment-history", "effective_utc"): "Operational Event Time",
    ("adjustment-history", "recorded_utc"): "WMS Recorded Time",
    ("adjustment-history", "reference_code"): "Source Reference",
    ("qa-activity", "qty_affected_cases"): "QA Observed Quantity",
    ("qa-activity", "occurred_utc"): "Operational Event Time",
    ("qa-activity", "recorded_utc"): "WMS Recorded Time",
}

_SPECS = (
    ReportSpec(
        "inventory-by-location",
        "Inventory by Location",
        (
            "location_id",
            "zone_code",
            "location_type",
            "aisle_code",
            "bay_number",
            "level_number",
            "position_number",
            "pallet_capacity",
            "pickable_flag",
            "active_flag",
            "item_id",
            "item_description",
            "qty_on_hand_cases",
            "code_date",
            "cases_per_pallet",
            "calculated_physical_maximum_cases",
            "available_capacity_cases",
            "occupancy_percentage",
            "minimum_qty_cases",
            "reorder_trigger_cases",
            "target_qty_cases",
            "maximum_qty_cases",
            "last_transaction_id",
            "last_updated_utc",
        ),
    ),
    ReportSpec(
        "inventory-by-item",
        "Inventory by Item",
        (
            "item_id",
            "item_description",
            "required_zone_code",
            "velocity_class",
            "total_on_hand_cases",
            "pick_cases",
            "reserve_cases",
            "occupied_location_count",
            "earliest_code_date",
            "latest_update_utc",
            "cases_per_pallet",
            "pallet_equivalent_qty",
        ),
        frozenset({"item"}),
    ),
    ReportSpec(
        "location-profile",
        "Location Profile",
        (
            "location_id",
            "zone_code",
            "location_type",
            "aisle_code",
            "bay_number",
            "level_number",
            "position_number",
            "pallet_capacity",
            "pickable_flag",
            "active_flag",
            "current_item_id",
            "current_qty_on_hand_cases",
            "occupied_flag",
        ),
        frozenset({"location"}),
    ),
    ReportSpec(
        "empty-locations",
        "Empty Locations",
        (
            "location_id",
            "zone_code",
            "location_type",
            "aisle_code",
            "bay_number",
            "level_number",
            "position_number",
            "pallet_capacity",
            "assigned_item_id",
            "empty_location_classification",
            "active_flag",
            "pickable_flag",
            "last_updated_utc",
        ),
    ),
    ReportSpec(
        "code-date-inventory",
        "Code-Date Inventory",
        (
            "item_id",
            "item_description",
            "location_id",
            "qty_on_hand_cases",
            "code_date",
            "days_to_code_date",
            "zone_code",
            "velocity_class",
            "category",
        ),
        frozenset({"item", "location", "as_of_date"}),
        frozenset({"as_of_date"}),
    ),
    ReportSpec(
        "replenishment-needs",
        "Replenishment Needs",
        (
            "item_id",
            "location_id",
            "qty_on_hand_cases",
            "minimum_qty_cases",
            "reorder_trigger_cases",
            "target_qty_cases",
            "maximum_qty_cases",
            "recommended_qty_cases",
            "compatible_reserve_qty_cases",
            "velocity_class",
            "open_task_id",
            "open_task_status",
            "oldest_open_task_age_hours",
        ),
        frozenset({"as_of_utc"}),
    ),
    ReportSpec(
        "open-replenishment-tasks",
        "Open Replenishment Tasks",
        (
            "replenishment_task_id",
            "item_id",
            "source_location_id",
            "destination_location_id",
            "status",
            "operator_id",
            "requested_qty_cases",
            "created_utc",
            "started_utc",
            "age_hours",
            "source_qty_on_hand_cases",
            "destination_qty_on_hand_cases",
            "delay_reason_code",
        ),
        frozenset({"item", "operator", "as_of_utc"}),
    ),
    ReportSpec(
        "inventory-transaction-inquiry",
        "Inventory Transaction Inquiry",
        (
            "transaction_id",
            "transaction_group_id",
            "command_id",
            "event_sequence",
            "line_number",
            "transaction_type",
            "item_id",
            "location_id",
            "related_location_id",
            "qty_delta_cases",
            "balance_before_cases",
            "balance_after_cases",
            "operator_id",
            "event_utc",
            "recorded_utc",
            "reason_code",
            "source_record_type",
            "source_record_id",
        ),
        _COMMON_FILTERS | frozenset({"transaction_group", "source_record"}),
    ),
    ReportSpec(
        "adjustment-history",
        "Adjustment History",
        (
            "adjustment_id",
            "item_id",
            "location_id",
            "qty_delta_cases",
            "reason_code",
            "operator_id",
            "effective_utc",
            "recorded_utc",
            "balance_before_cases",
            "balance_after_cases",
            "reference_code",
            "transaction_id",
            "command_id",
        ),
        _COMMON_FILTERS,
    ),
    ReportSpec(
        "qa-activity",
        "QA Activity",
        (
            "qa_event_id",
            "item_id",
            "location_id",
            "event_type",
            "qty_affected_cases",
            "operator_id",
            "occurred_utc",
            "recorded_utc",
            "reason_code",
            "disposition_code",
            "command_id",
            "event_sequence",
        ),
        _COMMON_FILTERS,
    ),
    ReportSpec(
        "inventory-snapshot",
        "Recorded Inventory Snapshot",
        (
            "snapshot_batch_id",
            "snapshot_type",
            "snapshot_utc",
            "location_id",
            "item_id",
            "qty_on_hand_cases",
            "code_date",
            "last_transaction_id",
        ),
        frozenset({"snapshot_batch"}),
        frozenset({"snapshot_batch"}),
    ),
    ReportSpec(
        "inventory-reconciliation",
        "Live-versus-Snapshot Reconciliation",
        (
            "location_id",
            "item_id",
            "live_qty_on_hand_cases",
            "snapshot_batch_id",
            "snapshot_utc",
            "snapshot_qty_on_hand_cases",
            "live_snapshot_difference_cases",
            "status",
        ),
        frozenset({"snapshot_batch"}),
        frozenset({"snapshot_batch"}),
    ),
)

REPORT_SPECS: Mapping[str, ReportSpec] = MappingProxyType({spec.code: spec for spec in _SPECS})
