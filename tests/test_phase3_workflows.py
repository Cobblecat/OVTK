from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from operational_variance_toolkit.application.phase1 import (
    canonical_phase1_content,
    validate_phase1_database,
)
from operational_variance_toolkit.application.phase2 import generate_phase2_database
from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import ConfigurationError, OutputExistsError
from operational_variance_toolkit.storage.ground_truth import canonical_ground_truth
from operational_variance_toolkit.validation.scenario import validate_scenario_artifacts


def test_investigation_config_enables_all_failure_overlays() -> None:
    config = load_project_config("configs/investigation.toml")

    assert config.run.scenario_name == "investigation"
    assert config.failures.any_enabled
    assert config.failures.replenishment_gap.enabled
    assert config.failures.qa_masking.enabled
    assert config.failures.selector_false_lead.enabled


def test_invalid_failure_configuration_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_text = Path("configs/investigation.toml").read_text(encoding="utf-8")
    config_path.write_text(
        config_text.replace("enabled = true", 'enabled = "yes"', 1),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="enabled"):
        load_project_config(config_path)


def test_phase3_generation_writes_separate_ground_truth_and_passes_scenario_check(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investigation.sqlite3"
    ground_truth_path = tmp_path / "restricted" / "ground_truth.json"

    result = generate_phase2_database(
        "configs/investigation.toml",
        database_path,
        ground_truth_path,
    )
    analyst_validation = validate_phase1_database(database_path)
    scenario_validation = validate_scenario_artifacts(database_path, ground_truth_path)

    assert result.validation.passed
    assert result.ground_truth_path == ground_truth_path
    assert analyst_validation.validation.passed
    assert scenario_validation.passed
    assert result.counts["pick_event"] > 0
    assert result.counts["qa_event"] > 0
    assert result.counts["inventory_adjustment"] > 0


def test_phase3_generation_requires_ground_truth_when_failures_are_enabled(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="ground-truth"):
        generate_phase2_database("configs/investigation.toml", tmp_path / "investigation.sqlite3")


def test_baseline_generation_rejects_ground_truth_path_when_failures_are_disabled(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigurationError, match="only supported"):
        generate_phase2_database(
            "configs/baseline.toml",
            tmp_path / "baseline.sqlite3",
            tmp_path / "ground_truth.json",
        )


def test_phase3_generation_refuses_existing_ground_truth(tmp_path: Path) -> None:
    database_path = tmp_path / "investigation.sqlite3"
    ground_truth_path = tmp_path / "ground_truth.json"
    ground_truth_path.write_text("existing", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        generate_phase2_database(
            "configs/investigation.toml",
            database_path,
            ground_truth_path,
        )

    assert not database_path.exists()
    assert ground_truth_path.read_text(encoding="utf-8") == "existing"


def test_phase3_generation_is_reproducible_for_analyst_and_ground_truth(
    tmp_path: Path,
) -> None:
    first_database = tmp_path / "first.sqlite3"
    first_ground_truth = tmp_path / "first.json"
    second_database = tmp_path / "second.sqlite3"
    second_ground_truth = tmp_path / "second.json"

    generate_phase2_database("configs/investigation.toml", first_database, first_ground_truth)
    generate_phase2_database("configs/investigation.toml", second_database, second_ground_truth)

    assert canonical_phase1_content(first_database) == canonical_phase1_content(second_database)
    assert canonical_ground_truth(first_ground_truth) == canonical_ground_truth(second_ground_truth)


def test_phase3_changed_seed_varies_but_stays_valid(tmp_path: Path) -> None:
    changed_config = tmp_path / "changed.toml"
    changed_config.write_text(
        Path("configs/investigation.toml")
        .read_text(encoding="utf-8")
        .replace("seed = 20260801", "seed = 20260802"),
        encoding="utf-8",
    )
    first_database = tmp_path / "first.sqlite3"
    first_ground_truth = tmp_path / "first.json"
    changed_database = tmp_path / "changed.sqlite3"
    changed_ground_truth = tmp_path / "changed.json"

    generate_phase2_database("configs/investigation.toml", first_database, first_ground_truth)
    generate_phase2_database(changed_config, changed_database, changed_ground_truth)

    assert canonical_phase1_content(first_database) != canonical_phase1_content(changed_database)
    assert canonical_ground_truth(first_ground_truth) != canonical_ground_truth(
        changed_ground_truth
    )
    assert validate_scenario_artifacts(changed_database, changed_ground_truth).passed


def test_phase3_analyst_database_contains_no_ground_truth_leakage(tmp_path: Path) -> None:
    database_path = tmp_path / "investigation.sqlite3"
    ground_truth_path = tmp_path / "ground_truth.json"
    generate_phase2_database("configs/investigation.toml", database_path, ground_truth_path)
    forbidden = (
        "is_anomaly",
        "is_injected",
        "target_selector",
        "true_root_cause",
        "failure_pattern",
        "hidden_arrival_time",
        "scenario_label",
        "ground_truth",
    )

    with sqlite3.connect(database_path) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        assert not any(token in table.lower() for table in table_names for token in forbidden)
        for table_name in table_names:
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")]
            assert not any(token in column.lower() for column in columns for token in forbidden)
