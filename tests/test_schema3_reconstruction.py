from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from operational_variance_toolkit.analysis.wms_reconstruction import (
    WmsReconstructionSourceData,
    WmsReconstructionTables,
    build_wms_reconstruction_tables,
    validate_wms_reconstruction_tables,
)
from operational_variance_toolkit.application.phase4 import reconstruct_database
from operational_variance_toolkit.application.wms_generation import generate_wms_baseline
from operational_variance_toolkit.application.wms_investigation import generate_wms_investigation
from operational_variance_toolkit.storage.database import connect_readonly_database
from operational_variance_toolkit.storage.wms_reconstruction import (
    WmsReconstructionSourceRepository,
)
from operational_variance_toolkit.wms.storage.repositories import WmsFoundationRepository

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)
INVESTIGATION_CONFIG = Path("configs/investigation.toml")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def baseline(baseline_config_path: Path, tmp_path: Path):
    database = tmp_path / "baseline.sqlite3"
    result = generate_wms_baseline(baseline_config_path, database, generated_at_utc=NOW)
    before = _sha256(database)
    reconstruction = reconstruct_database(database, tmp_path / "baseline-analysis")
    return result, reconstruction, before


def test_baseline_reconstruction_exports_expected_files_and_counts(baseline) -> None:
    _, result, source_checksum = baseline
    assert sorted(path.name for path in result.output_path.iterdir()) == [
        "analysis_manifest.json",
        "inventory_event_ledger.csv",
        "inventory_reconciliation.csv",
        "pick_context.csv",
        "qa_adjustment_context.csv",
        "replenishment_context.csv",
        "selector_exposure.csv",
    ]
    assert result.row_counts == {
        "inventory_event_ledger": 1283,
        "inventory_reconciliation": 192,
        "pick_context": 969,
        "replenishment_context": 59,
        "qa_adjustment_context": 3,
        "selector_exposure": 18,
    }
    assert result.source_sha256_before == source_checksum == result.source_sha256_after
    manifest = json.loads((result.output_path / "analysis_manifest.json").read_text())
    assert manifest["source"]["schema_version"] == "3.0.0"
    assert "scenario_name" not in manifest["source"]
    assert all("ground_truth" not in json.dumps(value).lower() for value in manifest.values())


def test_investigation_reconstructs_without_ground_truth_input(tmp_path: Path) -> None:
    database = tmp_path / "investigation.sqlite3"
    truth = tmp_path / "restricted.json"
    generated = generate_wms_investigation(INVESTIGATION_CONFIG, database, truth)
    result = reconstruct_database(database, tmp_path / "investigation-analysis")
    assert result.validation.passed
    assert result.reconciliation_status == "PASS"
    assert result.row_counts["inventory_event_ledger"] == 1499
    assert result.row_counts["inventory_reconciliation"] == 192
    assert result.row_counts["pick_context"] == 1133
    assert result.row_counts["replenishment_context"] == 78
    assert result.row_counts["qa_adjustment_context"] == 13
    assert result.row_counts["selector_exposure"] == 18
    assert generated.ground_truth_path.exists()


def test_reconstruction_is_reproducible_except_manifest_runtime_metadata(
    baseline_config_path: Path, tmp_path: Path
) -> None:
    first_db = tmp_path / "one.sqlite3"
    second_db = tmp_path / "two.sqlite3"
    generate_wms_baseline(baseline_config_path, first_db, generated_at_utc=NOW)
    generate_wms_baseline(baseline_config_path, second_db, generated_at_utc=NOW)
    first = reconstruct_database(first_db, tmp_path / "one-analysis")
    second = reconstruct_database(second_db, tmp_path / "two-analysis")
    for name in first.file_checksums:
        if name != "analysis_manifest.json":
            assert first.file_checksums[name] == second.file_checksums[name]

    def canonical_manifest(path: Path) -> dict:
        value = json.loads((path / "analysis_manifest.json").read_text())
        value.pop("generated_at_utc", None)
        value["source"].pop("path", None)
        value["source"].pop("sha256", None)
        value["outputs"] = {key: {"rows": item["rows"]} for key, item in value["outputs"].items()}
        return value

    assert canonical_manifest(first.output_path) == canonical_manifest(second.output_path)


