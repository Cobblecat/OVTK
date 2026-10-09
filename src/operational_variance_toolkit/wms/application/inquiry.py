"""Application services for factual schema-3 WMS inquiry and trace."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime

from operational_variance_toolkit.errors import DataValidationError, RecordNotFoundError
from operational_variance_toolkit.wms.domain.inquiry import InquiryResult, TraceResult
from operational_variance_toolkit.wms.storage.inquiry import (
    INVENTORY_COLUMNS,
    ITEM_COLUMNS,
    LOCATION_COLUMNS,
    TRANSACTION_COLUMNS,
    WmsInquiryRepository,
)

_TRANSACTION_FILTERS = frozenset(
    {
        "item",
        "location",
        "operator",
        "transaction_group",
        "command",
        "source_record",
        "start_utc",
        "end_utc",
    }
)

_PICK_COLUMNS = (
    "run_id",
    "pick_event_id",
    "command_id",
    "event_sequence",
    "trip_id",
    "selector_id",
    "item_id",
    "pick_location_id",
    "event_utc",
    "recorded_utc",
    "requested_qty_cases",
    "picked_qty_cases",
    "short_qty_cases",
    "short_reason_code",
    "system_qty_before_cases",
    "system_qty_after_cases",
    "eligible_pick_flag",
    "transaction_id",
    "transaction_group_id",
)

_REPLENISHMENT_COLUMNS = (
    "run_id",
    "replenishment_task_id",
    "create_command_id",
    "confirm_command_id",
    "event_sequence",
    "item_id",
    "source_location_id",
    "destination_location_id",
    "operator_id",
    "created_utc",
    "started_utc",
    "confirmed_utc",
    "recorded_utc",
    "requested_qty_cases",
    "confirmed_qty_cases",
    "status",
    "delay_reason_code",
    "start_command_id",
    "transaction_group_id",
)

_QA_COLUMNS = (
    "run_id",
    "qa_event_id",
    "command_id",
    "event_sequence",
    "item_id",
    "location_id",
    "operator_id",
    "event_type",
    "occurred_utc",
    "recorded_utc",
    "qty_affected_cases",
    "reason_code",
    "disposition_code",
)

_ADJUSTMENT_COLUMNS = (
    "run_id",
    "adjustment_id",
    "command_id",
    "event_sequence",
    "item_id",
    "location_id",
    "operator_id",
    "effective_utc",
    "recorded_utc",
    "qty_delta_cases",
    "reason_code",
    "reference_code",
    "transaction_id",
    "transaction_group_id",
    "balance_before_cases",
    "balance_after_cases",
)


class WmsInquiryService:
    """Coordinate typed inquiries over an already protected read-only connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        repository = WmsInquiryRepository(connection)
        if not repository.query_only_enabled():
            raise DataValidationError("Inquiry services require a query-only connection")
        self._repository = repository

    def item(self, item_id: str) -> InquiryResult:
        return self._detail("Item", item_id, ITEM_COLUMNS, self._repository.item(item_id))

    def location(self, location_id: str) -> InquiryResult:
        columns = LOCATION_COLUMNS + ("zone_code",)
        return self._detail(
            "Location", location_id, columns, self._repository.location(location_id)
        )

    def inventory_location(self, location_id: str) -> InquiryResult:
        columns = INVENTORY_COLUMNS + ("location_type", "zone_code", "item_description")
        return self._detail(
            "Inventory Location",
            location_id,
            columns,
            self._repository.inventory_by_location(location_id),
        )

    def inventory_item(self, item_id: str) -> InquiryResult:
        columns = (
            "location_id",
            "location_type",
            "zone_code",
            "item_id",
            "qty_on_hand_cases",
            "code_date",
            "reorder_trigger_cases",
            "minimum_qty_cases",
            "target_qty_cases",
            "maximum_qty_cases",
            "last_transaction_id",
            "last_updated_utc",
        )
        rows = self._repository.inventory_by_item(item_id)
        if not rows:
            raise RecordNotFoundError(f"Inventory for Item ID {item_id} was not found")
        return InquiryResult("Inventory by Item", columns, rows, len(rows))

    def trip(self, trip_id: str) -> InquiryResult:
        columns = (
            "run_id",
            "trip_id",
            "shift_id",
            "selector_id",
            "assigned_zone_id",
            "zone_code",
            "start_utc",
            "end_utc",
            "continuation_flag",
            "planned_pick_lines",
            "planned_cases",
            "recorded_pick_lines",
            "requested_cases",
            "picked_cases",
            "short_cases",
        )
        return self._detail("Trip", trip_id, columns, self._repository.trip(trip_id))

    def pick(self, pick_id: str) -> InquiryResult:
        return self._detail("Pick", pick_id, _PICK_COLUMNS, self._repository.pick(pick_id))

    def replenishment(self, task_id: str) -> InquiryResult:
        return self._detail(
            "Replenishment",
            task_id,
            _REPLENISHMENT_COLUMNS,
            self._repository.replenishment(task_id),
        )

    def qa(self, qa_id: str) -> InquiryResult:
        return self._detail("QA Event", qa_id, _QA_COLUMNS, self._repository.qa(qa_id))

    def adjustment(self, adjustment_id: str) -> InquiryResult:
        return self._detail(
            "Adjustment",
            adjustment_id,
            _ADJUSTMENT_COLUMNS,
            self._repository.adjustment(adjustment_id),
        )

    def transactions(self, filters: Mapping[str, str]) -> InquiryResult:
        clean = validate_transaction_filters(filters)
        rows = self._repository.transactions(clean)
        return InquiryResult("Inventory Transactions", TRANSACTION_COLUMNS, rows, len(rows))

    def trace(self, identifier: str) -> TraceResult:
        command_rows = self._repository.trace_commands(identifier)
        if not command_rows:
            raise RecordNotFoundError(f"Trace identifier {identifier} was not found")
        command_columns = (
            "run_id",
            "command_id",
            "command_type",
            "payload_hash",
            "accepted_utc",
            "result_record_type",
            "result_record_id",
            "event_sequence",
            "event_type",
            "event_utc",
            "recorded_utc",
        )
        command_ids = {str(row[1]) for row in command_rows}
        result_ids = {str(row[6]) for row in command_rows}
        transaction_rows = self._repository.trace_transactions(identifier)
        if identifier in command_ids:
            resolved_by = "command_id"
        elif any(str(row[2]) == identifier for row in transaction_rows):
            resolved_by = "transaction_group_id"
        elif identifier in result_ids or any(
            str(row[18]) == identifier for row in transaction_rows
        ):
            resolved_by = "source_record_id"
        else:
            resolved_by = "linked_record"

        workflow_parts: list[tuple[object, ...]] = []
        workflow_columns: tuple[str, ...] = ()
        workflow_title = "Workflow Record"
        seen: set[tuple[str, str]] = set()
        for row in command_rows:
            key = (str(row[5]), str(row[6]))
            if key in seen:
                continue
            seen.add(key)
            title, columns, rows = self._repository.trace_workflow(*key)
            if columns and (not workflow_columns or columns == workflow_columns):
                workflow_title = title
                workflow_columns = columns
                workflow_parts.extend(rows)

        live_rows = self._repository.live_inventory_for_transactions(transaction_rows)
        net_delta = sum(int(row[10]) for row in transaction_rows)
        transaction_types = {str(row[6]) for row in transaction_rows}
        if {"TRANSFER_OUT", "TRANSFER_IN"}.issubset(transaction_types):
            conservation = "BALANCED" if _transfer_is_balanced(transaction_rows) else "UNBALANCED"
        else:
            conservation = "NOT APPLICABLE"
        return TraceResult(
            identifier=identifier,
            resolved_by=resolved_by,
            commands=InquiryResult(
                "WMS Commands", command_columns, command_rows, len(command_rows)
            ),
            workflow=InquiryResult(
                workflow_title,
                workflow_columns,
                tuple(workflow_parts),
                len(workflow_parts),
            ),
            transactions=InquiryResult(
                "Inventory Transactions",
                TRANSACTION_COLUMNS,
                transaction_rows,
                len(transaction_rows),
            ),
            live_inventory=InquiryResult(
                "Final Live Inventory",
                (
                    "location_id",
                    "item_id",
                    "qty_on_hand_cases",
                    "code_date",
                    "last_transaction_id",
                    "last_updated_utc",
                ),
                live_rows,
                len(live_rows),
            ),
            net_quantity_delta_cases=net_delta,
            conservation_status=conservation,
        )

    @staticmethod
    def _detail(
        title: str,
        identifier: str,
        columns: tuple[str, ...],
        rows: tuple[tuple[object, ...], ...],
    ) -> InquiryResult:
        if not rows:
            raise RecordNotFoundError(f"{title} ID {identifier} was not found")
        return InquiryResult(title, columns, rows, len(rows))


