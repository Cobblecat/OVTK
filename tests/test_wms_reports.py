"""Focused Slice 3 tests for schema-3 WMS reports."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.storage.database import connect_database
from operational_variance_toolkit.wms.application.initialize import initialize_wms_foundation
from operational_variance_toolkit.wms.application.reports import (
    available_reports,
    export_report_csv,
    run_wms_report,
)
from operational_variance_toolkit.wms.application.service import WmsService
from operational_variance_toolkit.wms.domain.commands import (
    AdjustInventory,
    CreateReplenishmentTask,
    RecordQaEvent,
)

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


@pytest.fixture()
def wms_db(baseline_config_path, tmp_path: Path):
    path = tmp_path / "foundation.sqlite3"
    result = initialize_wms_foundation(baseline_config_path, path, generated_at_utc=NOW)
    yield path, result.run_metadata.run_id


def test_all_registered_reports_have_stable_schema_and_can_be_empty(wms_db):
    path, _ = wms_db
    specs = available_reports()
    assert len(specs) == 12
    for spec in specs:
        params = {key: "2026-05-04" for key in spec.required_parameters if key == "as_of_date"}
        params.update(
            {
                key: "SNAPSHOT-OPENING-001"
                for key in spec.required_parameters
                if key == "snapshot_batch"
            }
        )
        result = run_wms_report(path, spec.code, params, generated_at_utc=NOW)
        assert tuple(result.spec.columns) == spec.columns
        assert len(result.spec.display_columns) == len(spec.columns)
        repeat = run_wms_report(path, spec.code, params, generated_at_utc=NOW)
        assert result.rows == repeat.rows
    assert (
        run_wms_report(path, "inventory-transaction-inquiry", {"item": "NO-SUCH-ITEM"}).rows == ()
    )


def test_report_titles_display_labels_and_empty_classifications(wms_db):
    path, _ = wms_db
    specs = {spec.code: spec for spec in available_reports()}
    assert "Item ID" in specs["inventory-by-location"].display_columns
    assert "Recorded Occupied" in specs["location-profile"].display_columns
    assert "Empty Location Classification" in specs["empty-locations"].display_columns
    assert "Recorded Compatible Reserve Quantity" in specs["replenishment-needs"].display_columns
    assert {
        "Operational Event Time",
        "WMS Recorded Time",
        "Source Reference",
    } <= set(specs["inventory-transaction-inquiry"].display_columns)
    assert "Source Reference" in specs["adjustment-history"].display_columns
    assert {
        "QA Observed Quantity",
        "Operational Event Time",
        "WMS Recorded Time",
    } <= set(specs["qa-activity"].display_columns)
    assert specs["inventory-snapshot"].name == "Recorded Inventory Snapshot"
    assert specs["inventory-reconciliation"].name == "Live-versus-Snapshot Reconciliation"
    assert set(specs["inventory-by-location"].columns) >= {
        "location_id",
        "item_id",
        "qty_on_hand_cases",
    }
    empty = run_wms_report(path, "empty-locations", generated_at_utc=NOW)
    classifications = {row[9] for row in empty.rows}
    assert classifications >= {"Unassigned Empty Reserve", "Assigned Zero-Quantity Pick Slot"}


def test_core_reports_agree_with_direct_sql_and_capacity_is_dynamic(wms_db):
    path, run_id = wms_db
    connection = connect_database(path)
    try:
        by_location = run_wms_report(path, "inventory-by-location", generated_at_utc=NOW)
        direct = connection.execute(
            "SELECT location_id, qty_on_hand_cases FROM inventory_master "
            "WHERE run_id = ? ORDER BY location_id",
            (run_id,),
        ).fetchall()
        assert sorted((row[0], row[12]) for row in by_location.rows) == [
            tuple(row) for row in direct
        ]
        by_item = run_wms_report(path, "inventory-by-item", generated_at_utc=NOW)
        direct_items = connection.execute(
            "SELECT item_id, SUM(qty_on_hand_cases) FROM inventory_master "
            "WHERE run_id = ? AND item_id IS NOT NULL GROUP BY item_id ORDER BY item_id",
            (run_id,),
        ).fetchall()
        assert [(row[0], row[4]) for row in by_item.rows] == [tuple(row) for row in direct_items]
        transactions = run_wms_report(path, "inventory-transaction-inquiry", generated_at_utc=NOW)
        direct_transactions = connection.execute(
            "SELECT transaction_id FROM inventory_transaction ORDER BY event_sequence, line_number"
        )
        assert sorted(row[0] for row in transactions.rows) == sorted(
            row[0] for row in direct_transactions
        )
        for row in by_location.rows:
            assert row[15] is None or row[16] == row[15] - row[12]
            assert row[17] is None or 0 <= row[17] <= 100
    finally:
        connection.close()


def test_assigned_zero_pick_is_empty_but_not_unassigned(wms_db):
    path, run_id = wms_db
    connection = connect_database(path)
    try:
        pick = connection.execute(
            "SELECT inventory.item_id, inventory.location_id, "
            "inventory.qty_on_hand_cases FROM inventory_master AS inventory "
            "JOIN location_master AS location USING(run_id, location_id) "
            "WHERE inventory.run_id = ? AND inventory.item_id IS NOT NULL "
            "AND inventory.qty_on_hand_cases > 0 AND location.location_type = 'PICK' "
            "LIMIT 1",
            (run_id,),
        ).fetchone()
        assert pick is not None
        operator = connection.execute(
            "SELECT operator_id FROM operator WHERE run_id = ? "
            "AND role = 'INVENTORY_CONTROL' LIMIT 1",
            (run_id,),
        ).fetchone()[0]
        service = WmsService(connection)
        service.adjust_inventory(
            AdjustInventory(
                run_id=run_id,
                command_id="REPORT-ADJ-001",
                event_utc=NOW,
                recorded_utc=NOW,
                item_id=pick[0],
                location_id=pick[1],
                operator_id=operator,
                qty_delta_cases=-pick[2],
                reason_code="COUNT_CORRECTION",
            )
        )
        reserve_location = connection.execute(
            """
            SELECT inventory.location_id
            FROM inventory_master AS inventory
            JOIN location_master AS location USING(run_id, location_id)
            WHERE inventory.run_id = ? AND inventory.item_id = ?
                AND location.location_type = 'RESERVE'
                AND inventory.qty_on_hand_cases > 0
            LIMIT 1
            """,
            (run_id, pick[0]),
        ).fetchone()[0]
        replenisher = connection.execute(
            "SELECT operator_id FROM operator WHERE run_id = ? AND role = 'REPLENISHMENT' LIMIT 1",
            (run_id,),
        ).fetchone()[0]
        qa_operator = connection.execute(
            "SELECT operator_id FROM operator WHERE run_id = ? AND role = 'QA' LIMIT 1",
            (run_id,),
        ).fetchone()[0]
        task = service.create_replenishment(
            CreateReplenishmentTask(
                run_id=run_id,
                command_id="REPORT-REPL-001",
                event_utc=NOW,
                recorded_utc=NOW,
                item_id=pick[0],
                source_location_id=reserve_location,
                destination_location_id=pick[1],
                requested_qty_cases=1,
                operator_id=replenisher,
            )
        )
        service.record_qa_event(
            RecordQaEvent(
                run_id=run_id,
                command_id="REPORT-QA-001",
                event_utc=NOW,
                recorded_utc=NOW,
                item_id=pick[0],
                location_id=pick[1],
                operator_id=qa_operator,
                event_type="COUNT_VERIFICATION",
                qty_affected_cases=1,
                reason_code="CHECK",
                disposition_code="NO_ACTION",
            )
        )
    finally:
        connection.close()
    empty = run_wms_report(path, "empty-locations", generated_at_utc=NOW)
    zero_pick = next(row for row in empty.rows if row[0] == pick[1])
    assert zero_pick[8] == pick[0]
    location = next(
        row
        for row in run_wms_report(path, "inventory-by-location", generated_at_utc=NOW).rows
        if row[0] == pick[1]
    )
    assert location[10] == pick[0] and location[12] == 0
    adjustment = run_wms_report(path, "adjustment-history", generated_at_utc=NOW)
    transaction = run_wms_report(
        path,
        "inventory-transaction-inquiry",
        {"item": pick[0]},
        generated_at_utc=NOW,
    )
    qa = run_wms_report(path, "qa-activity", generated_at_utc=NOW)
    report_time = {"as_of_utc": NOW.isoformat()}
    open_tasks = run_wms_report(path, "open-replenishment-tasks", report_time, generated_at_utc=NOW)
    needs = run_wms_report(path, "replenishment-needs", report_time, generated_at_utc=NOW)
    assert adjustment.rows[0][0] == "ADJ-000001"
    assert transaction.rows[0][6] == pick[0]
    assert qa.rows[0][0] == "QA-000003"
    assert open_tasks.rows[0][0] == task.result_record_id
    assert next(row for row in needs.rows if row[1] == pick[1])[10] == task.result_record_id


def test_parameters_snapshot_reconciliation_and_csv_are_safe(wms_db, tmp_path: Path):
    path, _ = wms_db
    before = hashlib.sha256(path.read_bytes()).digest()
    with pytest.raises(DataValidationError, match="requires parameter"):
        run_wms_report(path, "code-date-inventory")
    with pytest.raises(DataValidationError, match="start_utc cannot follow"):
        run_wms_report(
            path,
            "qa-activity",
            {"start_utc": "2026-05-05T00:00:00+00:00", "end_utc": "2026-05-04T00:00:00+00:00"},
        )
    snapshot = run_wms_report(
        path, "inventory-snapshot", {"snapshot_batch": "SNAPSHOT-OPENING-001"}, generated_at_utc=NOW
    )
    reconciliation = run_wms_report(
        path,
        "inventory-reconciliation",
        {"snapshot_batch": "SNAPSHOT-OPENING-001"},
        generated_at_utc=NOW,
    )
    assert snapshot.rows and {row[7] for row in reconciliation.rows} == {"MATCH"}
    output = tmp_path / "report.csv"
    repeat_output = tmp_path / "report-repeat.csv"
    export_report_csv(snapshot, output)
    export_report_csv(snapshot, repeat_output)
    assert output.read_bytes() == repeat_output.read_bytes()
    with pytest.raises(OutputExistsError):
        export_report_csv(snapshot, output)
    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_cli_report_surfaces_and_dependency_boundary(wms_db, run_tool, tmp_path: Path):
    path, _ = wms_db
    listed = run_tool("report", "--database", str(path), "--list")
    assert listed.returncode == 0 and "inventory-by-location" in listed.stdout
    shown = run_tool("report", "--database", str(path), "--name", "inventory-by-location")
    assert shown.returncode == 0 and "location_id" in shown.stdout
    output = tmp_path / "cli.csv"
    exported = run_tool(
        "report", "--database", str(path), "--name", "inventory-by-item", "--output", str(output)
    )
    assert exported.returncode == 0 and output.is_file() and "CSV output" in exported.stdout
    bad = run_tool("report", "--database", str(path), "--name", "not-a-report")
    assert bad.returncode != 0 and "Unknown WMS report" in bad.stderr
    assert (
        "scenario"
        not in Path("src/operational_variance_toolkit/wms/application/reports.py")
        .read_text()
        .lower()
    )
    assert (
        "ground_truth"
        not in Path("src/operational_variance_toolkit/wms/storage/reports.py").read_text().lower()
    )
