from __future__ import annotations

import csv
import hashlib
import sqlite3
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

from operational_variance_toolkit.console.commands import CommandDispatcher
from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleSession
from operational_variance_toolkit.errors import (
    DataValidationError,
    OutputExistsError,
    RecordNotFoundError,
)
from operational_variance_toolkit.wms.application.export import (
    export_master_csv,
    export_report_result,
    export_transactions_csv,
    write_csv_atomic,
)
from operational_variance_toolkit.wms.application.inquiry import WmsInquiryService
from operational_variance_toolkit.wms.application.reports import (
    available_reports,
    run_wms_report,
)
from operational_variance_toolkit.wms.storage.inquiry import (
    INVENTORY_COLUMNS,
    ITEM_COLUMNS,
    LOCATION_COLUMNS,
    TRANSACTION_COLUMNS,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_session(database: Path, tmp_path: Path) -> ConsoleSession:
    session = ConsoleSession(tmp_path, tmp_path / "exports")
    session.open_database(database)
    return session


def _dispatcher(
    database: Path, tmp_path: Path
) -> tuple[ConsoleSession, CommandDispatcher, StringIO, StringIO]:
    stdout, stderr = StringIO(), StringIO()
    session = _open_session(database, tmp_path)
    dispatcher = CommandDispatcher(
        session,
        ConsoleRenderer(stdout, stderr, no_style=True),
        ResourceResolver(tmp_path),
    )
    return session, dispatcher, stdout, stderr


@pytest.mark.parametrize(
    ("method", "identifier", "title"),
    [
        ("item", "ITEM-0003", "Item"),
        ("location", "LOC-00003", "Location"),
        ("inventory_location", "LOC-00003", "Inventory Location"),
        ("inventory_item", "ITEM-0003", "Inventory by Item"),
        ("trip", "TRIP-000005", "Trip"),
        ("pick", "PICK-000006", "Pick"),
        ("replenishment", "REPL-000372", "Replenishment"),
        ("qa", "QA-000140", "QA Event"),
        ("adjustment", "ADJ-000141", "Adjustment"),
    ],
)
def test_typed_detail_inquiries_cover_operational_records(
    method: str,
    identifier: str,
    title: str,
    phase2_wms_path: Path,
    tmp_path: Path,
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        result = getattr(WmsInquiryService(session.connection), method)(identifier)

    assert result.title == title
    assert result.total_count == len(result.rows) > 0
    assert all(len(row) == len(result.columns) for row in result.rows)


def test_not_found_is_distinct_and_query_only_is_required(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        service = WmsInquiryService(session.connection)
        with pytest.raises(RecordNotFoundError, match="Item ID MISSING"):
            service.item("MISSING")

    with sqlite3.connect(phase2_wms_path) as writable:
        with pytest.raises(DataValidationError, match="query-only"):
            WmsInquiryService(writable)
        with pytest.raises(DataValidationError, match="query-only"):
            export_master_csv(writable, "item-master", tmp_path / "unsafe.csv")


@pytest.mark.parametrize(
    "method",
    [
        "item",
        "location",
        "inventory_location",
        "inventory_item",
        "trip",
        "pick",
        "replenishment",
        "qa",
        "adjustment",
    ],
)
def test_every_detail_inquiry_distinguishes_not_found(
    method: str, phase2_wms_path: Path, tmp_path: Path
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        service = WmsInquiryService(session.connection)
        with pytest.raises(RecordNotFoundError, match="not found"):
            getattr(service, method)("MISSING")


def test_inquiry_repository_matches_direct_schema_rows(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        service = WmsInquiryService(session.connection)
        item = service.item("ITEM-0003")
        direct_item = session.connection.execute(
            "SELECT * FROM item_master WHERE item_id = ?", ("ITEM-0003",)
        ).fetchone()
        transactions = service.transactions({"transaction_group": "TXG-000374"})
        direct_transactions = session.connection.execute(
            "SELECT * FROM inventory_transaction WHERE transaction_group_id = ? "
            "ORDER BY event_sequence, line_number, transaction_id",
            ("TXG-000374",),
        ).fetchall()

    assert item.rows == (tuple(direct_item),)
    assert transactions.rows == tuple(tuple(row) for row in direct_transactions)


@pytest.mark.parametrize(
    ("filter_name", "value"),
    [
        ("item", "ITEM-0024"),
        ("location", "LOC-05024"),
        ("transaction_group", "TXG-000374"),
        ("command", "BASE-REPL-CONFIRM-000001"),
    ],
)
def test_transaction_filters_are_stable_and_parameterized(
    filter_name: str, value: str, phase2_wms_path: Path, tmp_path: Path
) -> None:
    before = _sha256(phase2_wms_path)
    with _open_session(phase2_wms_path, tmp_path) as session:
        result = WmsInquiryService(session.connection).transactions({filter_name: value})

    assert result.rows
    assert tuple((row[4], row[5], row[1]) for row in result.rows) == tuple(
        sorted((row[4], row[5], row[1]) for row in result.rows)
    )
    assert _sha256(phase2_wms_path) == before


def test_transaction_filter_rejects_sql_structure_and_normalizes_offsets(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        service = WmsInquiryService(session.connection)
        with pytest.raises(DataValidationError, match="Unsupported"):
            service.transactions({"item OR 1=1": "ITEM-0003"})
        result = service.transactions(
            {
                "start_utc": "2026-05-04T03:00:00-04:00",
                "end_utc": "2026-05-04T03:01:00-04:00",
            }
        )
    assert isinstance(result.rows, tuple)


@pytest.mark.parametrize(
    ("identifier", "resolved_by", "line_count", "net", "conservation"),
    [
        ("BASE-PICK-000001", "command_id", 1, -1, "NOT APPLICABLE"),
        ("TXG-000374", "transaction_group_id", 2, 0, "BALANCED"),
        ("REPL-000372", "source_record_id", 2, 0, "BALANCED"),
        ("ADJ-000141", "source_record_id", 1, -1, "NOT APPLICABLE"),
        ("BASE-QA-000001", "command_id", 0, 0, "NOT APPLICABLE"),
        ("SNAPSHOT-001283", "source_record_id", 0, 0, "NOT APPLICABLE"),
    ],
)
def test_trace_resolves_audit_forms_and_reconciles_quantity(
    identifier: str,
    resolved_by: str,
    line_count: int,
    net: int,
    conservation: str,
    phase2_wms_path: Path,
    tmp_path: Path,
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        result = WmsInquiryService(session.connection).trace(identifier)

    assert result.resolved_by == resolved_by
    assert len(result.transactions.rows) == line_count
    assert result.net_quantity_delta_cases == net
    assert result.conservation_status == conservation
    assert result.commands.rows
    if line_count:
        for row in result.transactions.rows:
            assert row[12] == row[11] + row[10]


def test_replenishment_trace_has_create_start_confirm_chronology(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        result = WmsInquiryService(session.connection).trace("REPL-000372")

    assert tuple(row[2] for row in result.commands.rows) == (
        "CreateReplenishmentTask",
        "StartReplenishmentTask",
        "ConfirmReplenishmentTask",
    )
    assert tuple(row[7] for row in result.commands.rows) == tuple(
        sorted(row[7] for row in result.commands.rows)
    )
    assert result.transactions.rows[0][8] == result.transactions.rows[1][7]
    assert result.transactions.rows[1][8] == result.transactions.rows[0][7]


def test_adjustment_and_no_delta_system_workflow_trace_fixtures(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    with _open_session(phase2_wms_path, tmp_path) as session:
        service = WmsInquiryService(session.connection)
        adjustment = service.trace("ADJ-000141")
        system_command = session.connection.execute(
            "SELECT command_id FROM system_event ORDER BY event_sequence LIMIT 1"
        ).fetchone()[0]
        trip_command = session.connection.execute(
            "SELECT command_id FROM wms_command WHERE result_record_type = 'TRIP' "
            "ORDER BY event_sequence LIMIT 1"
        ).fetchone()[0]
        system = service.trace(system_command)
        trip = service.trace(trip_command)

    line = adjustment.transactions.rows[0]
    assert (line[11], line[10], line[12]) == (38, -1, 37)
    assert not system.transactions.rows
    assert system.workflow.title == "System Event"
    assert not trip.transactions.rows
    assert trip.workflow.title == "Trip"


@pytest.mark.parametrize(
    ("dataset", "columns", "expected_rows"),
    [
        ("item-master", ITEM_COLUMNS, 96),
        ("location-master", LOCATION_COLUMNS, 192),
        ("inventory-master", INVENTORY_COLUMNS, 192),
    ],
)
def test_master_exports_have_canonical_columns_counts_and_hashes(
    dataset: str,
    columns: tuple[str, ...],
    expected_rows: int,
    phase2_wms_path: Path,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first path" / f"{dataset}.csv"
    second = tmp_path / "second path" / f"{dataset}.csv"
    with _open_session(phase2_wms_path, tmp_path) as session:
        first_result = export_master_csv(session.connection, dataset, first)
        second_result = export_master_csv(session.connection, dataset, second)

    with first.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == columns
    assert len(rows) - 1 == first_result.row_count == expected_rows
    assert first_result.sha256 == _sha256(first)
    assert first.read_bytes() == second.read_bytes()
    assert first_result.sha256 == second_result.sha256
    assert not tuple(first.parent.glob(".*.tmp"))


def test_transaction_and_report_exports_match_read_models_and_refuse_overwrite(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    tx_path = tmp_path / "transaction export.csv"
    report_path = tmp_path / "report export.csv"
    with _open_session(phase2_wms_path, tmp_path) as session:
        tx_result = export_transactions_csv(
            session.connection,
            tx_path,
            {"transaction_group": "TXG-000374"},
        )
        report = run_wms_report(phase2_wms_path, "inventory-by-item", {"item": "ITEM-0003"})
        report_result = export_report_result(report, report_path)
        with pytest.raises(OutputExistsError):
            export_transactions_csv(session.connection, tx_path, {})

    with tx_path.open(encoding="utf-8", newline="") as handle:
        tx_rows = list(csv.reader(handle))
    with report_path.open(encoding="utf-8", newline="") as handle:
        report_rows = list(csv.reader(handle))
    assert tuple(tx_rows[0]) == TRANSACTION_COLUMNS
    assert tx_result.row_count == len(tx_rows) - 1 == 2
    assert tuple(report_rows[0]) == report.spec.display_columns
    assert report_result.row_count == len(report.rows)


def test_csv_formula_safety_includes_identifiers_and_preserves_numbers(tmp_path: Path) -> None:
    path = tmp_path / "formula.csv"
    result = write_csv_atomic(
        path,
        ("item_id", "qty_cases", "item_description", "reason_code"),
        (("=CANONICAL-ID", -3, "=2+2", "+CALC"),),
    )

    with path.open(encoding="utf-8", newline="") as handle:
        row = list(csv.reader(handle))[1]
    assert row == ["'=CANONICAL-ID", "-3", "'=2+2", "'+CALC"]
    assert result.sha256 == _sha256(path)


def test_all_twelve_reports_execute_through_console_with_required_parameters(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    session, dispatcher, stdout, stderr = _dispatcher(phase2_wms_path, tmp_path)
    closing_batch = session.connection.execute(
        "SELECT snapshot_batch_id FROM inventory_snapshot "
        "WHERE snapshot_type = 'CLOSING_SYSTEM' LIMIT 1"
    ).fetchone()[0]
    commands = {
        "code-date-inventory": "--as-of-date 2026-05-14",
        "inventory-snapshot": f"--snapshot-batch {closing_batch}",
        "inventory-reconciliation": f"--snapshot-batch {closing_batch}",
    }

    assert dispatcher.dispatch_line("reports").succeeded
    for spec in available_reports():
        suffix = commands.get(spec.code, "")
        assert dispatcher.dispatch_line(f"report {spec.code} {suffix}".strip()).succeeded
    session.close()

    output = stdout.getvalue()
    assert all(spec.code in output for spec in available_reports())
    assert stderr.getvalue() == ""


def test_console_report_result_matches_one_shot_application_result(
    phase2_wms_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, dispatcher, _stdout, stderr = _dispatcher(phase2_wms_path, tmp_path)
    captured = []
    monkeypatch.setattr(
        dispatcher._renderer, "report", lambda result, _session: captured.append(result)
    )

    assert dispatcher.dispatch_line(
        "report inventory-transaction-inquiry --item ITEM-0003"
    ).succeeded
    expected = run_wms_report(
        phase2_wms_path,
        "inventory-transaction-inquiry",
        {"item": "ITEM-0003"},
    )
    session.close()

    assert len(captured) == 1
    assert captured[0].spec == expected.spec
    assert captured[0].parameters == expected.parameters
    assert captured[0].rows == expected.rows
    assert stderr.getvalue() == ""


def test_console_commands_settings_limits_exports_and_trace_preserve_source(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    before = _sha256(phase2_wms_path)
    session, dispatcher, stdout, stderr = _dispatcher(phase2_wms_path, tmp_path)
    commands = (
        "ITEM ITEM-0003",
        "item ITEM-0003 --technical",
        "location LOC-00003",
        "inventory location LOC-00003",
        "set limit 1",
        "inventory item ITEM-0003",
        "transactions group TXG-000374",
        "trace BASE-REPL-CONFIRM-000001",
        "set format table",
        "set timestamps both",
        "show settings",
        'export item-master "exports with spaces/items.csv"',
        'export inventory-transactions "exports with spaces/tx.csv" --transaction-group TXG-000374',
    )
    for command in commands:
        assert dispatcher.dispatch_line(command).succeeded, command
    session.close()

    output = stdout.getvalue()
    assert "Item ID" in output
    assert "item_id" in output
    assert "Transfer conservation: BALANCED" in output
    assert "Result limit: 1" in output
    assert "Showing 1 of 2 record(s)." in output
    assert "use set limit <n> or export CSV" in output
    assert "Timestamp preference: both" in output
    assert output.count("SHA-256:") == 2
    assert "Rows: 96" in output
    assert "Rows: 2" in output
    assert "\x1b" not in output
    assert stderr.getvalue() == ""
    assert _sha256(phase2_wms_path) == before


def test_console_not_found_and_malicious_options_are_helpful(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    session, dispatcher, _stdout, stderr = _dispatcher(phase2_wms_path, tmp_path)

    assert not dispatcher.dispatch_line("item MISSING").succeeded
    assert not dispatcher.dispatch_line(
        "report inventory-by-item --item ITEM-0003 --sql DROP"
    ).succeeded
    assert not dispatcher.dispatch_line(
        'export inventory-transactions "x.csv" --where "1=1"'
    ).succeeded
    session.close()

    errors = stderr.getvalue()
    assert "Not found:" in errors
    assert "does not accept parameter(s): sql" in errors
    assert "Unsupported transaction filter(s): where" in errors


def test_phase2_redirected_session_is_plain_and_preserves_source(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    before = _sha256(phase2_wms_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "operational_variance_toolkit",
            "console",
            "--database",
            str(phase2_wms_path),
            "--no-style",
        ],
        input="item ITEM-0003\ntrace BASE-QA-000001\nreports\nexit\n",
        capture_output=True,
        check=False,
        cwd=tmp_path,
        text=True,
    )

    assert result.returncode == 0
    assert "Item ID" in result.stdout
    assert "No inventory delta was recorded" in result.stdout
    assert "inventory-reconciliation" in result.stdout
    assert "\x1b" not in result.stdout + result.stderr
    assert _sha256(phase2_wms_path) == before


def test_phase2_read_paths_have_no_simulator_or_ground_truth_dependency() -> None:
    project_root = Path(__file__).resolve().parents[1]
    paths = (
        project_root / "src/operational_variance_toolkit/console/commands.py",
        project_root / "src/operational_variance_toolkit/wms/application/inquiry.py",
        project_root / "src/operational_variance_toolkit/wms/application/export.py",
        project_root / "src/operational_variance_toolkit/wms/storage/inquiry.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "simulation.physical" not in source
    assert "ground_truth" not in source
