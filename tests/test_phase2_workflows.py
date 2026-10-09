from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from operational_variance_toolkit.application.phase1 import (
    canonical_phase1_content,
    validate_phase1_database,
)
from operational_variance_toolkit.application.phase2 import generate_phase2_database
from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.storage.repositories import PHASE2_ONLY_TABLES


def test_generate_phase2_database_creates_valid_normal_operations(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "phase2.sqlite3"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")

    result = generate_phase2_database(config_path, database_path)

    assert result.database_path == database_path
    assert result.validation.passed
    assert result.run_metadata.schema_version == "2.0.0"
    assert result.counts["trip"] == result.operation_counts.trips
    assert result.counts["pick_event"] == result.operation_counts.pick_events
    assert result.counts["replenishment_task"] > 0
    assert result.counts["qa_event"] > 0
    assert result.counts["inventory_adjustment"] > 0
    assert result.counts["system_event"] > 0
    assert result.counts["inventory_snapshot"] == 384


def test_generate_phase2_database_refuses_existing_output(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "existing.sqlite3"
    database_path.write_bytes(b"existing")
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")

    with pytest.raises(OutputExistsError):
        generate_phase2_database(config_path, database_path)

    assert database_path.read_bytes() == b"existing"


def test_generate_phase2_database_cleans_up_after_failure(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "cleanup.sqlite3"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")

    def fail_operations(*args, **kwargs) -> None:
        raise DataValidationError("planned phase2 failure")

    monkeypatch.setattr(
        "operational_variance_toolkit.application.phase2.generate_normal_operations",
        fail_operations,
    )

    with pytest.raises(DataValidationError, match="planned phase2 failure"):
        generate_phase2_database(config_path, database_path)

    assert not database_path.exists()


def test_phase2_validation_reports_corrupted_transactions(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "corrupt.sqlite3"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    generate_phase2_database(config_path, database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DELETE FROM event_sequence_registry WHERE event_sequence = 1")
        connection.commit()

    result = validate_phase1_database(database_path)

    assert not result.validation.passed
    assert any(issue.category == "transactions" for issue in result.validation.hard_failures)


def test_phase2_database_has_no_hidden_truth_columns(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    database_path = tmp_path / "phase2.sqlite3"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    generate_phase2_database(config_path, database_path)

    forbidden = ("true_root_cause", "is_injected_anomaly", "physical_arrival", "hidden")
    with sqlite3.connect(database_path) as connection:
        for table_name in PHASE2_ONLY_TABLES:
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")]
            assert not any(token in column.lower() for column in columns for token in forbidden)


def test_phase2_generation_is_reproducible_excluding_execution_timestamp(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    first_database = tmp_path / "first.sqlite3"
    second_database = tmp_path / "second.sqlite3"

    generate_phase2_database(config_path, first_database)
    generate_phase2_database(config_path, second_database)

    assert canonical_phase1_content(first_database) == canonical_phase1_content(second_database)


def test_different_seed_changes_phase2_stochastic_content(
    tmp_path: Path, write_phase1_config: Callable[[Path], Path]
) -> None:
    first_config = write_phase1_config(tmp_path / "first-owned.sqlite3")
    second_config = tmp_path / "second-seed.toml"
    second_config.write_text(
        first_config.read_text(encoding="utf-8").replace("seed = 20260801", "seed = 20260802"),
        encoding="utf-8",
    )
    first_database = tmp_path / "first.sqlite3"
    second_database = tmp_path / "second.sqlite3"

    first = generate_phase2_database(first_config, first_database)
    second = generate_phase2_database(second_config, second_database)

    assert first.validation.passed
    assert second.validation.passed
    assert canonical_phase1_content(first_database) != canonical_phase1_content(second_database)
