"""Plain console rendering with safe redirected-output behavior."""

from __future__ import annotations

import shutil
from datetime import datetime
from typing import TextIO
from zoneinfo import ZoneInfo

from prompt_toolkit.shortcuts import clear as clear_terminal

from operational_variance_toolkit.console.session import ConsoleMode, ConsoleSession
from operational_variance_toolkit.sandbox.domain import CloneSandboxResult
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.version import get_version
from operational_variance_toolkit.wms.application.describe import DescribeWmsResult
from operational_variance_toolkit.wms.domain.inquiry import ExportResult, InquiryResult, TraceResult
from operational_variance_toolkit.wms.domain.reports import ReportResult, ReportSpec
from operational_variance_toolkit.wms.storage.repositories import WMS_TABLES


class ConsoleRenderer:
    def __init__(self, stdout: TextIO, stderr: TextIO, *, no_style: bool = False) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.no_style = no_style or not stdout.isatty()

    def write(self, message: str = "") -> None:
        print(message, file=self._stdout)

    def error(self, message: str) -> None:
        print(f"Error: {message}", file=self._stderr)

    def not_found(self, message: str) -> None:
        print(f"Not found: {message}", file=self._stderr)

    def multiline_submission_error(self) -> None:
        print("Multiple commands in one submission are not supported.", file=self._stderr)
        print("Enter or paste one command at a time.", file=self._stderr)

    def banner(self) -> None:
        self.write(f"Operational Variance Toolkit {get_version()}")

    def opened_database(self, session: ConsoleSession) -> None:
        assert session.database_path is not None
        self.write(f"Database: {session.database_path.name}")
        self.write(f"Schema: {session.schema_version}")
        mode = "WRITABLE SANDBOX" if session.mode is ConsoleMode.SANDBOX else "READ-ONLY"
        self.write(f"Mode: {mode}")
        self.write("Validation: PASS")

    def cloned_sandbox(self, result: CloneSandboxResult) -> None:
        self.write("Sandbox created and verified.")
        self.write(f"Sandbox database: {result.database_path}")
        self.write(f"Sandbox manifest: {result.manifest_path}")
        self.write(f"Sandbox ID: {result.manifest.sandbox_id}")
        self.write(f"Source SHA-256: {result.manifest.source_database_sha256}")
        self.write(f"Initial sandbox SHA-256: {result.manifest.initial_sandbox_sha256}")

    def status(self, session: ConsoleSession) -> None:
        self.write("Session status")
        mode = {
            ConsoleMode.NO_DATABASE: "NO DATABASE",
            ConsoleMode.READ_ONLY: "READ-ONLY",
            ConsoleMode.SANDBOX: "WRITABLE SANDBOX",
        }[session.mode]
        self.write(f"Mode: {mode}")
        self.write(f"Working directory: {session.working_directory}")
        self.write(f"Output directory: {session.output_directory}")
        self.write(f"Result limit: {session.result_limit}")
        self.write(f"Display format: {session.display_format}")
        self.write(f"Timestamp preference: {session.timestamp_preference}")
        if session.database_path is None:
            self.write("Database: none")
            return
        self.write(f"Database: {session.database_path}")
        self.write(f"Schema version: {session.schema_version}")
        self.write(f"Run ID: {session.run_id}")
        self.write(f"Facility: {session.facility_id} ({session.facility_name})")
        self.write(f"Facility timezone: {session.facility_timezone}")
        self.write(f"Provenance: {session.provenance}")
        if session.mode is ConsoleMode.SANDBOX:
            sandbox = session.sandbox
            self.write(f"Sandbox ID: {sandbox.manifest.sandbox_id}")
            self.write(f"Source database: {sandbox.manifest.source_database_path}")
            self.write(f"Source SHA-256: {sandbox.manifest.source_database_sha256}")
            self.write(f"Sandbox created (UTC): {sandbox.manifest.created_at_utc}")
            self.write(
                f"Sandbox creation version: {sandbox.manifest.created_by_application_version}"
            )
            self.write(f"Current sandbox SHA-256: {sandbox.current_sha256}")
            self.write(f"Latest applied batch: {sandbox.latest_applied_batch_id or 'none'}")
            self.write("Supported write workflows: none at the Phase 3 checkpoint")
        if session.validation_checked_at_utc is not None:
            self.write(f"Validation checked (UTC): {session.validation_checked_at_utc.isoformat()}")
        if session.validation is not None:
            self.write(f"Validation status: {_validation_status(session.validation)}")

    def validation(self, result: ValidationResult) -> None:
        self.write(f"Validation status: {_validation_status(result)}")
        if result.hard_failures:
            self.write("Hard failures:")
            for issue in result.hard_failures:
                self.write(f"  [{issue.category}] {issue.message}")
        else:
            self.write("Hard failures: none")
        if result.warnings:
            self.write("Warnings:")
            for issue in result.warnings:
                self.write(f"  [{issue.category}] {issue.message}")
        else:
            self.write("Warnings: none")

    def description(self, result: DescribeWmsResult) -> None:
        metadata = result.run_metadata
        self.write("Schema-3 WMS description")
        self.write(f"Database path: {result.database_path}")
        self.write(f"Run ID: {metadata.run_id}")
        self.write(f"Seed: {metadata.seed}")
        self.write(f"Schema version: {metadata.schema_version}")
        self.write(f"Generator version: {metadata.generator_version}")
        self.write(f"Configuration SHA-256: {metadata.config_hash}")
        self.write(
            "Operating period (UTC): "
            f"{metadata.simulation_start_utc} to {metadata.simulation_end_utc}"
        )
        self.write(f"Facility timezone: {metadata.facility_timezone}")
        self.write("Table counts:")
        for table_name in WMS_TABLES:
            self.write(f"  {table_name}: {result.table_counts[table_name]}")
        self.write("Live inventory by zone:")
        for zone_code, qty_cases in result.live_totals_by_zone:
            self.write(f"  {zone_code}: {qty_cases} cases")
        self.write("Snapshot batches:")
        for batch_id, snapshot_type, snapshot_utc, row_count in result.snapshot_batches:
            self.write(f"  {batch_id}: {snapshot_type}, {snapshot_utc}, {row_count} rows")
        self.write(f"Validation status: {_validation_status(result.validation)}")

    def clear(self) -> None:
        if self._stdout.isatty():
            clear_terminal()
        else:
            self.write()

    def settings(self, session: ConsoleSession) -> None:
        self.write("Console settings")
        self.write(f"Result limit: {session.result_limit}")
        self.write(f"Display format: {session.display_format}")
        self.write(f"Timestamp preference: {session.timestamp_preference}")
        self.write(f"Output directory: {session.output_directory}")

    def inquiry(
        self, result: InquiryResult, session: ConsoleSession, *, technical: bool = False
    ) -> None:
        self.write(result.title)
        rows = result.rows[: session.result_limit]
        if not rows:
            self.write("No matching records.")
            return
        if session.display_format == "vertical" and len(rows) == 1:
            self._vertical(result.columns, rows[0], session, technical=technical)
        else:
            self._table(result.columns, rows, session, technical=technical)
        self._result_count(len(rows), result.total_count, session.result_limit)

    def reports(self, reports: tuple[ReportSpec, ...]) -> None:
        self.write("Standard WMS reports")
        for report in reports:
            parameters = ", ".join(report.parameters) or "none"
            required = ", ".join(sorted(report.required_parameters)) or "none"
            self.write(
                f"  {report.code}: {report.name} (parameters: {parameters}; required: {required})"
            )

    def report(self, result: ReportResult, session: ConsoleSession) -> None:
        self.write(f"{result.spec.name} [{result.spec.code}]")
        self.write(f"As of (UTC): {result.as_of_utc}")
        rows = result.rows[: session.result_limit]
        if rows:
            self._table(result.spec.display_columns, rows, session)
        else:
            self.write("No matching records.")
        self._result_count(len(rows), len(result.rows), session.result_limit)
        if result.rows:
            self.write("Export the report CSV for the full canonical column set.")

    def export(self, result: ExportResult) -> None:
        self.write(f"CSV created: {result.path}")
        self.write(f"Rows: {result.row_count}")
        self.write(f"SHA-256: {result.sha256}")

    def trace(self, result: TraceResult, session: ConsoleSession) -> None:
        self.write(f"Transaction trace: {result.identifier}")
        self.write(f"Resolved by: {_label(result.resolved_by)}")
        self._trace_commands(result.commands, session)
        if result.workflow.rows:
            self._trace_section(result.workflow, session)
        if result.transactions.rows:
            self._trace_transactions(result.transactions, session)
        else:
            self.write("Inventory Transactions")
            self.write("No inventory delta was recorded for this workflow event.")
        if result.live_inventory.rows:
            self._trace_section(result.live_inventory, session)
        self.write(f"Net quantity delta (cases): {result.net_quantity_delta_cases:+d}")
        self.write(f"Transfer conservation: {result.conservation_status}")

    def _trace_commands(self, result: InquiryResult, session: ConsoleSession) -> None:
        indexes = {name: index for index, name in enumerate(result.columns)}
        for number, row in enumerate(result.rows, start=1):
            self.write(f"WMS Command {number}")
            values = (
                ("Command ID", row[indexes["command_id"]]),
                (
                    "Operation Type",
                    _operation_name(str(row[indexes["command_type"]])),
                ),
                (
                    "Source Workflow",
                    _label(str(row[indexes["result_record_type"]]).lower()),
                ),
                ("Source Reference", row[indexes["result_record_id"]]),
                ("Event Sequence", row[indexes["event_sequence"]]),
                (
                    "Operational Event Time",
                    _display_value("event_utc", row[indexes["event_utc"]], session),
                ),
                (
                    "WMS Recorded Time",
                    _display_value("recorded_utc", row[indexes["recorded_utc"]], session),
                ),
            )
            width = max(len(label) for label, _value in values)
            for label, value in values:
                self.write(f"{label:<{width}} : {value}")

    def _trace_transactions(self, result: InquiryResult, session: ConsoleSession) -> None:
        indexes = {name: index for index, name in enumerate(result.columns)}
        for number, row in enumerate(result.rows, start=1):
            self.write(f"Inventory Transaction Line {number}")
            for column in (
                "transaction_id",
                "transaction_group_id",
                "transaction_type",
                "item_id",
                "operator_id",
                "location_id",
                "related_location_id",
                "qty_delta_cases",
                "balance_before_cases",
                "balance_after_cases",
                "event_utc",
                "recorded_utc",
                "source_record_id",
            ):
                value = _display_value(column, row[indexes[column]], session)
                self.write(f"{_label(column)}: {value}")

    def _trace_section(self, result: InquiryResult, session: ConsoleSession) -> None:
        self.write(result.title)
        if len(result.rows) == 1:
            self._vertical(result.columns, result.rows[0], session)
        else:
            self._table(result.columns, result.rows[: session.result_limit], session)

    def _vertical(
        self,
        columns: tuple[str, ...],
        row: tuple[object, ...],
        session: ConsoleSession,
        *,
        technical: bool = False,
    ) -> None:
        labels = tuple(column if technical else _label(column) for column in columns)
        width = max(len(label) for label in labels)
        for label, column, value in zip(labels, columns, row, strict=True):
            self.write(f"{label:<{width}} : {_display_value(column, value, session)}")

    def _table(
        self,
        columns: tuple[str, ...],
        rows: tuple[tuple[object, ...], ...],
        session: ConsoleSession,
        *,
        technical: bool = False,
    ) -> None:
        terminal_width = max(60, shutil.get_terminal_size(fallback=(120, 24)).columns)
        selected: list[tuple[int, str, int]] = []
        occupied = 0
        for index, column in enumerate(columns):
            label = column if technical else _label(column)
            values = [_display_value(column, row[index], session) for row in rows]
            width = min(28, max(len(label), *(len(value) for value in values)))
            next_width = width + (3 if selected else 0)
            if selected and occupied + next_width > terminal_width:
                break
            selected.append((index, label, width))
            occupied += next_width
        header = " | ".join(f"{label:<{width}}" for _index, label, width in selected)
        self.write(header.rstrip())
        self.write("-+-".join("-" * width for _index, _label_text, width in selected))
        for row in rows:
            cells = []
            for index, _label_text, width in selected:
                value = _display_value(columns[index], row[index], session)
                cells.append(f"{_truncate(value, width):<{width}}")
            self.write(" | ".join(cells).rstrip())
        if len(selected) < len(columns):
            self.write(f"Showing {len(selected)} of {len(columns)} columns at current width.")

    def _result_count(self, shown: int, total: int, limit: int) -> None:
        self.write(f"Showing {shown} of {total} record(s).")
        if shown < total:
            self.write(f"Results are limited to {limit}; use set limit <n> or export CSV.")


