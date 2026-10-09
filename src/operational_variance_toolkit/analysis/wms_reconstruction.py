"""Audit-first reconstruction for schema-3 WMS databases."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from operational_variance_toolkit.storage.schema import WMS_SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult

WMS_RECONSTRUCTION_VERSION = "2.0.0"

TableRecord = dict[str, Any]

WMS_LEDGER_COLUMNS = (
    "run_id",
    "ledger_sequence",
    "transaction_id",
    "transaction_group_id",
    "command_id",
    "event_sequence",
    "line_number",
    "transaction_type",
    "event_utc",
    "recorded_utc",
    "item_id",
    "location_id",
    "related_location_id",
    "operator_id",
    "quantity_delta_cases",
    "balance_before_cases",
    "balance_after_cases",
    "reason_code",
    "source_record_type",
    "source_record_id",
    "source_evidence",
)

WMS_RECONCILIATION_COLUMNS = (
    "run_id",
    "location_id",
    "item_id",
    "opening_snapshot_batch_id",
    "opening_qty_cases",
    "total_transaction_delta_cases",
    "reconstructed_closing_qty_cases",
    "live_master_qty_cases",
    "closing_snapshot_batch_id",
    "closing_snapshot_qty_cases",
    "difference_to_live_cases",
    "difference_to_snapshot_cases",
    "reconciliation_status",
    "transaction_count",
    "opening_snapshot_count",
    "closing_snapshot_count",
)

WMS_PICK_CONTEXT_COLUMNS = (
    "run_id",
    "pick_event_id",
    "command_id",
    "transaction_id",
    "transaction_group_id",
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
    "audit_balance_before_cases",
    "audit_balance_after_cases",
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

WMS_REPLENISHMENT_CONTEXT_COLUMNS = (
    "run_id",
    "replenishment_task_id",
    "create_command_id",
    "confirm_command_id",
    "transaction_group_id",
    "source_transaction_id",
    "destination_transaction_id",
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

WMS_QA_ADJUSTMENT_CONTEXT_COLUMNS = (
    "run_id",
    "qa_event_id",
    "qa_command_id",
    "adjustment_id",
    "adjustment_command_id",
    "adjustment_transaction_id",
    "adjustment_transaction_group_id",
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
    "audit_balance_before_cases",
    "audit_balance_after_cases",
    "minutes_qa_to_adjustment",
    "relationship_rule",
    "compatible_quantity_direction_flag",
    "compatible_quantity_amount_flag",
    "source_evidence",
)

WMS_SELECTOR_EXPOSURE_COLUMNS = (
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

WMS_OUTPUT_TABLE_COLUMNS = {
    "inventory_event_ledger": WMS_LEDGER_COLUMNS,
    "inventory_reconciliation": WMS_RECONCILIATION_COLUMNS,
    "pick_context": WMS_PICK_CONTEXT_COLUMNS,
    "replenishment_context": WMS_REPLENISHMENT_CONTEXT_COLUMNS,
    "qa_adjustment_context": WMS_QA_ADJUSTMENT_CONTEXT_COLUMNS,
    "selector_exposure": WMS_SELECTOR_EXPOSURE_COLUMNS,
}

WMS_OUTPUT_FILE_NAMES = {name: f"{name}.csv" for name in WMS_OUTPUT_TABLE_COLUMNS}

_FORBIDDEN_TOKENS = (
    "true_root_cause",
    "is_injected_anomaly",
    "physical_arrival",
    "scenario_target",
    "target_selector",
    "injected_pattern",
    "ground_truth",
)


@dataclass(frozen=True, slots=True)
class WmsReconstructionSourceData:
    run_id: str
    source_schema_version: str
    sqlite_user_version: int
    table_counts: Mapping[str, int]
    tables: Mapping[str, list[TableRecord]]


@dataclass(frozen=True, slots=True)
class WmsReconstructionTables:
    tables: dict[str, list[TableRecord]]

    @property
    def row_counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in self.tables.items()}


def build_wms_reconstruction_tables(
    source: WmsReconstructionSourceData,
) -> WmsReconstructionTables:
    opening = _selected_snapshot(source.tables["inventory_snapshot"], "OPENING_SYSTEM")
    closing = _selected_snapshot(source.tables["inventory_snapshot"], "CLOSING_SYSTEM")
    ledger = _build_ledger(source, opening)
    reconciliation = _build_reconciliation(source, opening, closing)
    pick_context = _build_pick_context(source)
    replenishment_context = _build_replenishment_context(source)
    qa_adjustment_context = _build_qa_adjustment_context(source)
    selector_exposure = _build_selector_exposure(pick_context)
    return WmsReconstructionTables(
        {
            "inventory_event_ledger": ledger,
            "inventory_reconciliation": reconciliation,
            "pick_context": pick_context,
            "replenishment_context": replenishment_context,
            "qa_adjustment_context": qa_adjustment_context,
            "selector_exposure": selector_exposure,
        }
    )


def validate_wms_reconstruction_tables(
    source: WmsReconstructionSourceData,
    derived: WmsReconstructionTables,
) -> ValidationResult:
    failures: list[ValidationIssue] = []
    if source.sqlite_user_version != 3 or source.source_schema_version != WMS_SCHEMA_VERSION:
        failures.append(
            ValidationIssue(
                "reconstruction",
                "schema-3 reconstruction requires WMS schema 3.0.0 "
                f"(found user_version={source.sqlite_user_version}, "
                f"schema={source.source_schema_version})",
            )
        )
    _validate_ledger(source, derived.tables["inventory_event_ledger"], failures)
    _validate_reconciliation(derived.tables["inventory_reconciliation"], failures)
    _validate_outputs(derived, failures)
    return ValidationResult(tuple(failures))


def _build_ledger(
    source: WmsReconstructionSourceData,
    opening: Mapping[str, TableRecord],
) -> list[TableRecord]:
    rows: list[TableRecord] = []
    sequence = 0
    for location_id, snapshot in sorted(opening.items()):
        sequence += 1
        qty = int(snapshot["qty_on_hand_cases"])
        rows.append(
            {
                "run_id": source.run_id,
                "ledger_sequence": sequence,
                "transaction_id": "",
                "transaction_group_id": "",
                "command_id": "",
                "event_sequence": 0,
                "line_number": 1,
                "transaction_type": "OPENING_BALANCE",
                "event_utc": str(snapshot["snapshot_utc"]),
                "recorded_utc": str(snapshot["snapshot_utc"]),
                "item_id": snapshot["item_id"] or "",
                "location_id": location_id,
                "related_location_id": "",
                "operator_id": "",
                "quantity_delta_cases": qty,
                "balance_before_cases": 0,
                "balance_after_cases": qty,
                "reason_code": "OPENING_SYSTEM",
                "source_record_type": "INVENTORY_SNAPSHOT",
                "source_record_id": str(snapshot["snapshot_line_id"]),
                "source_evidence": f"inventory_snapshot.{snapshot['snapshot_line_id']}",
            }
        )
    transactions = sorted(
        source.tables["inventory_transaction"],
        key=lambda row: (
            int(row["event_sequence"]),
            int(row["line_number"]),
            str(row["transaction_id"]),
        ),
    )
    for transaction in transactions:
        sequence += 1
        rows.append(
            {
                "run_id": str(transaction["run_id"]),
                "ledger_sequence": sequence,
                "transaction_id": str(transaction["transaction_id"]),
                "transaction_group_id": str(transaction["transaction_group_id"]),
                "command_id": str(transaction["command_id"]),
                "event_sequence": int(transaction["event_sequence"]),
                "line_number": int(transaction["line_number"]),
                "transaction_type": str(transaction["transaction_type"]),
                "event_utc": str(transaction["event_utc"]),
                "recorded_utc": str(transaction["recorded_utc"]),
                "item_id": str(transaction["item_id"]),
                "location_id": str(transaction["location_id"]),
                "related_location_id": transaction["related_location_id"] or "",
                "operator_id": transaction["operator_id"] or "",
                "quantity_delta_cases": int(transaction["qty_delta_cases"]),
                "balance_before_cases": int(transaction["balance_before_cases"]),
                "balance_after_cases": int(transaction["balance_after_cases"]),
                "reason_code": transaction["reason_code"] or "",
                "source_record_type": str(transaction["source_record_type"]),
                "source_record_id": str(transaction["source_record_id"]),
                "source_evidence": f"inventory_transaction.{transaction['transaction_id']}",
            }
        )
    return rows


def _build_reconciliation(
    source: WmsReconstructionSourceData,
    opening: Mapping[str, TableRecord],
    closing: Mapping[str, TableRecord],
) -> list[TableRecord]:
    live = _by_id(source.tables["inventory_master"], "location_id")
    deltas: defaultdict[str, int] = defaultdict(int)
    counts: defaultdict[str, int] = defaultdict(int)
    for transaction in source.tables["inventory_transaction"]:
        location_id = str(transaction["location_id"])
        deltas[location_id] += int(transaction["qty_delta_cases"])
        counts[location_id] += 1
    locations = sorted(set(opening) | set(closing) | set(live))
    rows: list[TableRecord] = []
    for location_id in locations:
        opening_row = opening.get(location_id)
        closing_row = closing.get(location_id)
        live_row = live.get(location_id)
        opening_qty = 0 if opening_row is None else int(opening_row["qty_on_hand_cases"])
        reconstructed = opening_qty + deltas[location_id]
        live_qty = 0 if live_row is None else int(live_row["qty_on_hand_cases"])
        snapshot_qty = 0 if closing_row is None else int(closing_row["qty_on_hand_cases"])
        difference_live = reconstructed - live_qty
        difference_snapshot = reconstructed - snapshot_qty
        item_id = next(
            (
                str(row["item_id"])
                for row in (live_row, closing_row, opening_row)
                if row is not None and row["item_id"] is not None
            ),
            "",
        )
        rows.append(
            {
                "run_id": source.run_id,
                "location_id": location_id,
                "item_id": item_id,
                "opening_snapshot_batch_id": ""
                if opening_row is None
                else str(opening_row["snapshot_batch_id"]),
                "opening_qty_cases": opening_qty,
                "total_transaction_delta_cases": deltas[location_id],
                "reconstructed_closing_qty_cases": reconstructed,
                "live_master_qty_cases": live_qty,
                "closing_snapshot_batch_id": ""
                if closing_row is None
                else str(closing_row["snapshot_batch_id"]),
                "closing_snapshot_qty_cases": snapshot_qty,
                "difference_to_live_cases": difference_live,
                "difference_to_snapshot_cases": difference_snapshot,
                "reconciliation_status": (
                    "PASS"
                    if difference_live == 0
                    and difference_snapshot == 0
                    and opening_row is not None
                    and closing_row is not None
                    and live_row is not None
                    else "FAIL"
                ),
                "transaction_count": counts[location_id],
                "opening_snapshot_count": 1 if opening_row is not None else 0,
                "closing_snapshot_count": 1 if closing_row is not None else 0,
            }
        )
    return rows


def _build_pick_context(source: WmsReconstructionSourceData) -> list[TableRecord]:
    items = _by_id(source.tables["item_master"], "item_id")
    locations = _by_id(source.tables["location_master"], "location_id")
    trips = _by_id(source.tables["trip"], "trip_id")
    transactions = {
        str(row["source_record_id"]): row
        for row in source.tables["inventory_transaction"]
        if row["source_record_type"] == "PICK"
    }
    replenishments = [
        row
        for row in source.tables["replenishment_task"]
        if row["status"] == "CONFIRMED" and row["confirmed_utc"] is not None
    ]
    ordered_picks = sorted(source.tables["pick_event"], key=lambda row: int(row["event_sequence"]))
    rows: list[TableRecord] = []
    for pick in ordered_picks:
        if int(pick["eligible_pick_flag"]) != 1:
            continue
        pick_id = str(pick["pick_event_id"])
        item_id = str(pick["item_id"])
        location_id = str(pick["pick_location_id"])
        pick_time = _parse_utc(str(pick["event_utc"]))
        trip = trips[str(pick["trip_id"])]
        location = locations[location_id]
        item = items[item_id]
        transaction = transactions.get(pick_id)
        nearest = _nearest_replenishment(pick, replenishments)
        nearest_minutes: float | str = ""
        if nearest is not None:
            nearest_minutes = _signed_minutes(pick_time, _parse_utc(str(nearest["confirmed_utc"])))
        active = any(
            task["item_id"] == pick["item_id"]
            and task["destination_location_id"] == pick["pick_location_id"]
            and _parse_utc(str(task["created_utc"])) <= pick_time
            and (
                task["confirmed_utc"] is None or pick_time <= _parse_utc(str(task["confirmed_utc"]))
            )
            for task in source.tables["replenishment_task"]
        )
        recent_qa = _count_recent(
            source.tables["qa_event"], pick, pick_time, "occurred_utc", timedelta(hours=4)
        )
        recent_adjustments = _count_recent(
            source.tables["inventory_adjustment"],
            pick,
            pick_time,
            "effective_utc",
            timedelta(hours=4),
        )
        recent_shorts = sum(
            1
            for prior in ordered_picks
            if int(prior["event_sequence"]) < int(pick["event_sequence"])
            and prior["item_id"] == pick["item_id"]
            and prior["pick_location_id"] == pick["pick_location_id"]
            and int(prior["short_qty_cases"]) > 0
            and pick_time - timedelta(hours=1) <= _parse_utc(str(prior["event_utc"])) <= pick_time
        )
        system_overlap = _system_event_overlap(source.tables["system_event"], location, pick_time)
        replenishment_adjacent = active or (
            nearest_minutes != "" and abs(float(nearest_minutes)) <= 30.0
        )
        rows.append(
            {
                "run_id": str(pick["run_id"]),
                "pick_event_id": pick_id,
                "command_id": str(pick["command_id"]),
                "transaction_id": "" if transaction is None else str(transaction["transaction_id"]),
                "transaction_group_id": ""
                if transaction is None
                else str(transaction["transaction_group_id"]),
                "event_sequence": int(pick["event_sequence"]),
                "trip_id": str(pick["trip_id"]),
                "selector_id": str(pick["selector_id"]),
                "shift_id": str(trip["shift_id"]),
                "shift_code": str(trip["shift_code"]),
                "operating_date_local": str(trip["operating_date_local"]),
                "item_id": item_id,
                "velocity_class": str(item["velocity_class"]),
                "fragility_score": float(item["fragility_score"]),
                "pick_location_id": location_id,
                "zone_id": str(location["zone_id"]),
                "zone_code": str(location["zone_code"]),
                "aisle_code": location["aisle_code"] or "",
                "event_utc": str(pick["event_utc"]),
                "recorded_utc": str(pick["recorded_utc"]),
                "requested_qty_cases": int(pick["requested_qty_cases"]),
                "picked_qty_cases": int(pick["picked_qty_cases"]),
                "short_qty_cases": int(pick["short_qty_cases"]),
                "short_flag": 1 if int(pick["short_qty_cases"]) > 0 else 0,
                "system_qty_before_cases": int(pick["system_qty_before_cases"]),
                "system_qty_after_cases": int(pick["system_qty_after_cases"]),
                "audit_balance_before_cases": int(pick["system_qty_before_cases"])
                if transaction is None
                else int(transaction["balance_before_cases"]),
                "audit_balance_after_cases": int(pick["system_qty_after_cases"])
                if transaction is None
                else int(transaction["balance_after_cases"]),
                "nearest_replenishment_task_id": ""
                if nearest is None
                else str(nearest["replenishment_task_id"]),
                "nearest_replenishment_completion_utc": ""
                if nearest is None
                else str(nearest["confirmed_utc"]),
                "minutes_to_nearest_replenishment_completion": nearest_minutes,
                "active_replenishment_at_pick_flag": 1 if active else 0,
                "recent_qa_event_count_4h": recent_qa,
                "recent_adjustment_count_4h": recent_adjustments,
                "recent_same_item_location_short_count_60m": recent_shorts,
                "system_event_overlap_flag": 1 if system_overlap else 0,
                "replenishment_adjacent_flag": 1 if replenishment_adjacent else 0,
                "source_evidence": f"pick_event.{pick_id}",
            }
        )
    return rows


def _build_replenishment_context(
    source: WmsReconstructionSourceData,
) -> list[TableRecord]:
    items = _by_id(source.tables["item_master"], "item_id")
    locations = _by_id(source.tables["location_master"], "location_id")
    transactions: defaultdict[str, list[TableRecord]] = defaultdict(list)
    for transaction in source.tables["inventory_transaction"]:
        if transaction["source_record_type"] == "REPLENISHMENT":
            transactions[str(transaction["source_record_id"])].append(transaction)
    rows: list[TableRecord] = []
    for task in sorted(
        source.tables["replenishment_task"],
        key=lambda row: (
            int(row["event_sequence"] or 0),
            str(row["replenishment_task_id"]),
        ),
    ):
        task_id = str(task["replenishment_task_id"])
        task_transactions = transactions[task_id]
        source_tx = next(
            (row for row in task_transactions if row["transaction_type"] == "TRANSFER_OUT"),
            None,
        )
        destination_tx = next(
            (row for row in task_transactions if row["transaction_type"] == "TRANSFER_IN"),
            None,
        )
        created = _parse_utc(str(task["created_utc"]))
        started = _parse_optional_utc(task["started_utc"])
        confirmed = _parse_optional_utc(task["confirmed_utc"])
        window_end = confirmed or _parse_utc(str(task["recorded_utc"]))
        picks = [
            pick
            for pick in source.tables["pick_event"]
            if pick["item_id"] == task["item_id"]
            and pick["pick_location_id"] == task["destination_location_id"]
            and created <= _parse_utc(str(pick["event_utc"])) <= window_end
        ]
        destination = locations[str(task["destination_location_id"])]
        item = items[str(task["item_id"])]
        rows.append(
            {
                "run_id": str(task["run_id"]),
                "replenishment_task_id": task_id,
                "create_command_id": str(task["create_command_id"]),
                "confirm_command_id": task["confirm_command_id"] or "",
                "transaction_group_id": ""
                if source_tx is None
                else str(source_tx["transaction_group_id"]),
                "source_transaction_id": ""
                if source_tx is None
                else str(source_tx["transaction_id"]),
                "destination_transaction_id": ""
                if destination_tx is None
                else str(destination_tx["transaction_id"]),
                "event_sequence": int(task["event_sequence"] or 0),
                "status": str(task["status"]),
                "item_id": str(task["item_id"]),
                "velocity_class": str(item["velocity_class"]),
                "source_location_id": str(task["source_location_id"]),
                "destination_location_id": str(task["destination_location_id"]),
                "destination_zone_id": str(destination["zone_id"]),
                "destination_zone_code": str(destination["zone_code"]),
                "destination_aisle_code": destination["aisle_code"] or "",
                "operator_id": task["operator_id"] or "",
                "created_utc": str(task["created_utc"]),
                "started_utc": task["started_utc"] or "",
                "confirmed_utc": task["confirmed_utc"] or "",
                "recorded_utc": str(task["recorded_utc"]),
                "requested_qty_cases": int(task["requested_qty_cases"]),
                "confirmed_qty_cases": int(task["confirmed_qty_cases"]),
                "creation_to_start_minutes": ""
                if started is None
                else _signed_minutes(created, started),
                "start_to_confirmation_minutes": ""
                if started is None or confirmed is None
                else _signed_minutes(started, confirmed),
                "creation_to_confirmation_minutes": ""
                if confirmed is None
                else _signed_minutes(created, confirmed),
                "pick_lines_during_creation_confirmation": len(picks),
                "short_lines_during_creation_confirmation": sum(
                    1 for pick in picks if int(pick["short_qty_cases"]) > 0
                ),
                "short_cases_during_creation_confirmation": sum(
                    int(pick["short_qty_cases"]) for pick in picks
                ),
                "source_balance_before_cases": _tx_value(source_tx, "balance_before_cases"),
                "source_balance_after_cases": _tx_value(source_tx, "balance_after_cases"),
                "destination_balance_before_cases": _tx_value(
                    destination_tx, "balance_before_cases"
                ),
                "destination_balance_after_cases": _tx_value(destination_tx, "balance_after_cases"),
                "source_evidence": f"replenishment_task.{task_id}",
            }
        )
    return rows


def _build_qa_adjustment_context(
    source: WmsReconstructionSourceData,
) -> list[TableRecord]:
    adjustment_transactions = {
        str(row["source_record_id"]): row
        for row in source.tables["inventory_transaction"]
        if row["source_record_type"] == "ADJUSTMENT"
    }
    adjustments = sorted(
        source.tables["inventory_adjustment"],
        key=lambda row: int(row["event_sequence"]),
    )
    rows: list[TableRecord] = []
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
            adjustment_id = str(adjustment["adjustment_id"])
            transaction = adjustment_transactions.get(adjustment_id)
            delta = int(adjustment["qty_delta_cases"])
            affected = int(qa["qty_affected_cases"])
            rows.append(
                {
                    "run_id": str(qa["run_id"]),
                    "qa_event_id": str(qa["qa_event_id"]),
                    "qa_command_id": str(qa["command_id"]),
                    "adjustment_id": adjustment_id,
                    "adjustment_command_id": str(adjustment["command_id"]),
                    "adjustment_transaction_id": ""
                    if transaction is None
                    else str(transaction["transaction_id"]),
                    "adjustment_transaction_group_id": ""
                    if transaction is None
                    else str(transaction["transaction_group_id"]),
                    "qa_event_sequence": int(qa["event_sequence"]),
                    "adjustment_event_sequence": int(adjustment["event_sequence"]),
                    "item_id": str(qa["item_id"]),
                    "location_id": str(qa["location_id"]),
                    "qa_event_type": str(qa["event_type"]),
                    "qa_occurred_utc": str(qa["occurred_utc"]),
                    "qa_recorded_utc": str(qa["recorded_utc"]),
                    "qa_qty_affected_cases": affected,
                    "qa_reason_code": str(qa["reason_code"]),
                    "qa_disposition_code": str(qa["disposition_code"]),
                    "adjustment_effective_utc": str(adjustment["effective_utc"]),
                    "adjustment_recorded_utc": str(adjustment["recorded_utc"]),
                    "adjustment_qty_delta_cases": delta,
                    "adjustment_reason_code": str(adjustment["reason_code"]),
                    "audit_balance_before_cases": _tx_value(transaction, "balance_before_cases"),
                    "audit_balance_after_cases": _tx_value(transaction, "balance_after_cases"),
                    "minutes_qa_to_adjustment": _signed_minutes(qa_time, adjustment_time),
                    "relationship_rule": ("same_item_same_location_adjustment_after_qa_within_4h"),
                    "compatible_quantity_direction_flag": 1 if delta < 0 else 0,
                    "compatible_quantity_amount_flag": (
                        1 if delta < 0 and abs(delta) <= affected else 0
                    ),
                    "source_evidence": (
                        f"qa_event.{qa['qa_event_id']};inventory_adjustment.{adjustment_id}"
                    ),
                }
            )
    return rows


def _build_selector_exposure(picks: list[TableRecord]) -> list[TableRecord]:
    groups: dict[str, dict[str, Any]] = {}
    for pick in picks:
        selector = str(pick["selector_id"])
        group = groups.setdefault(
            selector,
            {
                "run_id": pick["run_id"],
                "trips": set(),
                "pick_lines": 0,
                "eligible_pick_lines": 0,
                "requested_cases": 0,
                "picked_cases": 0,
                "short_lines": 0,
                "short_cases": 0,
                "high_velocity_pick_lines": 0,
                "replenishment_adjacent_pick_lines": 0,
                "AMBIENT": 0,
                "CHILLED": 0,
                "FROZEN": 0,
                "aisles": set(),
                "dates": set(),
                "shifts": set(),
            },
        )
        group["trips"].add(pick["trip_id"])
        group["pick_lines"] += 1
        group["eligible_pick_lines"] += 1
        group["requested_cases"] += int(pick["requested_qty_cases"])
        group["picked_cases"] += int(pick["picked_qty_cases"])
        group["short_lines"] += int(pick["short_flag"])
        group["short_cases"] += int(pick["short_qty_cases"])
        group["high_velocity_pick_lines"] += int(pick["velocity_class"] == "A")
        group["replenishment_adjacent_pick_lines"] += int(pick["replenishment_adjacent_flag"])
        zone = str(pick["zone_code"])
        if zone in {"AMBIENT", "CHILLED", "FROZEN"}:
            group[zone] += 1
        if pick["aisle_code"]:
            group["aisles"].add(pick["aisle_code"])
        group["dates"].add(pick["operating_date_local"])
        group["shifts"].add(pick["shift_id"])
    return [
        {
            "run_id": group["run_id"],
            "selector_id": selector,
            "trips": len(group["trips"]),
            "pick_lines": group["pick_lines"],
            "eligible_pick_lines": group["eligible_pick_lines"],
            "requested_cases": group["requested_cases"],
            "picked_cases": group["picked_cases"],
            "short_lines": group["short_lines"],
            "short_cases": group["short_cases"],
            "high_velocity_pick_lines": group["high_velocity_pick_lines"],
            "replenishment_adjacent_pick_lines": group["replenishment_adjacent_pick_lines"],
            "ambient_pick_lines": group["AMBIENT"],
            "chilled_pick_lines": group["CHILLED"],
            "frozen_pick_lines": group["FROZEN"],
            "aisles_worked": len(group["aisles"]),
            "operating_dates_worked": len(group["dates"]),
            "shifts_worked": len(group["shifts"]),
        }
        for selector, group in sorted(groups.items())
    ]


def _validate_ledger(
    source: WmsReconstructionSourceData,
    ledger: list[TableRecord],
    failures: list[ValidationIssue],
) -> None:
    opening = _selected_snapshot(source.tables["inventory_snapshot"], "OPENING_SYSTEM")
    opening_rows = [row for row in ledger if row["transaction_type"] == "OPENING_BALANCE"]
    transaction_rows = [row for row in ledger if row["transaction_id"]]
    if len(opening_rows) != len(opening):
        failures.append(ValidationIssue("reconstruction", "Opening ledger coverage is incomplete"))
    if len(transaction_rows) != len(source.tables["inventory_transaction"]):
        failures.append(
            ValidationIssue("reconstruction", "Inventory transaction ledger coverage is incomplete")
        )
    balances = {location_id: int(row["qty_on_hand_cases"]) for location_id, row in opening.items()}
    seen_transactions: set[str] = set()
    groups: defaultdict[str, list[TableRecord]] = defaultdict(list)
    for row in transaction_rows:
        transaction_id = str(row["transaction_id"])
        if transaction_id in seen_transactions:
            failures.append(
                ValidationIssue("reconstruction", f"Duplicate transaction replay: {transaction_id}")
            )
        seen_transactions.add(transaction_id)
        location_id = str(row["location_id"])
        before = balances.get(location_id, 0)
        if before != int(row["balance_before_cases"]):
            failures.append(
                ValidationIssue(
                    "reconstruction", f"Audit replay before-balance mismatch: {transaction_id}"
                )
            )
        after = before + int(row["quantity_delta_cases"])
        if after != int(row["balance_after_cases"]):
            failures.append(
                ValidationIssue(
                    "reconstruction", f"Audit replay after-balance mismatch: {transaction_id}"
                )
            )
        balances[location_id] = after
        groups[str(row["transaction_group_id"])].append(row)
    for group_id, group_rows in groups.items():
        transfer_rows = [
            row for row in group_rows if row["transaction_type"] in {"TRANSFER_OUT", "TRANSFER_IN"}
        ]
        if transfer_rows and (
            len(transfer_rows) != 2
            or sum(int(row["quantity_delta_cases"]) for row in transfer_rows) != 0
        ):
            failures.append(
                ValidationIssue(
                    "reconstruction", f"Transfer group is not conserved exactly once: {group_id}"
                )
            )
    if [int(row["ledger_sequence"]) for row in ledger] != list(range(1, len(ledger) + 1)):
        failures.append(ValidationIssue("reconstruction", "Ledger sequence is not contiguous"))


def _validate_reconciliation(rows: list[TableRecord], failures: list[ValidationIssue]) -> None:
    seen_locations: set[str] = set()
    for row in rows:
        location_id = str(row["location_id"])
        if location_id in seen_locations:
            failures.append(
                ValidationIssue(
                    "reconstruction", f"Duplicate reconciliation location: {location_id}"
                )
            )
        seen_locations.add(location_id)
        if (
            row["reconciliation_status"] != "PASS"
            or int(row["difference_to_live_cases"]) != 0
            or int(row["difference_to_snapshot_cases"]) != 0
        ):
            failures.append(
                ValidationIssue(
                    "reconstruction", f"Three-way reconciliation difference at {location_id}"
                )
            )


def _validate_outputs(
    derived: WmsReconstructionTables,
    failures: list[ValidationIssue],
) -> None:
    sort_keys = {
        "inventory_event_ledger": lambda row: int(row["ledger_sequence"]),
        "inventory_reconciliation": lambda row: str(row["location_id"]),
        "pick_context": lambda row: int(row["event_sequence"]),
        "replenishment_context": lambda row: (
            int(row["event_sequence"]),
            str(row["replenishment_task_id"]),
        ),
        "qa_adjustment_context": lambda row: (
            int(row["qa_event_sequence"]),
            int(row["adjustment_event_sequence"]),
        ),
        "selector_exposure": lambda row: str(row["selector_id"]),
    }
    for name, rows in derived.tables.items():
        if rows != sorted(rows, key=sort_keys[name]):
            failures.append(ValidationIssue("reconstruction", f"{name} ordering is unstable"))
        expected = set(WMS_OUTPUT_TABLE_COLUMNS[name])
        if any(set(row) != expected for row in rows):
            failures.append(
                ValidationIssue("reconstruction", f"{name} columns do not match the contract")
            )
        for row in rows:
            for column, value in row.items():
                text = f"{column}={value}".lower()
                if any(token in text for token in _FORBIDDEN_TOKENS):
                    failures.append(
                        ValidationIssue("reconstruction", f"Hidden truth leaked into {name}")
                    )
                    return


def _selected_snapshot(rows: list[TableRecord], snapshot_type: str) -> dict[str, TableRecord]:
    matching = [row for row in rows if row["snapshot_type"] == snapshot_type]
    if not matching:
        return {}
    batch_id = max(
        (
            str(row["snapshot_utc"]),
            str(row["snapshot_batch_id"]),
        )
        for row in matching
    )[1]
    return {
        str(row["location_id"]): row
        for row in matching
        if str(row["snapshot_batch_id"]) == batch_id
    }


def _by_id(rows: list[TableRecord], column: str) -> dict[str, TableRecord]:
    return {str(row[column]): row for row in rows}


def _nearest_replenishment(pick: TableRecord, tasks: list[TableRecord]) -> TableRecord | None:
    candidates = [
        task
        for task in tasks
        if task["item_id"] == pick["item_id"]
        and task["destination_location_id"] == pick["pick_location_id"]
    ]
    if not candidates:
        return None
    pick_time = _parse_utc(str(pick["event_utc"]))
    return min(
        candidates,
        key=lambda task: (
            abs((_parse_utc(str(task["confirmed_utc"])) - pick_time).total_seconds()),
            str(task["replenishment_task_id"]),
        ),
    )


def _count_recent(
    rows: list[TableRecord],
    pick: TableRecord,
    event_utc: datetime,
    time_column: str,
    lookback: timedelta,
) -> int:
    return sum(
        1
        for row in rows
        if row["item_id"] == pick["item_id"]
        and row["location_id"] == pick["pick_location_id"]
        and event_utc - lookback <= _parse_utc(str(row[time_column])) <= event_utc
    )


def _system_event_overlap(
    rows: list[TableRecord], location: TableRecord, event_utc: datetime
) -> bool:
    for row in rows:
        if not _parse_utc(str(row["start_utc"])) <= event_utc <= _parse_utc(str(row["end_utc"])):
            continue
        if row["location_id"] is not None and row["location_id"] != location["location_id"]:
            continue
        if row["zone_id"] is not None and row["zone_id"] != location["zone_id"]:
            continue
        if row["aisle_code"] is not None and row["aisle_code"] != location["aisle_code"]:
            continue
        return True
    return False


def _tx_value(row: TableRecord | None, column: str) -> int | str:
    return "" if row is None else int(row[column])


def _signed_minutes(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 60.0, 3)


def _parse_optional_utc(value: Any) -> datetime | None:
    return None if value is None else _parse_utc(str(value))


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
