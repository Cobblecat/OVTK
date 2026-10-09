"""Deterministic Phase 4 inventory reconstruction and context builders."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from operational_variance_toolkit.storage.schema import PHASE2_SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult

RECONSTRUCTION_VERSION = "1.0.0"

TableRecord = dict[str, Any]
TableRows = dict[str, list[TableRecord]]
InventoryKey = tuple[str, str]

INVENTORY_LEDGER_COLUMNS: tuple[str, ...] = (
    "run_id",
    "ledger_sequence",
    "event_sequence",
    "event_type",
    "source_table",
    "source_record_id",
    "source_line",
    "event_utc",
    "recorded_utc",
    "item_id",
    "location_id",
    "related_location_id",
    "operator_id",
    "trip_id",
    "quantity_delta_cases",
    "balance_before_cases",
    "balance_after_cases",
    "reason_code",
    "status_code",
    "source_evidence",
)

INVENTORY_RECONCILIATION_COLUMNS: tuple[str, ...] = (
    "run_id",
    "item_id",
    "location_id",
    "opening_qty_cases",
    "total_reconstructed_delta_cases",
    "reconstructed_closing_qty_cases",
    "reported_closing_qty_cases",
    "difference_cases",
    "reconciliation_status",
    "ledger_event_count",
    "pick_event_count",
    "replenishment_event_count",
    "adjustment_event_count",
    "opening_snapshot_count",
    "closing_snapshot_count",
)

PICK_CONTEXT_COLUMNS: tuple[str, ...] = (
    "run_id",
    "pick_event_id",
    "event_sequence",
    "trip_id",
    "selector_id",
    "shift_id",
    "shift_code",
    "operating_date_local",
    "item_id",
    "velocity_class",
    "fragility_score",
    "pick_location_id",
    "zone_id",
    "zone_code",
    "aisle_code",
    "event_utc",
    "recorded_utc",
    "requested_qty_cases",
    "picked_qty_cases",
    "short_qty_cases",
    "short_flag",
    "system_qty_before_cases",
    "system_qty_after_cases",
    "reconstructed_balance_before_cases",
    "reconstructed_balance_after_cases",
    "nearest_replenishment_task_id",
    "nearest_replenishment_completion_utc",
    "minutes_to_nearest_replenishment_completion",
    "active_replenishment_at_pick_flag",
    "recent_qa_event_count_4h",
    "recent_adjustment_count_4h",
    "recent_same_item_location_short_count_60m",
    "system_event_overlap_flag",
    "replenishment_adjacent_flag",
    "source_evidence",
)

REPLENISHMENT_CONTEXT_COLUMNS: tuple[str, ...] = (
    "run_id",
    "replenishment_task_id",
    "event_sequence",
    "status",
    "item_id",
    "velocity_class",
    "source_location_id",
    "destination_location_id",
    "destination_zone_id",
    "destination_zone_code",
    "destination_aisle_code",
    "operator_id",
    "created_utc",
    "started_utc",
    "confirmed_utc",
    "recorded_utc",
    "requested_qty_cases",
    "confirmed_qty_cases",
    "creation_to_start_minutes",
    "start_to_confirmation_minutes",
    "creation_to_confirmation_minutes",
    "pick_lines_during_creation_confirmation",
    "short_lines_during_creation_confirmation",
    "short_cases_during_creation_confirmation",
    "source_balance_before_cases",
    "source_balance_after_cases",
    "destination_balance_before_cases",
    "destination_balance_after_cases",
    "source_evidence",
)

QA_ADJUSTMENT_CONTEXT_COLUMNS: tuple[str, ...] = (
    "run_id",
    "qa_event_id",
    "adjustment_id",
    "qa_event_sequence",
    "adjustment_event_sequence",
    "item_id",
    "location_id",
    "qa_event_type",
    "qa_occurred_utc",
    "qa_recorded_utc",
    "qa_qty_affected_cases",
    "qa_reason_code",
    "qa_disposition_code",
    "adjustment_effective_utc",
    "adjustment_recorded_utc",
    "adjustment_qty_delta_cases",
    "adjustment_reason_code",
    "minutes_qa_to_adjustment",
    "relationship_rule",
    "compatible_quantity_direction_flag",
    "compatible_quantity_amount_flag",
    "source_evidence",
)

SELECTOR_EXPOSURE_COLUMNS: tuple[str, ...] = (
    "run_id",
    "selector_id",
    "trips",
    "pick_lines",
    "eligible_pick_lines",
    "requested_cases",
    "picked_cases",
    "short_lines",
    "short_cases",
    "high_velocity_pick_lines",
    "replenishment_adjacent_pick_lines",
    "ambient_pick_lines",
    "chilled_pick_lines",
    "frozen_pick_lines",
    "aisles_worked",
    "operating_dates_worked",
    "shifts_worked",
)

OUTPUT_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "inventory_event_ledger": INVENTORY_LEDGER_COLUMNS,
    "inventory_reconciliation": INVENTORY_RECONCILIATION_COLUMNS,
    "pick_context": PICK_CONTEXT_COLUMNS,
    "replenishment_context": REPLENISHMENT_CONTEXT_COLUMNS,
    "qa_adjustment_context": QA_ADJUSTMENT_CONTEXT_COLUMNS,
    "selector_exposure": SELECTOR_EXPOSURE_COLUMNS,
}

OUTPUT_FILE_NAMES: dict[str, str] = {
    "inventory_event_ledger": "inventory_event_ledger.csv",
    "inventory_reconciliation": "inventory_reconciliation.csv",
    "pick_context": "pick_context.csv",
    "replenishment_context": "replenishment_context.csv",
    "qa_adjustment_context": "qa_adjustment_context.csv",
    "selector_exposure": "selector_exposure.csv",
}

_SOURCE_TABLE_ORDER = {
    "pick_event": 10,
    "replenishment_task": 20,
    "inventory_adjustment": 30,
}

_SOURCE_LINE_ORDER = {
    "pick": 1,
    "source": 1,
    "destination": 2,
    "adjustment": 1,
}

_FORBIDDEN_HIDDEN_TOKENS = (
    "true_root_cause",
    "is_injected_anomaly",
    "physical_arrival",
    "scenario_target",
    "target_selector",
    "injected_pattern",
)


@dataclass(frozen=True, slots=True)
class ReconstructionSourceData:
    """Analyst-facing source rows needed by reconstruction."""

    run_id: str
    source_schema_version: str
    sqlite_user_version: int
    table_counts: Mapping[str, int]
    tables: Mapping[str, list[TableRecord]]


@dataclass(frozen=True, slots=True)
class ReconstructionTables:
    """Derived Phase 4 output tables."""

    tables: TableRows

    @property
    def row_counts(self) -> dict[str, int]:
        return {table_name: len(rows) for table_name, rows in self.tables.items()}


@dataclass(frozen=True, slots=True)
class _LedgerDraft:
    run_id: str
    event_sequence: int
    event_type: str
    source_table: str
    source_record_id: str
    source_line: str
    event_utc: str
    recorded_utc: str
    item_id: str
    location_id: str
    related_location_id: str | None
    operator_id: str | None
    trip_id: str | None
    quantity_delta_cases: int
    reason_code: str | None
    status_code: str | None
    source_evidence: str

    @property
    def sort_key(self) -> tuple[int, int, str, int]:
        return (
            self.event_sequence,
            _SOURCE_TABLE_ORDER[self.source_table],
            self.source_record_id,
            _SOURCE_LINE_ORDER[self.source_line],
        )


def build_reconstruction_tables(source: ReconstructionSourceData) -> ReconstructionTables:
    """Build all Phase 4 derived tables from analyst-facing source rows."""

    opening_totals, opening_counts = _snapshot_totals(source, "OPENING_SYSTEM")
    closing_totals, closing_counts = _snapshot_totals(source, "CLOSING_SYSTEM")
    ledger = _build_inventory_event_ledger(source, opening_totals)
    reconciliation = _build_inventory_reconciliation(
        source,
        opening_totals,
        opening_counts,
        closing_totals,
        closing_counts,
        ledger,
    )
    pick_context = _build_pick_context(source, ledger)
    replenishment_context = _build_replenishment_context(source, ledger)
    qa_adjustment_context = _build_qa_adjustment_context(source)
    selector_exposure = _build_selector_exposure(pick_context)
    return ReconstructionTables(
        tables={
            "inventory_event_ledger": ledger,
            "inventory_reconciliation": reconciliation,
            "pick_context": pick_context,
            "replenishment_context": replenishment_context,
            "qa_adjustment_context": qa_adjustment_context,
            "selector_exposure": selector_exposure,
        }
    )


def validate_reconstruction_tables(
    source: ReconstructionSourceData, derived: ReconstructionTables
) -> ValidationResult:
    """Validate source compatibility and derived reconstruction invariants."""

    failures: list[ValidationIssue] = []
    if source.sqlite_user_version != 2 or source.source_schema_version != PHASE2_SCHEMA_VERSION:
        failures.append(
            ValidationIssue(
                category="reconstruction",
                message=(
                    "reconstruction requires analyst schema 2.0.0 "
                    f"(found user_version={source.sqlite_user_version}, "
                    f"schema={source.source_schema_version})"
                ),
            )
        )

    ledger = derived.tables["inventory_event_ledger"]
    reconciliation = derived.tables["inventory_reconciliation"]
    _validate_ledger(source, ledger, failures)
    _validate_reconciliation(reconciliation, failures)
    _validate_output_ordering(derived, failures)
    _validate_hidden_truth_absence(derived, failures)
    return ValidationResult(tuple(failures))


def _build_inventory_event_ledger(
    source: ReconstructionSourceData, opening_totals: Mapping[InventoryKey, int]
) -> list[TableRecord]:
    balances = dict(opening_totals)
    rows: list[TableRecord] = []
    for ledger_sequence, draft in enumerate(
        sorted(_ledger_drafts(source), key=lambda item: item.sort_key), start=1
    ):
        key = (draft.item_id, draft.location_id)
        before = balances.get(key, 0)
        after = before + draft.quantity_delta_cases
        balances[key] = after
        rows.append(
            {
                "run_id": draft.run_id,
                "ledger_sequence": ledger_sequence,
                "event_sequence": draft.event_sequence,
                "event_type": draft.event_type,
                "source_table": draft.source_table,
                "source_record_id": draft.source_record_id,
                "source_line": draft.source_line,
                "event_utc": draft.event_utc,
                "recorded_utc": draft.recorded_utc,
                "item_id": draft.item_id,
                "location_id": draft.location_id,
                "related_location_id": draft.related_location_id,
                "operator_id": draft.operator_id,
                "trip_id": draft.trip_id,
                "quantity_delta_cases": draft.quantity_delta_cases,
                "balance_before_cases": before,
                "balance_after_cases": after,
                "reason_code": draft.reason_code,
                "status_code": draft.status_code,
                "source_evidence": draft.source_evidence,
            }
        )
    return rows


def _ledger_drafts(source: ReconstructionSourceData) -> list[_LedgerDraft]:
    drafts: list[_LedgerDraft] = []
    for row in source.tables["pick_event"]:
        picked_qty = int(row["picked_qty_cases"])
        if picked_qty <= 0:
            continue
        source_id = str(row["pick_event_id"])
        event_sequence = int(row["event_sequence"])
        drafts.append(
            _LedgerDraft(
                run_id=str(row["run_id"]),
                event_sequence=event_sequence,
                event_type="PICK",
                source_table="pick_event",
                source_record_id=source_id,
                source_line="pick",
                event_utc=str(row["event_utc"]),
                recorded_utc=str(row["recorded_utc"]),
                item_id=str(row["item_id"]),
                location_id=str(row["pick_location_id"]),
                related_location_id=None,
                operator_id=str(row["selector_id"]),
                trip_id=str(row["trip_id"]),
                quantity_delta_cases=-picked_qty,
                reason_code=_nullable_string(row["short_reason_code"]),
                status_code="ELIGIBLE" if int(row["eligible_pick_flag"]) else "INELIGIBLE",
                source_evidence=_source_evidence("pick_event", source_id, event_sequence, "pick"),
            )
        )

    for row in source.tables["replenishment_task"]:
        status = str(row["status"])
        confirmed_qty = int(row["confirmed_qty_cases"])
        if status != "CONFIRMED" or confirmed_qty <= 0:
            continue
        source_id = str(row["replenishment_task_id"])
        event_sequence = int(row["event_sequence"])
        confirmed_utc = str(row["confirmed_utc"])
        common = {
            "run_id": str(row["run_id"]),
            "event_sequence": event_sequence,
            "source_table": "replenishment_task",
            "source_record_id": source_id,
            "event_utc": confirmed_utc,
            "recorded_utc": str(row["recorded_utc"]),
            "item_id": str(row["item_id"]),
            "operator_id": _nullable_string(row["operator_id"]),
            "trip_id": None,
            "reason_code": _nullable_string(row["delay_reason_code"]),
            "status_code": status,
        }
        drafts.append(
            _LedgerDraft(
                **common,
                event_type="REPLENISHMENT_SOURCE",
                source_line="source",
                location_id=str(row["source_location_id"]),
                related_location_id=str(row["destination_location_id"]),
                quantity_delta_cases=-confirmed_qty,
                source_evidence=_source_evidence(
                    "replenishment_task", source_id, event_sequence, "source"
                ),
            )
        )
        drafts.append(
            _LedgerDraft(
                **common,
                event_type="REPLENISHMENT_DESTINATION",
                source_line="destination",
                location_id=str(row["destination_location_id"]),
                related_location_id=str(row["source_location_id"]),
                quantity_delta_cases=confirmed_qty,
                source_evidence=_source_evidence(
                    "replenishment_task", source_id, event_sequence, "destination"
                ),
            )
        )

    for row in source.tables["inventory_adjustment"]:
        source_id = str(row["adjustment_id"])
        event_sequence = int(row["event_sequence"])
        drafts.append(
            _LedgerDraft(
                run_id=str(row["run_id"]),
                event_sequence=event_sequence,
                event_type="ADJUSTMENT",
                source_table="inventory_adjustment",
                source_record_id=source_id,
                source_line="adjustment",
                event_utc=str(row["effective_utc"]),
                recorded_utc=str(row["recorded_utc"]),
                item_id=str(row["item_id"]),
                location_id=str(row["location_id"]),
                related_location_id=None,
                operator_id=_nullable_string(row["operator_id"]),
                trip_id=None,
                quantity_delta_cases=int(row["qty_delta_cases"]),
                reason_code=str(row["reason_code"]),
                status_code=None,
                source_evidence=_source_evidence(
                    "inventory_adjustment", source_id, event_sequence, "adjustment"
                ),
            )
        )
    return drafts


def _build_inventory_reconciliation(
    source: ReconstructionSourceData,
    opening_totals: Mapping[InventoryKey, int],
    opening_counts: Mapping[InventoryKey, int],
    closing_totals: Mapping[InventoryKey, int],
    closing_counts: Mapping[InventoryKey, int],
    ledger: list[TableRecord],
) -> list[TableRecord]:
    deltas: defaultdict[InventoryKey, int] = defaultdict(int)
    event_counts: defaultdict[InventoryKey, int] = defaultdict(int)
    pick_counts: defaultdict[InventoryKey, int] = defaultdict(int)
    replenishment_counts: defaultdict[InventoryKey, int] = defaultdict(int)
    adjustment_counts: defaultdict[InventoryKey, int] = defaultdict(int)

    for row in ledger:
        key = (str(row["item_id"]), str(row["location_id"]))
        deltas[key] += int(row["quantity_delta_cases"])
        event_counts[key] += 1
        event_type = str(row["event_type"])
        if event_type == "PICK":
            pick_counts[key] += 1
        elif event_type.startswith("REPLENISHMENT"):
            replenishment_counts[key] += 1
        elif event_type == "ADJUSTMENT":
            adjustment_counts[key] += 1

    keys = sorted(set(opening_totals) | set(closing_totals) | set(deltas))
    rows: list[TableRecord] = []
    for item_id, location_id in keys:
        opening_qty = int(opening_totals.get((item_id, location_id), 0))
        total_delta = int(deltas.get((item_id, location_id), 0))
        reconstructed_qty = opening_qty + total_delta
        reported_qty = int(closing_totals.get((item_id, location_id), 0))
        difference = reconstructed_qty - reported_qty
        rows.append(
            {
                "run_id": source.run_id,
                "item_id": item_id,
                "location_id": location_id,
                "opening_qty_cases": opening_qty,
                "total_reconstructed_delta_cases": total_delta,
                "reconstructed_closing_qty_cases": reconstructed_qty,
                "reported_closing_qty_cases": reported_qty,
                "difference_cases": difference,
                "reconciliation_status": "PASS" if difference == 0 else "FAIL",
                "ledger_event_count": event_counts.get((item_id, location_id), 0),
                "pick_event_count": pick_counts.get((item_id, location_id), 0),
                "replenishment_event_count": replenishment_counts.get((item_id, location_id), 0),
                "adjustment_event_count": adjustment_counts.get((item_id, location_id), 0),
                "opening_snapshot_count": opening_counts.get((item_id, location_id), 0),
                "closing_snapshot_count": closing_counts.get((item_id, location_id), 0),
            }
        )
    return rows


def _build_pick_context(
    source: ReconstructionSourceData, ledger: list[TableRecord]
) -> list[TableRecord]:
    items = _records_by_id(source.tables["item"], "item_id")
    locations = _records_by_id(source.tables["location"], "location_id")
    trips = _records_by_id(source.tables["trip"], "trip_id")
    pick_ledger = {
        str(row["source_record_id"]): row for row in ledger if row["source_table"] == "pick_event"
    }
    replenishments = [
        row
        for row in source.tables["replenishment_task"]
        if row["status"] == "CONFIRMED" and row["confirmed_utc"] is not None
    ]
    qa_events = source.tables["qa_event"]
    adjustments = source.tables["inventory_adjustment"]
    system_events = source.tables["system_event"]
    rows: list[TableRecord] = []
    ordered_picks = sorted(source.tables["pick_event"], key=lambda row: int(row["event_sequence"]))

    for row in ordered_picks:
        if int(row["eligible_pick_flag"]) != 1:
            continue
        pick_id = str(row["pick_event_id"])
        item_id = str(row["item_id"])
        location_id = str(row["pick_location_id"])
        pick_time = _parse_utc(str(row["event_utc"]))
        item = items[item_id]
        location = locations[location_id]
        trip = trips[str(row["trip_id"])]
        nearest = _nearest_replenishment(row, replenishments)
        nearest_minutes = "" if nearest is None else _signed_minutes(pick_time, nearest[1])
        ledger_row = pick_ledger.get(pick_id)
        balance_before = (
            int(ledger_row["balance_before_cases"])
            if ledger_row is not None
            else int(row["system_qty_before_cases"])
        )
        balance_after = (
            int(ledger_row["balance_after_cases"])
            if ledger_row is not None
            else int(row["system_qty_after_cases"])
        )
        recent_qa = _count_recent_events(
            qa_events,
            item_id,
            location_id,
            pick_time,
            time_column="occurred_utc",
            lookback=timedelta(hours=4),
        )
        recent_adjustments = _count_recent_events(
            adjustments,
            item_id,
            location_id,
            pick_time,
            time_column="effective_utc",
            lookback=timedelta(hours=4),
        )
        short_history = _count_recent_short_picks(ordered_picks, row, pick_time)
        active_replenishment = _active_replenishment_at_pick(row, replenishments, pick_time)
        rows.append(
            {
                "run_id": str(row["run_id"]),
                "pick_event_id": pick_id,
                "event_sequence": int(row["event_sequence"]),
                "trip_id": str(row["trip_id"]),
                "selector_id": str(row["selector_id"]),
                "shift_id": trip["shift_id"],
                "shift_code": trip["shift_code"],
                "operating_date_local": trip["operating_date_local"],
                "item_id": item_id,
                "velocity_class": item["velocity_class"],
                "fragility_score": item["fragility_score"],
                "pick_location_id": location_id,
                "zone_id": location["zone_id"],
                "zone_code": location["zone_code"],
                "aisle_code": location["aisle_code"],
                "event_utc": str(row["event_utc"]),
                "recorded_utc": str(row["recorded_utc"]),
                "requested_qty_cases": int(row["requested_qty_cases"]),
                "picked_qty_cases": int(row["picked_qty_cases"]),
                "short_qty_cases": int(row["short_qty_cases"]),
                "short_flag": 1 if int(row["short_qty_cases"]) > 0 else 0,
                "system_qty_before_cases": int(row["system_qty_before_cases"]),
                "system_qty_after_cases": int(row["system_qty_after_cases"]),
                "reconstructed_balance_before_cases": balance_before,
                "reconstructed_balance_after_cases": balance_after,
                "nearest_replenishment_task_id": "" if nearest is None else nearest[0],
                "nearest_replenishment_completion_utc": "" if nearest is None else nearest[2],
                "minutes_to_nearest_replenishment_completion": nearest_minutes,
                "active_replenishment_at_pick_flag": 1 if active_replenishment else 0,
                "recent_qa_event_count_4h": recent_qa,
                "recent_adjustment_count_4h": recent_adjustments,
                "recent_same_item_location_short_count_60m": short_history,
                "system_event_overlap_flag": 1
                if _system_event_overlaps(system_events, location, pick_time)
                else 0,
                "replenishment_adjacent_flag": 1
                if _replenishment_adjacent(active_replenishment, nearest_minutes)
                else 0,
                "source_evidence": _source_evidence(
                    "pick_event", pick_id, int(row["event_sequence"]), "context"
                ),
            }
        )
    return rows


def _build_replenishment_context(
    source: ReconstructionSourceData, ledger: list[TableRecord]
) -> list[TableRecord]:
    items = _records_by_id(source.tables["item"], "item_id")
    locations = _records_by_id(source.tables["location"], "location_id")
    ledger_by_line = {
        (str(row["source_record_id"]), str(row["source_line"])): row
        for row in ledger
        if row["source_table"] == "replenishment_task"
    }
    picks = source.tables["pick_event"]
    rows: list[TableRecord] = []
    ordered_tasks = sorted(
        source.tables["replenishment_task"], key=lambda row: int(row["event_sequence"])
    )
    for row in ordered_tasks:
        task_id = str(row["replenishment_task_id"])
        item = items[str(row["item_id"])]
        destination = locations[str(row["destination_location_id"])]
        created = _parse_utc(str(row["created_utc"]))
        started = _parse_optional_utc(row["started_utc"])
        confirmed = _parse_optional_utc(row["confirmed_utc"])
        window_end = confirmed or _parse_utc(str(row["recorded_utc"]))
        picks_in_window = [
            pick
            for pick in picks
            if pick["item_id"] == row["item_id"]
            and pick["pick_location_id"] == row["destination_location_id"]
            and created <= _parse_utc(str(pick["event_utc"])) <= window_end
        ]
        source_ledger = ledger_by_line.get((task_id, "source"))
        destination_ledger = ledger_by_line.get((task_id, "destination"))
        rows.append(
            {
                "run_id": str(row["run_id"]),
                "replenishment_task_id": task_id,
                "event_sequence": int(row["event_sequence"]),
                "status": str(row["status"]),
                "item_id": str(row["item_id"]),
                "velocity_class": item["velocity_class"],
                "source_location_id": str(row["source_location_id"]),
                "destination_location_id": str(row["destination_location_id"]),
                "destination_zone_id": destination["zone_id"],
                "destination_zone_code": destination["zone_code"],
                "destination_aisle_code": destination["aisle_code"],
                "operator_id": _nullable_string(row["operator_id"]) or "",
                "created_utc": str(row["created_utc"]),
                "started_utc": row["started_utc"] or "",
                "confirmed_utc": row["confirmed_utc"] or "",
                "recorded_utc": str(row["recorded_utc"]),
                "requested_qty_cases": int(row["requested_qty_cases"]),
                "confirmed_qty_cases": int(row["confirmed_qty_cases"]),
                "creation_to_start_minutes": ""
                if started is None
                else _signed_minutes(created, started),
                "start_to_confirmation_minutes": ""
                if started is None or confirmed is None
                else _signed_minutes(started, confirmed),
                "creation_to_confirmation_minutes": ""
                if confirmed is None
                else _signed_minutes(created, confirmed),
                "pick_lines_during_creation_confirmation": len(picks_in_window),
                "short_lines_during_creation_confirmation": sum(
                    1 for pick in picks_in_window if int(pick["short_qty_cases"]) > 0
                ),
                "short_cases_during_creation_confirmation": sum(
                    int(pick["short_qty_cases"]) for pick in picks_in_window
                ),
                "source_balance_before_cases": _ledger_value(source_ledger, "balance_before_cases"),
                "source_balance_after_cases": _ledger_value(source_ledger, "balance_after_cases"),
                "destination_balance_before_cases": _ledger_value(
                    destination_ledger, "balance_before_cases"
                ),
                "destination_balance_after_cases": _ledger_value(
                    destination_ledger, "balance_after_cases"
                ),
                "source_evidence": _source_evidence(
                    "replenishment_task", task_id, int(row["event_sequence"]), "context"
                ),
            }
        )
    return rows


def _build_qa_adjustment_context(source: ReconstructionSourceData) -> list[TableRecord]:
    rows: list[TableRecord] = []
    adjustments = sorted(
        source.tables["inventory_adjustment"], key=lambda row: int(row["event_sequence"])
    )
    for qa in sorted(source.tables["qa_event"], key=lambda row: int(row["event_sequence"])):
        qa_time = _parse_utc(str(qa["occurred_utc"]))
        for adjustment in adjustments:
            if (
                adjustment["item_id"] != qa["item_id"]
                or adjustment["location_id"] != qa["location_id"]
            ):
                continue
            adjustment_time = _parse_utc(str(adjustment["effective_utc"]))
            if not qa_time <= adjustment_time <= qa_time + timedelta(hours=4):
                continue
            adjustment_delta = int(adjustment["qty_delta_cases"])
            affected_qty = int(qa["qty_affected_cases"])
            rows.append(
                {
                    "run_id": str(qa["run_id"]),
                    "qa_event_id": str(qa["qa_event_id"]),
                    "adjustment_id": str(adjustment["adjustment_id"]),
                    "qa_event_sequence": int(qa["event_sequence"]),
                    "adjustment_event_sequence": int(adjustment["event_sequence"]),
                    "item_id": str(qa["item_id"]),
                    "location_id": str(qa["location_id"]),
                    "qa_event_type": str(qa["event_type"]),
                    "qa_occurred_utc": str(qa["occurred_utc"]),
                    "qa_recorded_utc": str(qa["recorded_utc"]),
                    "qa_qty_affected_cases": affected_qty,
                    "qa_reason_code": str(qa["reason_code"]),
                    "qa_disposition_code": str(qa["disposition_code"]),
                    "adjustment_effective_utc": str(adjustment["effective_utc"]),
                    "adjustment_recorded_utc": str(adjustment["recorded_utc"]),
                    "adjustment_qty_delta_cases": adjustment_delta,
                    "adjustment_reason_code": str(adjustment["reason_code"]),
                    "minutes_qa_to_adjustment": _signed_minutes(qa_time, adjustment_time),
                    "relationship_rule": "same_item_same_location_adjustment_after_qa_within_4h",
                    "compatible_quantity_direction_flag": 1 if adjustment_delta < 0 else 0,
                    "compatible_quantity_amount_flag": 1
                    if adjustment_delta < 0 and abs(adjustment_delta) <= affected_qty
                    else 0,
                    "source_evidence": (
                        f"qa_event.{qa['qa_event_id']};"
                        f"inventory_adjustment.{adjustment['adjustment_id']}"
                    ),
                }
            )
    return rows


def _build_selector_exposure(pick_context: list[TableRecord]) -> list[TableRecord]:
    groups: dict[str, dict[str, Any]] = {}
    for row in pick_context:
        selector_id = str(row["selector_id"])
        group = groups.setdefault(
            selector_id,
            {
                "run_id": row["run_id"],
                "selector_id": selector_id,
                "trip_ids": set(),
                "pick_lines": 0,
                "eligible_pick_lines": 0,
                "requested_cases": 0,
                "picked_cases": 0,
                "short_lines": 0,
                "short_cases": 0,
                "high_velocity_pick_lines": 0,
                "replenishment_adjacent_pick_lines": 0,
                "ambient_pick_lines": 0,
                "chilled_pick_lines": 0,
                "frozen_pick_lines": 0,
                "aisles": set(),
                "operating_dates": set(),
                "shifts": set(),
            },
        )
        group["trip_ids"].add(row["trip_id"])
        group["pick_lines"] += 1
        group["eligible_pick_lines"] += 1
        group["requested_cases"] += int(row["requested_qty_cases"])
        group["picked_cases"] += int(row["picked_qty_cases"])
        group["short_lines"] += int(row["short_flag"])
        group["short_cases"] += int(row["short_qty_cases"])
        group["high_velocity_pick_lines"] += 1 if row["velocity_class"] == "A" else 0
        group["replenishment_adjacent_pick_lines"] += int(row["replenishment_adjacent_flag"])
        zone_code = str(row["zone_code"])
        if zone_code == "AMBIENT":
            group["ambient_pick_lines"] += 1
        elif zone_code == "CHILLED":
            group["chilled_pick_lines"] += 1
        elif zone_code == "FROZEN":
            group["frozen_pick_lines"] += 1
        if row["aisle_code"]:
            group["aisles"].add(row["aisle_code"])
        group["operating_dates"].add(row["operating_date_local"])
        group["shifts"].add(row["shift_id"])

    rows: list[TableRecord] = []
    for selector_id in sorted(groups):
        group = groups[selector_id]
        rows.append(
            {
                "run_id": group["run_id"],
                "selector_id": selector_id,
                "trips": len(group["trip_ids"]),
                "pick_lines": group["pick_lines"],
                "eligible_pick_lines": group["eligible_pick_lines"],
                "requested_cases": group["requested_cases"],
                "picked_cases": group["picked_cases"],
                "short_lines": group["short_lines"],
                "short_cases": group["short_cases"],
                "high_velocity_pick_lines": group["high_velocity_pick_lines"],
                "replenishment_adjacent_pick_lines": group["replenishment_adjacent_pick_lines"],
                "ambient_pick_lines": group["ambient_pick_lines"],
                "chilled_pick_lines": group["chilled_pick_lines"],
                "frozen_pick_lines": group["frozen_pick_lines"],
                "aisles_worked": len(group["aisles"]),
                "operating_dates_worked": len(group["operating_dates"]),
                "shifts_worked": len(group["shifts"]),
            }
        )
    return rows


def _snapshot_totals(
    source: ReconstructionSourceData, snapshot_type: str
) -> tuple[dict[InventoryKey, int], dict[InventoryKey, int]]:
    totals: defaultdict[InventoryKey, int] = defaultdict(int)
    counts: defaultdict[InventoryKey, int] = defaultdict(int)
    for row in source.tables["inventory_snapshot"]:
        if row["snapshot_type"] != snapshot_type:
            continue
        location_id = row["location_id"]
        if location_id is None:
            continue
        key = (str(row["item_id"]), str(location_id))
        totals[key] += int(row["qty_cases"])
        counts[key] += 1
    return dict(totals), dict(counts)


def _validate_ledger(
    source: ReconstructionSourceData, ledger: list[TableRecord], failures: list[ValidationIssue]
) -> None:
    opening_totals, _ = _snapshot_totals(source, "OPENING_SYSTEM")
    source_ids = {
        "pick_event": {str(row["pick_event_id"]) for row in source.tables["pick_event"]},
        "replenishment_task": {
            str(row["replenishment_task_id"]) for row in source.tables["replenishment_task"]
        },
        "inventory_adjustment": {
            str(row["adjustment_id"]) for row in source.tables["inventory_adjustment"]
        },
    }
    seen_ledger_sequences: set[int] = set()
    seen_source_lines: set[tuple[str, str, str]] = set()
    event_sequences = {
        int(row["event_sequence"]) for row in source.tables["event_sequence_registry"]
    }
    for row in ledger:
        ledger_sequence = int(row["ledger_sequence"])
        if ledger_sequence in seen_ledger_sequences:
            failures.append(
                ValidationIssue("reconstruction", f"duplicate ledger_sequence {ledger_sequence}")
            )
        seen_ledger_sequences.add(ledger_sequence)

        source_key = (
            str(row["source_table"]),
            str(row["source_record_id"]),
            str(row["source_line"]),
        )
        if source_key in seen_source_lines:
            failures.append(
                ValidationIssue("reconstruction", f"duplicate source application {source_key}")
            )
        seen_source_lines.add(source_key)

        if int(row["event_sequence"]) not in event_sequences:
            failures.append(
                ValidationIssue(
                    "reconstruction",
                    f"ledger row references missing event_sequence {row['event_sequence']}",
                )
            )
        if str(row["source_record_id"]) not in source_ids[str(row["source_table"])]:
            failures.append(
                ValidationIssue("reconstruction", f"untraceable source row {source_key}")
            )

        key = (str(row["item_id"]), str(row["location_id"]))
        if key not in opening_totals:
            failures.append(
                ValidationIssue(
                    "reconstruction",
                    f"missing opening system state for transacted item/location {key}",
                )
            )
        delta = int(row["quantity_delta_cases"])
        event_type = str(row["event_type"])
        if delta == 0:
            failures.append(ValidationIssue("reconstruction", "ledger contains zero delta"))
        if event_type == "PICK" and delta >= 0:
            failures.append(ValidationIssue("reconstruction", "pick delta must be negative"))
        if event_type == "REPLENISHMENT_SOURCE" and delta >= 0:
            failures.append(
                ValidationIssue("reconstruction", "replenishment source delta must be negative")
            )
        if event_type == "REPLENISHMENT_DESTINATION" and delta <= 0:
            failures.append(
                ValidationIssue(
                    "reconstruction", "replenishment destination delta must be positive"
                )
            )
        if int(row["balance_after_cases"]) < 0:
            failures.append(
                ValidationIssue("reconstruction", f"negative reconstructed balance at {key}")
            )

    expected_sequences = list(range(1, len(ledger) + 1))
    actual_sequences = [int(row["ledger_sequence"]) for row in ledger]
    if actual_sequences != expected_sequences:
        failures.append(
            ValidationIssue("reconstruction", "ledger_sequence values are not contiguous")
        )


def _validate_reconciliation(
    reconciliation: list[TableRecord], failures: list[ValidationIssue]
) -> None:
    seen_keys: set[InventoryKey] = set()
    for row in reconciliation:
        key = (str(row["item_id"]), str(row["location_id"]))
        if key in seen_keys:
            failures.append(
                ValidationIssue("reconstruction", f"duplicate reconciliation key {key}")
            )
        seen_keys.add(key)
        if row["reconciliation_status"] != "PASS" or int(row["difference_cases"]) != 0:
            failures.append(
                ValidationIssue("reconstruction", f"unexplained closing difference at {key}")
            )
        if int(row["reconstructed_closing_qty_cases"]) < 0:
            failures.append(
                ValidationIssue("reconstruction", f"negative reconstructed closing at {key}")
            )


def _validate_output_ordering(
    derived: ReconstructionTables, failures: list[ValidationIssue]
) -> None:
    sort_keys = {
        "inventory_event_ledger": lambda row: int(row["ledger_sequence"]),
        "inventory_reconciliation": lambda row: (row["item_id"], row["location_id"]),
        "pick_context": lambda row: int(row["event_sequence"]),
        "replenishment_context": lambda row: int(row["event_sequence"]),
        "qa_adjustment_context": lambda row: (
            int(row["qa_event_sequence"]),
            int(row["adjustment_event_sequence"]),
        ),
        "selector_exposure": lambda row: row["selector_id"],
    }
    for table_name, rows in derived.tables.items():
        if rows != sorted(rows, key=sort_keys[table_name]):
            failures.append(
                ValidationIssue("reconstruction", f"{table_name} rows are not stably ordered")
            )
        expected_columns = set(OUTPUT_TABLE_COLUMNS[table_name])
        for row in rows:
            if set(row) != expected_columns:
                failures.append(
                    ValidationIssue(
                        "reconstruction",
                        f"{table_name} row columns do not match the output contract",
                    )
                )
                break


def _validate_hidden_truth_absence(
    derived: ReconstructionTables, failures: list[ValidationIssue]
) -> None:
    for table_name, rows in derived.tables.items():
        for column_name in OUTPUT_TABLE_COLUMNS[table_name]:
            lowered_column = column_name.lower()
            if any(token in lowered_column for token in _FORBIDDEN_HIDDEN_TOKENS):
                failures.append(
                    ValidationIssue(
                        "reconstruction",
                        f"hidden-truth-like output column found: {table_name}.{column_name}",
                    )
                )
        for row in rows:
            for value in row.values():
                lowered_value = str(value).lower()
                if any(token in lowered_value for token in _FORBIDDEN_HIDDEN_TOKENS):
                    failures.append(
                        ValidationIssue(
                            "reconstruction",
                            f"hidden-truth-like output value found in {table_name}",
                        )
                    )
                    return


def _records_by_id(rows: list[TableRecord], key_column: str) -> dict[str, TableRecord]:
    return {str(row[key_column]): row for row in rows}


def _nearest_replenishment(
    pick: Mapping[str, Any], replenishments: list[TableRecord]
) -> tuple[str, datetime, str] | None:
    pick_time = _parse_utc(str(pick["event_utc"]))
    candidates: list[tuple[float, str, datetime, str]] = []
    for row in replenishments:
        if (
            row["item_id"] != pick["item_id"]
            or row["destination_location_id"] != pick["pick_location_id"]
            or row["confirmed_utc"] is None
        ):
            continue
        confirmed_time = _parse_utc(str(row["confirmed_utc"]))
        delta_seconds = abs((confirmed_time - pick_time).total_seconds())
        candidates.append(
            (
                delta_seconds,
                str(row["replenishment_task_id"]),
                confirmed_time,
                str(row["confirmed_utc"]),
            )
        )
    if not candidates:
        return None
    _, task_id, confirmed_time, confirmed_text = min(candidates)
    return task_id, confirmed_time, confirmed_text


def _active_replenishment_at_pick(
    pick: Mapping[str, Any], replenishments: list[TableRecord], pick_time: datetime
) -> bool:
    for row in replenishments:
        if (
            row["item_id"] != pick["item_id"]
            or row["destination_location_id"] != pick["pick_location_id"]
            or row["confirmed_utc"] is None
        ):
            continue
        created = _parse_utc(str(row["created_utc"]))
        confirmed = _parse_utc(str(row["confirmed_utc"]))
        if created <= pick_time <= confirmed:
            return True
    return False


def _count_recent_events(
    rows: list[TableRecord],
    item_id: str,
    location_id: str,
    event_time: datetime,
    *,
    time_column: str,
    lookback: timedelta,
) -> int:
    start = event_time - lookback
    count = 0
    for row in rows:
        if row["item_id"] != item_id or row["location_id"] != location_id:
            continue
        row_time = _parse_utc(str(row[time_column]))
        if start <= row_time <= event_time:
            count += 1
    return count


def _count_recent_short_picks(
    picks: list[TableRecord], current_pick: Mapping[str, Any], pick_time: datetime
) -> int:
    start = pick_time - timedelta(minutes=60)
    count = 0
    for row in picks:
        if int(row["event_sequence"]) >= int(current_pick["event_sequence"]):
            continue
        if (
            row["item_id"] != current_pick["item_id"]
            or row["pick_location_id"] != current_pick["pick_location_id"]
            or int(row["short_qty_cases"]) <= 0
        ):
            continue
        row_time = _parse_utc(str(row["event_utc"]))
        if start <= row_time <= pick_time:
            count += 1
    return count


def _system_event_overlaps(
    system_events: list[TableRecord], location: Mapping[str, Any], event_time: datetime
) -> bool:
    for row in system_events:
        start = _parse_utc(str(row["start_utc"]))
        end = _parse_utc(str(row["end_utc"]))
        if not start <= event_time <= end:
            continue
        location_match = row["location_id"] == location["location_id"]
        zone_match = row["zone_id"] == location["zone_id"]
        equipment_area = row["equipment_area"]
        equipment_match = (
            equipment_area is not None and equipment_area == location["equipment_area"]
        )
        if location_match or zone_match or equipment_match:
            return True
    return False


def _replenishment_adjacent(active_replenishment: bool, nearest_minutes: Any) -> bool:
    if active_replenishment:
        return True
    if nearest_minutes == "":
        return False
    return 0 <= float(nearest_minutes) <= 20


def _ledger_value(row: TableRecord | None, column_name: str) -> int | str:
    if row is None:
        return ""
    return int(row[column_name])


def _signed_minutes(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 60, 3)


def _parse_optional_utc(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    return _parse_utc(str(value))


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _source_evidence(
    source_table: str, source_record_id: str, event_sequence: int, source_line: str
) -> str:
    return (
        f"{source_table}.{source_record_id};"
        f"event_sequence={event_sequence};source_line={source_line}"
    )