def _validation_status(result: ValidationResult) -> str:
    if result.passed:
        return "PASS"
    return f"FAIL ({len(result.hard_failures)} hard failure(s))"


_DISPLAY_LABELS = {
    "item_id": "Item ID",
    "location_id": "Location ID",
    "pick_location_id": "Pick Location ID",
    "qty_on_hand_cases": "Recorded Occupied",
    "available_reserve_cases": "Recorded Compatible Reserve Quantity",
    "event_utc": "Operational Event Time",
    "occurred_utc": "Operational Event Time",
    "effective_utc": "Operational Event Time",
    "recorded_utc": "WMS Recorded Time",
    "source_record_id": "Source Reference",
    "qty_affected_cases": "QA Observed Quantity",
    "snapshot_batch_id": "Recorded Inventory Snapshot",
}


def _label(column: str) -> str:
    return _DISPLAY_LABELS.get(column, column.replace("_", " ").title())


def _display_value(column: str, value: object, session: ConsoleSession) -> str:
    if value is None:
        return "-"
    text = str(value)
    if not (column.endswith("_utc") or "time" in column.lower()):
        return text
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    utc_text = parsed.isoformat().replace("+00:00", "Z")
    if session.timestamp_preference == "utc" or session.facility_timezone is None:
        return utc_text
    local_text = parsed.astimezone(ZoneInfo(session.facility_timezone)).isoformat()
    if session.timestamp_preference == "local":
        return local_text
    return f"{utc_text} / {local_text}"


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return f"{value[: width - 3]}..."


def _operation_name(value: str) -> str:
    words = []
    start = 0
    for index in range(1, len(value)):
        if value[index].isupper() and not value[index - 1].isupper():
            words.append(value[start:index])
            start = index
    words.append(value[start:])
    return " ".join(words)