def validate_transaction_filters(filters: Mapping[str, str]) -> dict[str, str]:
    clean = {key: value.strip() for key, value in filters.items() if value.strip()}
    unsupported = sorted(set(clean) - _TRANSACTION_FILTERS)
    if unsupported:
        raise DataValidationError(f"Unsupported transaction filter(s): {', '.join(unsupported)}")
    for name in ("start_utc", "end_utc"):
        if name in clean:
            clean[name] = _normalize_utc(clean[name], name)
    if "start_utc" in clean and "end_utc" in clean:
        if clean["start_utc"] > clean["end_utc"]:
            raise DataValidationError("start_utc cannot follow end_utc")
    return clean


def _normalize_utc(value: str, name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataValidationError(f"{name} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise DataValidationError(f"{name} must be timezone-aware")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _transfer_is_balanced(rows: tuple[tuple[object, ...], ...]) -> bool:
    transfer_rows = tuple(row for row in rows if str(row[6]).startswith("TRANSFER_"))
    if len(transfer_rows) != 2:
        return False
    outgoing = next((row for row in transfer_rows if row[6] == "TRANSFER_OUT"), None)
    incoming = next((row for row in transfer_rows if row[6] == "TRANSFER_IN"), None)
    if outgoing is None or incoming is None:
        return False
    return (
        int(outgoing[10]) < 0
        and int(incoming[10]) == -int(outgoing[10])
        and outgoing[9] == incoming[9]
        and outgoing[2] == incoming[2]
        and outgoing[8] == incoming[7]
        and incoming[8] == outgoing[7]
    )
