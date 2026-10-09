from __future__ import annotations

from pathlib import Path

import pytest

from operational_variance_toolkit.application.phase1 import (
    canonical_phase1_content,
    initialize_phase1_database,
)


def test_phase1_initialization_is_reproducible_excluding_execution_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "baseline.toml"
    config_path.write_text(
        """
[run]
scenario_name = "baseline"
scenario_version = "0.1.0"
seed = 20260801
start_local = "2026-05-04T03:00:00"
end_local = "2026-05-14T15:00:00"
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
    first_root = tmp_path / "first-root"
    second_root = tmp_path / "second-root"
    first_root.mkdir()
    second_root.mkdir()

    monkeypatch.chdir(first_root)
    initialize_phase1_database(config_path)
    first_database_path = first_root / "artifacts/data/baseline.sqlite3"

    monkeypatch.chdir(second_root)
    initialize_phase1_database(config_path)
    second_database_path = second_root / "artifacts/data/baseline.sqlite3"

    assert canonical_phase1_content(first_database_path) == canonical_phase1_content(
        second_database_path
    )
