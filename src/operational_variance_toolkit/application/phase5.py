"""Phase 5 statistical investigation application workflow."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from operational_variance_toolkit.analysis.statistical_config import (
    AnalysisConfig,
    load_analysis_config,
)
from operational_variance_toolkit.analysis.statistics import (
    STATISTICS_VERSION,
    build_statistical_analysis,
)
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.storage.statistical_outputs import (
    require_available_statistics_output,
    write_statistical_outputs,
)
from operational_variance_toolkit.storage.statistical_sources import (
    RECONSTRUCTION_FILES,
    StatisticalSource,
    load_statistical_source,
    sha256_file,
)


@dataclass(frozen=True, slots=True)
class AnalyzeDatabaseResult:
    database_path: Path
    reconstruction_path: Path
    output_path: Path
    run_id: str
    source_sha256_before: str
    source_sha256_after: str
    configuration_sha256: str
    row_counts: dict[str, int]
    file_checksums: dict[str, str]
    model_kind: str
    covariance: str
    crude_risk_difference: float
    adjusted_risk_difference: float
    proportional_attenuation: float
    material_attenuation: bool
    hypotheses_complete: bool
    ordinary_analysis_ground_truth_loaded: bool


def analyze_database(
    database_path: str | Path,
    reconstruction_path: str | Path,
    config_path: str | Path,
    output_path: str | Path,
    *,
    generated_at_utc: datetime | None = None,
) -> AnalyzeDatabaseResult:
    """Validate sources, execute frozen statistics, and atomically write outputs."""

    final_output = require_available_statistics_output(output_path)
    config = load_analysis_config(config_path)
    source = load_statistical_source(database_path, reconstruction_path)
    comparison = _load_comparison(config)
    before_hashes = _source_hashes(source, comparison)
    created_output: Path | None = None
    try:
        analysis = build_statistical_analysis(source, config, comparison)
        adjusted = analysis.tables["selector_adjusted.csv"][0]
        manifest = _build_manifest(
            source,
            comparison,
            config,
            analysis.row_counts,
            generated_at_utc or datetime.now(tz=UTC),
        )
        write_result = write_statistical_outputs(final_output, analysis, config, manifest)
        created_output = write_result.output_path
        after_hashes = _source_hashes(source, comparison)
        if after_hashes != before_hashes:
            shutil.rmtree(created_output, ignore_errors=True)
            raise DataValidationError("A source changed during read-only statistical analysis")
        return AnalyzeDatabaseResult(
            database_path=source.database_path,
            reconstruction_path=source.reconstruction_path,
            output_path=write_result.output_path,
            run_id=str(source.metadata["run_id"]),
            source_sha256_before=source.source_sha256,
            source_sha256_after=after_hashes["primary_database"],
            configuration_sha256=config.sha256(),
            row_counts=analysis.row_counts,
            file_checksums=write_result.file_checksums,
            model_kind=str(adjusted["model_kind"]),
            covariance=str(adjusted["covariance"]),
            crude_risk_difference=float(adjusted["crude_risk_difference"]),
            adjusted_risk_difference=float(adjusted["adjusted_risk_difference"]),
            proportional_attenuation=float(adjusted["proportional_attenuation"]),
            material_attenuation=bool(adjusted["material_attenuation"]),
            hypotheses_complete=bool(analysis.model_diagnostics["all_six_hypotheses_present"]),
            ordinary_analysis_ground_truth_loaded=bool(
                analysis.model_diagnostics["ordinary_analysis_ground_truth_loaded"]
            ),
        )
    except Exception:
        if created_output is not None and created_output.exists():
            shutil.rmtree(created_output, ignore_errors=True)
        raise


def _load_comparison(config: AnalysisConfig) -> StatisticalSource | None:
    if config.comparison is None:
        return None
    return load_statistical_source(
        config.comparison.database,
        config.comparison.reconstruction,
    )


def _source_hashes(
    source: StatisticalSource, comparison: StatisticalSource | None
) -> dict[str, str]:
    hashes = {
        "primary_database": sha256_file(source.database_path),
        "primary_reconstruction_manifest": sha256_file(
            source.reconstruction_path / "analysis_manifest.json"
        ),
    }
    for file_name in RECONSTRUCTION_FILES:
        hashes[f"primary_reconstruction:{file_name}"] = sha256_file(
            source.reconstruction_path / file_name
        )
    if comparison is not None:
        hashes.update(
            {
                "comparison_database": sha256_file(comparison.database_path),
                "comparison_reconstruction_manifest": sha256_file(
                    comparison.reconstruction_path / "analysis_manifest.json"
                ),
            }
        )
        for file_name in RECONSTRUCTION_FILES:
            hashes[f"comparison_reconstruction:{file_name}"] = sha256_file(
                comparison.reconstruction_path / file_name
            )
    return hashes


def _build_manifest(
    source: StatisticalSource,
    comparison: StatisticalSource | None,
    config: AnalysisConfig,
    row_counts: dict[str, int],
    generated_at_utc: datetime,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifact_type": "frozen_statistical_analysis",
        "statistics_version": STATISTICS_VERSION,
        "generated_at_utc": generated_at_utc.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "analysis_contract_version": config.contract_version,
        "analysis_configuration_sha256": config.sha256(),
        "source": {
            "path": str(source.database_path),
            "sha256": source.source_sha256,
            "reconstruction_path": str(source.reconstruction_path),
            "reconstruction_manifest_sha256": source.reconstruction_manifest_sha256,
            **source.metadata,
        },
        "row_counts": row_counts,
        "validation": {
            "status": "PASS",
            "source_identity": "PASS",
            "reconstruction_identity": "PASS",
            "analytical_grain_uniqueness": "PASS",
            "reconciliation": "PASS",
            "ordinary_analysis_ground_truth_loaded": False,
            "findings_frozen": True,
        },
    }
    if comparison is not None:
        payload["comparison_source"] = {
            "path": str(comparison.database_path),
            "sha256": comparison.source_sha256,
            "reconstruction_path": str(comparison.reconstruction_path),
            "reconstruction_manifest_sha256": comparison.reconstruction_manifest_sha256,
            **comparison.metadata,
        }
    return payload
