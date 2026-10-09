from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from operational_variance_toolkit.analysis.statistical_config import load_analysis_config
from operational_variance_toolkit.analysis.statistics import OUTPUT_COLUMNS, StatisticalAnalysis
from operational_variance_toolkit.application.phase4 import reconstruct_database
from operational_variance_toolkit.application.phase5 import analyze_database
from operational_variance_toolkit.application.wms_generation import generate_wms_baseline
from operational_variance_toolkit.application.wms_investigation import generate_wms_investigation
from operational_variance_toolkit.cli import main
from operational_variance_toolkit.errors import (
    DatabaseError,
    DataValidationError,
    OutputExistsError,
)
from operational_variance_toolkit.storage import statistical_outputs

NOW = datetime(2026, 8, 2, 15, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def phase5_sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase5")
    baseline_database = root / "baseline.sqlite3"
    investigation_database = root / "investigation.sqlite3"
    truth_path = root / "restricted_ground_truth.json"
    generate_wms_baseline("configs/baseline.toml", baseline_database, generated_at_utc=NOW)
    generate_wms_investigation(
        "configs/investigation.toml",
        investigation_database,
        truth_path,
        generated_at_utc=NOW,
    )
    baseline_reconstruction = reconstruct_database(
        baseline_database, root / "baseline-reconstruction"
    ).output_path
    investigation_reconstruction = reconstruct_database(
        investigation_database, root / "investigation-reconstruction"
    ).output_path
    config_text = Path("configs/phase5_analysis.toml").read_text(encoding="utf-8")
    config_text = config_text.replace(
        "artifacts/data/schema3_baseline_accepted.sqlite3",
        baseline_database.as_posix(),
    ).replace(
        "artifacts/analysis/schema3_baseline_accepted",
        baseline_reconstruction.as_posix(),
    )
    config_path = root / "analysis.toml"
    config_path.write_text(config_text, encoding="utf-8")
    before = {
        "baseline": _sha256(baseline_database),
        "investigation": _sha256(investigation_database),
    }
    return {
        "root": root,
        "baseline_database": baseline_database,
        "investigation_database": investigation_database,
        "baseline_reconstruction": baseline_reconstruction,
        "investigation_reconstruction": investigation_reconstruction,
        "config": config_path,
        "truth": truth_path,
        "before": before,
    }


@pytest.fixture(scope="module")
def phase5_result(phase5_sources):
    return analyze_database(
        phase5_sources["investigation_database"],
        phase5_sources["investigation_reconstruction"],
        phase5_sources["config"],
        phase5_sources["root"] / "statistics-one",
        generated_at_utc=NOW,
    )


def test_phase5_workflow_writes_complete_frozen_outputs_and_preserves_sources(
    phase5_sources, phase5_result
) -> None:
    assert sorted(path.name for path in phase5_result.output_path.iterdir()) == sorted(
        [
            "analysis_config.json",
            "analysis_manifest.json",
            "model_diagnostics.json",
            *OUTPUT_COLUMNS,
        ]
    )
    assert phase5_result.model_kind == "binomial_logit"
    assert phase5_result.covariance == "cluster_trip"
    assert phase5_result.material_attenuation
    assert phase5_result.hypotheses_complete
    assert not phase5_result.ordinary_analysis_ground_truth_loaded
    assert phase5_result.adjusted_risk_difference < phase5_result.crude_risk_difference
    assert (
        _sha256(phase5_sources["investigation_database"])
        == phase5_sources["before"]["investigation"]
    )
    assert _sha256(phase5_sources["baseline_database"]) == phase5_sources["before"]["baseline"]

    manifest = json.loads((phase5_result.output_path / "analysis_manifest.json").read_text())
    diagnostics = json.loads((phase5_result.output_path / "model_diagnostics.json").read_text())
    assert manifest["validation"]["findings_frozen"] is True
    assert manifest["validation"]["ordinary_analysis_ground_truth_loaded"] is False
    assert diagnostics["events"] == 33
    assert diagnostics["clusters"] == 140
    assert diagnostics["fallback_used"] is False


def test_phase5_outputs_are_reproducible_and_changed_valid_source_differs(
    phase5_sources, phase5_result
) -> None:
    repeat = analyze_database(
        phase5_sources["investigation_database"],
        phase5_sources["investigation_reconstruction"],
        phase5_sources["config"],
        phase5_sources["root"] / "statistics-two",
        generated_at_utc=NOW,
    )
    assert phase5_result.file_checksums == repeat.file_checksums

    baseline = analyze_database(
        phase5_sources["baseline_database"],
        phase5_sources["baseline_reconstruction"],
        phase5_sources["config"],
        phase5_sources["root"] / "baseline-statistics",
        generated_at_utc=NOW,
    )
    assert (
        baseline.file_checksums["descriptive_metrics.csv"]
        != phase5_result.file_checksums["descriptive_metrics.csv"]
    )
    assert baseline.source_sha256_before == baseline.source_sha256_after


def test_phase5_hypotheses_sensitivities_and_crude_exposure_are_complete(
    phase5_result,
) -> None:
    hypothesis_rows = list(
        __import__("csv").DictReader(
            (phase5_result.output_path / "hypothesis_evidence.csv").open(encoding="utf-8")
        )
    )
    sensitivity_rows = list(
        __import__("csv").DictReader(
            (phase5_result.output_path / "sensitivity_results.csv").open(encoding="utf-8")
        )
    )
    selector_rows = list(
        __import__("csv").DictReader(
            (phase5_result.output_path / "selector_crude.csv").open(encoding="utf-8")
        )
    )
    assert {row["hypothesis_id"] for row in hypothesis_rows} == {
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
    }
    assert {
        "case_outcome",
        "alternate_time_control",
        "alternate_covariance",
        "target_outside_condition",
        "exposed_peers",
        "baseline_comparison",
        "remove_high_leverage_trip",
        "remove_high_leverage_item",
    } <= {row["sensitivity_id"] for row in sensitivity_rows}
    target = next(row for row in selector_rows if row["is_target_contrast"] == "1")
    assert target["selector_id"] == "OP-0002"
    assert target["crude_rank"] == "1"
    assert int(target["operational_condition_picks"]) > 0


def test_phase5_refuses_existing_output_and_restricted_paths(phase5_sources, phase5_result) -> None:
    with pytest.raises(OutputExistsError, match="already exists"):
        analyze_database(
            phase5_sources["investigation_database"],
            phase5_sources["investigation_reconstruction"],
            phase5_sources["config"],
            phase5_result.output_path,
        )
    with pytest.raises(DataValidationError, match="restricted-truth"):
        analyze_database(
            phase5_sources["truth"],
            phase5_sources["investigation_reconstruction"],
            phase5_sources["config"],
            phase5_sources["root"] / "forbidden-output",
        )


def test_phase5_rejects_malformed_database_without_output(tmp_path: Path, phase5_sources) -> None:
    malformed = tmp_path / "malformed.sqlite3"
    malformed.write_text("not sqlite", encoding="utf-8")
    output = tmp_path / "statistics"
    with pytest.raises(DataValidationError, match="checksum does not match"):
        analyze_database(
            malformed,
            phase5_sources["investigation_reconstruction"],
            phase5_sources["config"],
            output,
        )
    assert not output.exists()


def test_statistical_writer_cleans_partial_output(monkeypatch, tmp_path: Path) -> None:
    config = load_analysis_config("configs/phase5_analysis.toml")
    analysis = StatisticalAnalysis(
        tables={file_name: [] for file_name in OUTPUT_COLUMNS},
        model_diagnostics={},
    )

    def fail_write(*args, **kwargs):
        raise OSError("injected writer failure")

    monkeypatch.setattr(statistical_outputs, "_write_csv", fail_write)
    output = tmp_path / "failed-statistics"
    with pytest.raises(DatabaseError, match="injected writer failure"):
        statistical_outputs.write_statistical_outputs(output, analysis, config, {})
    assert not output.exists()
    assert not list(tmp_path.glob(".failed-statistics.tmp-*"))


def test_analyze_cli_prints_factual_summary(monkeypatch, capsys, phase5_result) -> None:
    monkeypatch.setattr(
        "operational_variance_toolkit.cli.analyze_database",
        lambda *args, **kwargs: phase5_result,
    )
    exit_code = main(
        [
            "analyze",
            "--database",
            "source.sqlite3",
            "--reconstruction",
            "reconstruction",
            "--config",
            "analysis.toml",
            "--output",
            "statistics",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Phase 5 statistical analysis complete" in output
    assert "Material attenuation: True" in output
    assert "Ordinary analysis loaded ground truth: False" in output
