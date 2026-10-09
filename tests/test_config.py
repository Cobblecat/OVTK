from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import ConfigurationError

VALID_CONFIG = """
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
"""


def write_config(tmp_path: Path, text: str) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def test_valid_toml_maps_to_immutable_project_config(baseline_config_path: Path) -> None:
    config = load_project_config(baseline_config_path)

    assert config.run.scenario_name == "baseline"
    assert config.run.scenario_version == "0.1.0"
    assert config.run.seed == 20260801
    assert config.run.start_utc == datetime(2026, 5, 4, 7, 0, tzinfo=UTC)
    assert config.run.end_utc == datetime(2026, 5, 14, 19, 0, tzinfo=UTC)
    assert config.facility.facility_id == "FAC-001"
    assert config.dimensions.item_count == 96
    assert config.storage.database_path.as_posix() == "artifacts/data/baseline.sqlite3"
    assert config.operations.trip_count == 120
    assert config.operations.short_probability == 0.005

    with pytest.raises(FrozenInstanceError):
        config.run.seed = 1


def test_unknown_top_level_section_fails(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, f"{VALID_CONFIG}\n[unexpected]\nvalue = true\n")

    with pytest.raises(ConfigurationError, match="Unknown top-level"):
        load_project_config(config_path)


def test_unknown_key_within_known_section_fails(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        VALID_CONFIG.replace(
            'scenario_name = "baseline"',
            'scenario_name = "baseline"\nunexpected = "nope"',
        ),
    )

    with pytest.raises(ConfigurationError, match="Unknown key"):
        load_project_config(config_path)


def test_missing_required_key_fails(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, VALID_CONFIG.replace("seed = 20260801\n", ""))

    with pytest.raises(ConfigurationError, match="Missing required key"):
        load_project_config(config_path)


def test_invalid_timezone_fails(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        VALID_CONFIG.replace(
            'facility_timezone = "America/New_York"',
            'facility_timezone = "Mars/Depot"',
        ),
    )

    with pytest.raises(ConfigurationError, match="facility_timezone"):
        load_project_config(config_path)


def test_end_before_start_fails(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        VALID_CONFIG.replace(
            'end_local = "2026-05-14T15:00:00"',
            'end_local = "2026-05-01T15:00:00"',
        ),
    )

    with pytest.raises(ConfigurationError, match="start_local must be before"):
        load_project_config(config_path)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("zone_count = 3", "zone_count = 0"),
        ("item_count = 96", "item_count = -1"),
        ("selector_count = 18", "selector_count = 0"),
        ("replenisher_count = 7", "replenisher_count = 0"),
        ("qa_operator_count = 3", "qa_operator_count = 0"),
        ("shift_count = 10", "shift_count = 0"),
    ],
)
def test_zero_or_negative_required_dimensions_fail(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    config_path = write_config(tmp_path, VALID_CONFIG.replace(field, replacement))

    with pytest.raises(ConfigurationError, match="must be positive"):
        load_project_config(config_path)


def test_invalid_operations_range_fails(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        f"{VALID_CONFIG}\n[operations]\npick_lines_per_trip_min = 9\npick_lines_per_trip_max = 8\n",
    )

    with pytest.raises(ConfigurationError, match="pick_lines_per_trip_min"):
        load_project_config(config_path)


def test_invalid_operations_probability_fails(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        f"{VALID_CONFIG}\n[operations]\nshort_probability = 1.5\n",
    )

    with pytest.raises(ConfigurationError, match="short_probability"):
        load_project_config(config_path)


def test_equivalent_semantic_configuration_produces_same_hash(tmp_path: Path) -> None:
    reordered_config = """
[storage]
export_directory = "artifacts/exports"
ground_truth_directory = "artifacts/restricted_ground_truth"
database_path = "artifacts/data/baseline.sqlite3"

[dimensions]
shift_count = 10
qa_operator_count = 3
replenisher_count = 7
selector_count = 18
item_count = 96
zone_count = 3

[facility]
name = "Synthetic Grocery Distribution Center"
facility_id = "FAC-001"

[run]
facility_timezone = "America/New_York"
end_local = "2026-05-14T15:00:00"
start_local = "2026-05-04T03:00:00"
seed = 20260801
scenario_version = "0.1.0"
scenario_name = "baseline"
"""
    first = load_project_config(write_config(tmp_path, VALID_CONFIG))
    second = load_project_config(write_config(tmp_path, reordered_config))

    assert first.configuration_hash == second.configuration_hash


def test_meaningful_value_change_produces_different_hash(tmp_path: Path) -> None:
    first = load_project_config(write_config(tmp_path, VALID_CONFIG))
    changed = load_project_config(
        write_config(tmp_path, VALID_CONFIG.replace("item_count = 96", "item_count = 95"))
    )

    assert first.configuration_hash != changed.configuration_hash


def test_path_parsing_does_not_create_directories(tmp_path: Path) -> None:
    database_path = tmp_path / "missing" / "baseline.sqlite3"
    export_directory = tmp_path / "exports"
    ground_truth_directory = tmp_path / "ground_truth"
    config_text = VALID_CONFIG.replace(
        'database_path = "artifacts/data/baseline.sqlite3"',
        f'database_path = "{database_path.as_posix()}"',
    )
    config_text = config_text.replace(
        'ground_truth_directory = "artifacts/restricted_ground_truth"',
        f'ground_truth_directory = "{ground_truth_directory.as_posix()}"',
    )
    config_text = config_text.replace(
        'export_directory = "artifacts/exports"',
        f'export_directory = "{export_directory.as_posix()}"',
    )

    config = load_project_config(write_config(tmp_path, config_text))

    assert config.storage.database_path == database_path
    assert not database_path.exists()
    assert not export_directory.exists()
    assert not ground_truth_directory.exists()
