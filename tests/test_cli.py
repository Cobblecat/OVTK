from __future__ import annotations

import sqlite3
import subprocess
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from operational_variance_toolkit.application.phase2 import generate_phase2_database


def test_help_succeeds(run_tool: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    result = run_tool("--help")

    assert result.returncode == 0
    assert "operational-variance-toolkit" in result.stdout
    assert "config-check" in result.stdout
    assert "init-db" in result.stdout
    assert "init-wms" in result.stdout
    assert "generate" in result.stdout
    assert "reconstruct" in result.stdout
    assert "analyze" in result.stdout
    assert "validate" in result.stdout
    assert "describe" in result.stdout
    assert "scenario-check" in result.stdout


def test_version_succeeds_and_contains_installed_version(
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    result = run_tool("--version")

    assert result.returncode == 0
    assert version("operational-variance-toolkit") in result.stdout


def test_init_wms_creates_schema_3_database(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "wms.sqlite3"
    result = run_tool(
        "init-wms",
        "--config",
        str(baseline_config_path),
        "--output",
        str(database_path),
    )

    assert result.returncode == 0
    assert "Schema-3 WMS initialized" in result.stdout
    assert "Schema version: 3.0.0" in result.stdout
    assert "Validation status: PASS" in result.stdout
    assert "item_master: 96" in result.stdout
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3


def test_init_wms_refuses_existing_output(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "existing.sqlite3"
    database_path.write_bytes(b"preserve")

    result = run_tool(
        "init-wms",
        "--config",
        str(baseline_config_path),
        "--output",
        str(database_path),
    )

    assert result.returncode == 4
    assert "already exists" in result.stderr
    assert database_path.read_bytes() == b"preserve"


def test_config_check_succeeds_for_baseline_config(
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    result = run_tool("config-check", "--config", str(baseline_config_path))

    assert result.returncode == 0
    assert "Configuration valid" in result.stdout
    assert "Scenario: baseline 0.1.0" in result.stdout
    assert "Seed: 20260801" in result.stdout
    assert "Facility timezone: America/New_York" in result.stdout
    assert "Configuration SHA-256:" in result.stdout


def test_invalid_configuration_returns_config_error(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    invalid_config = tmp_path / "invalid.toml"
    invalid_config.write_text(
        """
[run]
scenario_name = "baseline"
scenario_version = "0.1.0"
seed = 20260801
start_local = "2026-05-14T15:00:00"
end_local = "2026-05-04T03:00:00"
facility_timezone = "America/New_York"

[facility]
facility_id = "FAC-001"
name = "Synthetic Grocery Distribution Center"

[dimensions]
zone_count = 3
item_count = 96
selector_count = 18
replenisher_count = 7
qa_operator_count = 3
shift_count = 10

[storage]
database_path = "artifacts/data/baseline.sqlite3"
ground_truth_directory = "artifacts/restricted_ground_truth"
export_directory = "artifacts/exports"
""",
        encoding="utf-8",
    )

    result = run_tool("config-check", "--config", str(invalid_config))

    assert result.returncode == 3
    assert "Configuration error:" in result.stderr
    assert "start_local must be before" in result.stderr


def _config_with_database_path(baseline_config_path: Path, database_path: Path) -> Path:
    config_path = database_path.with_suffix(".toml")
    config_text = baseline_config_path.read_text(encoding="utf-8")
    config_text = config_text.replace(
        'database_path = "artifacts/data/baseline.sqlite3"',
        f'database_path = "{database_path.as_posix()}"',
    )
    config_path.write_text(config_text, encoding="utf-8")
    return config_path


def test_init_db_succeeds_for_temp_config_path(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase1.sqlite3"
    config_path = _config_with_database_path(baseline_config_path, database_path)

    result = run_tool("init-db", "--config", str(config_path))

    assert result.returncode == 0
    assert database_path.is_file()
    assert "Phase 1 database initialized" in result.stdout
    assert "Validation status: PASS" in result.stdout


def test_init_db_refuses_existing_output(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase1.sqlite3"
    config_path = _config_with_database_path(baseline_config_path, database_path)
    first_result = run_tool("init-db", "--config", str(config_path))

    result = run_tool("init-db", "--config", str(config_path))

    assert first_result.returncode == 0
    assert result.returncode == 4
    assert "Error:" in result.stderr


def test_validate_missing_database_returns_expected_error(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    database_path = tmp_path / "missing.sqlite3"

    result = run_tool("validate", "--database", str(database_path))

    assert result.returncode == 5
    assert f"Database does not exist: {database_path}" in result.stderr


def test_validate_corrupted_database_returns_validation_exit_code(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase1.sqlite3"
    config_path = _config_with_database_path(baseline_config_path, database_path)
    init_result = run_tool("init-db", "--config", str(config_path))
    assert init_result.returncode == 0

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DELETE FROM handling_unit WHERE handling_unit_id = 'HU-0001'")
        connection.commit()

    result = run_tool("validate", "--database", str(database_path))

    assert result.returncode == 6
    assert "Validation status: FAIL" in result.stdout
    assert "Hard failures:" in result.stdout


def test_describe_success_contains_factual_fields(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase1.sqlite3"
    config_path = _config_with_database_path(baseline_config_path, database_path)
    init_result = run_tool("init-db", "--config", str(config_path))

    result = run_tool("describe", "--database", str(database_path))

    assert init_result.returncode == 0
    assert result.returncode == 0
    assert "Dataset description" in result.stdout
    assert "Run ID:" in result.stdout
    assert "Scenario: baseline 0.1.0" in result.stdout
    assert "Schema version:" in result.stdout
    assert "Table counts:" in result.stdout
    assert "Opening inventory by zone:" in result.stdout
    assert "Validation status: PASS" in result.stdout


def test_generate_schema3_baseline_validate_and_describe_cli(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "schema3.sqlite3"

    generate_result = run_tool(
        "generate",
        "--config",
        str(baseline_config_path),
        "--output",
        str(database_path),
    )
    validate_result = run_tool("validate", "--database", str(database_path))
    describe_result = run_tool("describe", "--database", str(database_path))

    assert generate_result.returncode == 0
    assert "Schema-3 baseline WMS generated" in generate_result.stdout
    assert "replenishment_tasks: 59" in generate_result.stdout
    assert validate_result.returncode == 0
    assert "Validation status: PASS" in validate_result.stdout
    assert describe_result.returncode == 0
    assert "Schema version: 3.0.0" in describe_result.stdout
    assert "Live inventory by zone:" in describe_result.stdout
    assert "CLOSING_SYSTEM" in describe_result.stdout


def test_reconstruct_cli_success_contains_factual_fields(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase2.sqlite3"
    output_path = tmp_path / "analysis"
    generate_phase2_database(baseline_config_path, database_path)

    help_result = run_tool("reconstruct", "--help")
    result = run_tool("reconstruct", "--database", str(database_path), "--output", str(output_path))

    assert help_result.returncode == 0
    assert "--database" in help_result.stdout
    assert "--output" in help_result.stdout
    assert result.returncode == 0
    assert "Inventory reconstruction complete" in result.stdout
    assert "Derived row counts:" in result.stdout
    assert "inventory_event_ledger:" in result.stdout
    assert "pick_context:" in result.stdout
    assert "Reconciliation status: PASS (0 difference(s))" in result.stdout
    assert "Source preserved: True" in result.stdout
    assert (output_path / "analysis_manifest.json").exists()


def test_reconstruct_cli_refuses_existing_output(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase2.sqlite3"
    output_path = tmp_path / "analysis"
    output_path.mkdir()
    (output_path / "existing.txt").write_text("existing", encoding="utf-8")
    generate_phase2_database(baseline_config_path, database_path)

    result = run_tool("reconstruct", "--database", str(database_path), "--output", str(output_path))

    assert result.returncode == 4
    assert "Output directory already exists and is not empty" in result.stderr


def test_reconstruct_cli_returns_validation_exit_for_corrupted_source(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase2.sqlite3"
    generate_phase2_database(baseline_config_path, database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE inventory_snapshot
            SET qty_cases = qty_cases + 1
            WHERE snapshot_id = (
                SELECT snapshot_id
                FROM inventory_snapshot
                WHERE snapshot_type = 'CLOSING_SYSTEM'
                ORDER BY snapshot_id
                LIMIT 1
            )
            """
        )
        connection.commit()

    result = run_tool(
        "reconstruct",
        "--database",
        str(database_path),
        "--output",
        str(tmp_path / "analysis"),
    )

    assert result.returncode == 6
    assert "Source database failed validation" in result.stderr
    assert "closing snapshots must reconcile" in result.stderr


def test_validate_phase2_corruption_returns_exit_code_6(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
    baseline_config_path: Path,
) -> None:
    database_path = tmp_path / "phase2.sqlite3"
    generate_result = run_tool(
        "generate",
        "--config",
        str(baseline_config_path),
        "--output",
        str(database_path),
    )
    assert generate_result.returncode == 0

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DELETE FROM event_sequence_registry WHERE event_sequence = 1")
        connection.commit()

    result = run_tool("validate", "--database", str(database_path))

    assert result.returncode == 6
    assert "Validation status: FAIL" in result.stdout
    assert "Hard failures:" in result.stdout


def test_generate_phase3_and_scenario_check_cli(
    tmp_path: Path,
    run_tool: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    database_path = tmp_path / "investigation.sqlite3"
    ground_truth_path = tmp_path / "ground_truth.json"

    generate_result = run_tool(
        "generate",
        "--config",
        "configs/investigation.toml",
        "--output",
        str(database_path),
        "--ground-truth",
        str(ground_truth_path),
    )
    validate_result = run_tool("validate", "--database", str(database_path))
    scenario_result = run_tool(
        "scenario-check",
        "--database",
        str(database_path),
        "--ground-truth",
        str(ground_truth_path),
    )

    assert generate_result.returncode == 0
    assert "Schema-3 investigation WMS generated" in generate_result.stdout
    assert "Restricted ground-truth path:" in generate_result.stdout
    assert validate_result.returncode == 0
    assert "Validation status: PASS" in validate_result.stdout
    assert scenario_result.returncode == 0
    assert "Scenario validation status: PASS" in scenario_result.stdout
