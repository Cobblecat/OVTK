"""Focused Slice 4 tests for the schema-3 baseline protocol."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from operational_variance_toolkit.application.wms_generation import (
    canonical_wms_content,
    generate_wms_baseline,
)
from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.simulation.physical import (
    ChronologicalActionRunner,
    PhysicalInventoryState,
    PhysicalPick,
    PhysicalPosition,
    PhysicalQuantityChange,
    PhysicalTransfer,
)
from operational_variance_toolkit.storage.database import connect_database
from operational_variance_toolkit.wms.application.reports import available_reports, run_wms_report

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def baseline(baseline_config_path: Path, tmp_path_factory: pytest.TempPathFactory):
    path = tmp_path_factory.mktemp("schema3-baseline") / "baseline.sqlite3"
    return generate_wms_baseline(baseline_config_path, path, generated_at_utc=NOW)


def _state() -> PhysicalInventoryState:
    return PhysicalInventoryState(
        (
            PhysicalPosition("PICK-001", "ITEM-001", 5, "2026-06-01"),
            PhysicalPosition("RESERVE-001", "ITEM-001", 8, "2026-06-01"),
            PhysicalPosition("EMPTY-001", None, 0, None),
        )
    )


@pytest.mark.parametrize(
    "action",
    [
        lambda: _state().pick("PICK-001", "ITEM-001", -1),
        lambda: _state().transfer("ITEM-001", "PICK-001", "EMPTY-001", 6),
        lambda: _state().change_quantity("PICK-001", "ITEM-001", -6),
    ],
)
def test_physical_state_rejects_negative_quantity(action) -> None:
    with pytest.raises(DataValidationError):
        action()


def test_action_runner_orders_equal_time_by_priority_then_id_and_rejects_backwards() -> None:
    state = _state()
    when = NOW
    actions = (
        PhysicalQuantityChange("z", when, "PICK-001", "ITEM-001", 1, priority=30),
        PhysicalTransfer("a", when, "ITEM-001", "RESERVE-001", "PICK-001", 1, priority=10),
        PhysicalPick("b", when, "PICK-001", "ITEM-001", 1, priority=20),
    )
    runner = ChronologicalActionRunner()
    runner.run(state, actions)
    assert state.quantity("PICK-001", "ITEM-001") == 6
    with pytest.raises(DataValidationError, match="chronologically"):
        runner.apply(
            state,
            PhysicalPick("earlier", when - timedelta(seconds=1), "PICK-001", "ITEM-001", 1),
        )


def test_baseline_is_schema3_valid_reconciled_and_reports_available(baseline) -> None:
    assert baseline.validation.passed
    assert baseline.run_metadata.schema_version == "3.0.0"
    assert baseline.operation_counts.trips > 0
    assert baseline.table_counts["inventory_master"] > 0
    assert baseline.table_counts["inventory_transaction"] > 0
    assert {spec.code for spec in available_reports()} >= {
        "inventory-by-location",
        "inventory-transaction-inquiry",
        "inventory-reconciliation",
    }
    with connect_database(baseline.database_path) as connection:
        closing_batch = connection.execute(
            "SELECT snapshot_batch_id FROM inventory_snapshot "
            "WHERE snapshot_type = 'CLOSING_SYSTEM' LIMIT 1"
        ).fetchone()[0]
    reconciliation = run_wms_report(
        baseline.database_path,
        "inventory-reconciliation",
        {"snapshot_batch": closing_batch},
        generated_at_utc=NOW,
    )
    assert reconciliation.rows
    assert {row[7] for row in reconciliation.rows} == {"MATCH"}


def test_baseline_physical_and_recorded_closing_quantities_match(baseline) -> None:
    with connect_database(baseline.database_path) as connection:
        recorded = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT location_id, qty_on_hand_cases FROM inventory_master ORDER BY location_id"
            )
        }
    assert baseline.operation_counts.closing_snapshots == len(recorded)
    assert baseline.physical_recorded_equal
    assert baseline.database_path.exists()


def test_baseline_closing_has_realistic_occupancy_and_replenishment_supply(baseline) -> None:
    with connect_database(baseline.database_path) as connection:
        reserves = connection.execute(
            """SELECT COUNT(*), SUM(item_id IS NULL)
               FROM inventory_master AS i JOIN location_master AS l
                 USING (run_id, location_id)
               WHERE i.run_id = ? AND l.location_type = 'RESERVE'""",
            (baseline.run_metadata.run_id,),
        ).fetchone()
        picks = connection.execute(
            """SELECT i.qty_on_hand_cases, i.maximum_qty_cases
               FROM inventory_master AS i JOIN location_master AS l
                 USING (run_id, location_id)
               WHERE i.run_id = ? AND l.location_type = 'PICK'
                 AND i.item_id IS NOT NULL""",
            (baseline.run_metadata.run_id,),
        ).fetchall()
        reserve_supply = connection.execute(
            """SELECT COUNT(*) FROM inventory_master AS i JOIN location_master AS l
                 USING (run_id, location_id)
               WHERE i.run_id = ? AND l.location_type = 'RESERVE'
                 AND i.item_id IS NOT NULL AND i.qty_on_hand_cases > 0""",
            (baseline.run_metadata.run_id,),
        ).fetchone()[0]
        completed_replenishments = connection.execute(
            "SELECT COUNT(*) FROM replenishment_task WHERE run_id = ? AND status = 'CONFIRMED'",
            (baseline.run_metadata.run_id,),
        ).fetchone()[0]
    empty_ratio = reserves[1] / reserves[0]
    zero_picks = [row for row in picks if row[0] == 0]
    near_max_picks = [row for row in picks if row[1] and row[0] * 100 >= row[1] * 90]
    assert 0.10 <= empty_ratio <= 0.20
    assert 0 < len(zero_picks) <= len(picks) // 10
    assert 0 < len(near_max_picks) <= len(picks) // 10
    assert reserve_supply >= reserves[0] * 0.75
    assert completed_replenishments > 0


def test_same_seed_has_canonical_reproducibility(
    baseline_config_path: Path, tmp_path: Path
) -> None:
    first = generate_wms_baseline(
        baseline_config_path, tmp_path / "one.sqlite3", generated_at_utc=NOW
    )
    second = generate_wms_baseline(
        baseline_config_path, tmp_path / "two.sqlite3", generated_at_utc=NOW
    )
    assert canonical_wms_content(first.database_path) == canonical_wms_content(second.database_path)


def test_generation_refuses_existing_output(baseline_config_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "existing.sqlite3"
    output.write_bytes(b"keep")
    with pytest.raises(OutputExistsError):
        generate_wms_baseline(baseline_config_path, output, generated_at_utc=NOW)
    assert output.read_bytes() == b"keep"


def test_generation_cleans_partial_output_after_driver_failure(
    baseline_config_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import operational_variance_toolkit.application.wms_generation as workflow

    def fail(*args, **kwargs):
        raise RuntimeError("injected baseline failure")

    monkeypatch.setattr(workflow, "run_baseline_protocol", fail)
    output = tmp_path / "failed.sqlite3"
    with pytest.raises(RuntimeError, match="injected"):
        generate_wms_baseline(baseline_config_path, output, generated_at_utc=NOW)
    assert not output.exists()


def test_wms_and_storage_are_not_imported_by_physical_or_baseline_driver() -> None:
    for module_path in (
        Path("src/operational_variance_toolkit/simulation/physical.py"),
        Path("src/operational_variance_toolkit/simulation/baseline.py"),
    ):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = [
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        names = {alias.name for node in imports for alias in node.names}
        assert not any(
            name.startswith("operational_variance_toolkit.wms.storage") for name in names
        )
        assert not any(
            name.startswith("operational_variance_toolkit.storage.repositories") for name in names
        )


def test_cli_generate_validate_report(baseline_config_path: Path, tmp_path: Path, run_tool) -> None:
    database = tmp_path / "cli.sqlite3"
    generated = run_tool(
        "generate", "--config", str(baseline_config_path), "--output", str(database)
    )
    assert generated.returncode == 0
    validated = run_tool("validate", "--database", str(database))
    assert validated.returncode == 0
    assert "PASS" in validated.stdout
    reported = run_tool("report", "--database", str(database), "--name", "inventory-by-location")
    assert reported.returncode == 0
    assert "inventory-by-location" in reported.stdout