def test_hand_calculated_audit_replay_applies_transfer_lines_once() -> None:
    snapshots = [
        {
            "snapshot_type": kind,
            "snapshot_batch_id": f"{kind}-BATCH",
            "snapshot_utc": "2026-01-01T00:00:00+00:00",
            "snapshot_line_id": f"{kind}-A",
            "location_id": "LOC-A",
            "item_id": "ITEM-1",
            "qty_on_hand_cases": qty,
        }
        for kind, qty in (("OPENING_SYSTEM", 10), ("CLOSING_SYSTEM", 7))
    ] + [
        {
            "snapshot_type": kind,
            "snapshot_batch_id": f"{kind}-BATCH",
            "snapshot_utc": "2026-01-01T00:00:00+00:00",
            "snapshot_line_id": f"{kind}-B",
            "location_id": "LOC-B",
            "item_id": "ITEM-1",
            "qty_on_hand_cases": qty,
        }
        for kind, qty in (("OPENING_SYSTEM", 2), ("CLOSING_SYSTEM", 5))
    ]
    transactions = [
        {
            "run_id": "RUN-1",
            "transaction_id": "TX-OUT",
            "transaction_group_id": "GROUP-1",
            "command_id": "CMD-1",
            "event_sequence": 1,
            "line_number": 1,
            "transaction_type": "TRANSFER_OUT",
            "event_utc": "2026-01-01T01:00:00+00:00",
            "recorded_utc": "2026-01-01T01:00:00+00:00",
            "item_id": "ITEM-1",
            "location_id": "LOC-A",
            "related_location_id": "LOC-B",
            "operator_id": None,
            "qty_delta_cases": -3,
            "balance_before_cases": 10,
            "balance_after_cases": 7,
            "reason_code": None,
            "source_record_type": "REPLENISHMENT",
            "source_record_id": "REPL-1",
        },
        {
            "run_id": "RUN-1",
            "transaction_id": "TX-IN",
            "transaction_group_id": "GROUP-1",
            "command_id": "CMD-1",
            "event_sequence": 1,
            "line_number": 2,
            "transaction_type": "TRANSFER_IN",
            "event_utc": "2026-01-01T01:00:00+00:00",
            "recorded_utc": "2026-01-01T01:00:00+00:00",
            "item_id": "ITEM-1",
            "location_id": "LOC-B",
            "related_location_id": "LOC-A",
            "operator_id": None,
            "qty_delta_cases": 3,
            "balance_before_cases": 2,
            "balance_after_cases": 5,
            "reason_code": None,
            "source_record_type": "REPLENISHMENT",
            "source_record_id": "REPL-1",
        },
    ]
    source = WmsReconstructionSourceData(
        "RUN-1",
        "3.0.0",
        3,
        {},
        {
            "inventory_snapshot": snapshots,
            "inventory_transaction": transactions,
            "inventory_master": [
                {"location_id": "LOC-A", "item_id": "ITEM-1", "qty_on_hand_cases": 7},
                {"location_id": "LOC-B", "item_id": "ITEM-1", "qty_on_hand_cases": 5},
            ],
            "trip": [],
            "pick_event": [],
            "replenishment_task": [],
            "qa_event": [],
            "inventory_adjustment": [],
            "system_event": [],
            "item_master": [],
            "location_master": [],
        },
    )
    derived = build_wms_reconstruction_tables(source)
    ledger = derived.tables["inventory_event_ledger"]
    assert [row["quantity_delta_cases"] for row in ledger[2:]] == [-3, 3]
    assert [row["transaction_group_id"] for row in ledger[2:]] == ["GROUP-1", "GROUP-1"]
    assert all(
        row["difference_to_live_cases"] == 0 and row["difference_to_snapshot_cases"] == 0
        for row in derived.tables["inventory_reconciliation"]
    )
    assert validate_wms_reconstruction_tables(source, derived).passed


def test_corrupted_derived_reconciliation_fails_validation(baseline) -> None:
    result, _, _ = baseline
    with connect_readonly_database(result.database_path) as connection:
        source = WmsReconstructionSourceRepository(connection).source_tables()
        metadata = WmsFoundationRepository(connection).run_metadata()
    source_data = WmsReconstructionSourceData(
        metadata.run_id, metadata.schema_version, 3, {}, source
    )
    derived = build_wms_reconstruction_tables(source_data)
    rows = list(derived.tables["inventory_reconciliation"])
    rows[0] = {**rows[0], "difference_to_live_cases": 1, "reconciliation_status": "FAIL"}
    corrupted = WmsReconstructionTables({**derived.tables, "inventory_reconciliation": rows})
    assert not validate_wms_reconstruction_tables(source_data, corrupted).passed
