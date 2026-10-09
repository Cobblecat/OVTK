from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from operational_variance_toolkit.application.phase1 import initialize_phase1_database
from operational_variance_toolkit.application.phase2 import generate_phase2_database
from operational_variance_toolkit.application.phase4 import reconstruct_database
from operational_variance_toolkit.errors import (
    DatabaseError,
    DataValidationError,
    OutputExistsError,
)


def test_reconstruct_database_exports_baseline_outputs_and_preserves_source(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
) -> None:
    database_path = tmp_path / "baseline.sqlite3"
    output_path = tmp_path / "analysis"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    generate_phase2_database(config_path, database_path)

    result = reconstruct_database(database_path, output_path)

    assert result.validation.passed
    assert result.reconciliation_status == "PASS"
    assert result.reconciliation_failure_count == 0
    assert result.source_sha256_before == result.source_sha256_after
    assert result.row_counts["inventory_event_ledger"] > result.row_counts["pick_context"]
    assert result.row_counts["inventory_reconciliation"] == 192
    assert result.row_counts["pick_context"] == 969
    assert result.row_counts["replenishment_context"] == 91
    assert result.row_counts["selector_exposure"] == 18
    assert (output_path / "analysis_manifest.json").exists()
    assert (output_path / "inventory_event_ledger.csv").exists()
    assert _manifest_without_generated_at(output_path)["validation"]["status"] == "PASS"
    assert _hidden_truth_tokens_absent(output_path)


def test_reconstruct_investigation_database_without_ground_truth_input(tmp_path: Path) -> None:
    database_path = tmp_path / "investigation.sqlite3"
    ground_truth_path = tmp_path / "restricted" / "ground_truth.json"
    output_path = tmp_path / "analysis"
    generate_phase2_database("configs/investigation.toml", database_path, ground_truth_path)

    result = reconstruct_database(database_path, output_path)

    assert result.validation.passed
    assert result.reconciliation_status == "PASS"
    assert result.row_counts["pick_context"] > 0
    assert ground_truth_path.exists()
    assert _hidden_truth_tokens_absent(output_path)


def test_reconstruct_refuses_existing_nonempty_output(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
) -> None:
    database_path = tmp_path / "baseline.sqlite3"
    output_path = tmp_path / "analysis"
    output_path.mkdir()
    sentinel = output_path / "sentinel.txt"
    sentinel.write_text("existing", encoding="utf-8")
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    generate_phase2_database(config_path, database_path)

    with pytest.raises(OutputExistsError):
        reconstruct_database(database_path, output_path)

    assert sentinel.read_text(encoding="utf-8") == "existing"


def test_reconstruct_cleans_up_partial_output_after_write_failure(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "baseline.sqlite3"
    output_path = tmp_path / "analysis"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    generate_phase2_database(config_path, database_path)

    def fail_csv(*args: Any, **kwargs: Any) -> None:
        raise OSError("planned write failure")

    monkeypatch.setattr(
        "operational_variance_toolkit.storage.reconstruction_outputs._write_csv",
        fail_csv,
    )

    with pytest.raises(DatabaseError, match="planned write failure"):
        reconstruct_database(database_path, output_path)

    assert not output_path.exists()
    assert not list(tmp_path.glob(".analysis.tmp-*"))


def test_reconstruct_same_source_outputs_are_equivalent(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
) -> None:
    database_path = tmp_path / "baseline.sqlite3"
    first_output = tmp_path / "first-analysis"
    second_output = tmp_path / "second-analysis"
    config_path = write_phase1_config(tmp_path / "config-owned.sqlite3")
    generate_phase2_database(config_path, database_path)

    reconstruct_database(database_path, first_output)
    reconstruct_database(database_path, second_output)

    assert _canonical_output_content(first_output) == _canonical_output_content(second_output)


def test_changed_source_produces_different_reconstruction_content(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
) -> None:
    first_config = write_phase1_config(tmp_path / "first-owned.sqlite3")
    second_config = tmp_path / "second-seed.toml"
    second_config.write_text(
        first_config.read_text(encoding="utf-8").replace("seed = 20260801", "seed = 20260802"),
        encoding="utf-8",
    )
    first_database = tmp_path / "first.sqlite3"
    second_database = tmp_path / "second.sqlite3"
    first_output = tmp_path / "first-analysis"
    second_output = tmp_path / "second-analysis"
    generate_phase2_database(first_config, first_database)
    generate_phase2_database(second_config, second_database)

    reconstruct_database(first_database, first_output)
    reconstruct_database(second_database, second_output)

    assert (first_output / "inventory_event_ledger.csv").read_text(encoding="utf-8") != (
        second_output / "inventory_event_ledger.csv"
    ).read_text(encoding="utf-8")


def test_reconstruct_rejects_unsupported_or_malformed_databases(
    tmp_path: Path,
    write_phase1_config: Callable[[Path], Path],
) -> None:
    phase1_database = tmp_path / "phase1.sqlite3"
    phase1_config = write_phase1_config(phase1_database)
    initialize_phase1_database(phase1_config)

    with pytest.raises(DataValidationError, match="Phase 2/3"):
        reconstruct_database(phase1_database, tmp_path / "phase1-analysis")

    malformed = tmp_path / "malformed.sqlite3"
    malformed.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(DataValidationError, match="Unable to read schema version"):
        reconstruct_database(malformed, tmp_path / "malformed-analysis")


def _canonical_output_content(output_path: Path) -> dict[str, Any]:
    content: dict[str, Any] = {}
    for path in sorted(output_path.iterdir()):
        if path.name == "analysis_manifest.json":
            content[path.name] = _manifest_without_generated_at(output_path)
        else:
            content[path.name] = path.read_text(encoding="utf-8")
    return content


def _manifest_without_generated_at(output_path: Path) -> dict[str, Any]:
    manifest = json.loads((output_path / "analysis_manifest.json").read_text(encoding="utf-8"))
    manifest.pop("generated_at_utc", None)
    return manifest


def _hidden_truth_tokens_absent(output_path: Path) -> bool:
    forbidden = (
        "true_root_cause",
        "is_injected_anomaly",
        "physical_arrival",
        "target_selector",
        "injected_pattern",
    )
    for path in output_path.iterdir():
        lowered = path.read_text(encoding="utf-8").lower()
        if any(token in lowered for token in forbidden):
            return False
    return True
