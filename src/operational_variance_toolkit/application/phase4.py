"""Phase 4 reconstruction application workflow."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from operational_variance_toolkit.analysis.reconstruction import (
    RECONSTRUCTION_VERSION,
    ReconstructionSourceData,
    build_reconstruction_tables,
    validate_reconstruction_tables,
)
from operational_variance_toolkit.analysis.wms_reconstruction import (
    WMS_OUTPUT_FILE_NAMES,
    WMS_OUTPUT_TABLE_COLUMNS,
    WMS_RECONSTRUCTION_VERSION,
    WmsReconstructionSourceData,
    build_wms_reconstruction_tables,
    validate_wms_reconstruction_tables,
)
from operational_variance_toolkit.errors import DatabaseError, DataValidationError, ToolkitError
from operational_variance_toolkit.storage.database import connect_readonly_database
from operational_variance_toolkit.storage.reconstruction import ReconstructionSourceRepository
from operational_variance_toolkit.storage.reconstruction_outputs import (
    write_reconstruction_outputs,
)
from operational_variance_toolkit.storage.repositories import Phase1DatasetRepository, RunMetadata
from operational_variance_toolkit.storage.schema import PHASE2_SCHEMA_VERSION
from operational_variance_toolkit.storage.wms_reconstruction import (
    WmsReconstructionSourceRepository,
)
from operational_variance_toolkit.validation.dataset import validate_dataset
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.wms.storage.repositories import (
    WmsFoundationRepository,
    WmsRunMetadata,
)


@dataclass(frozen=True, slots=True)
class ReconstructDatabaseResult:
    database_path: Path
    output_path: Path
    run_metadata: RunMetadata | WmsRunMetadata
    row_counts: dict[str, int]
    reconciliation_status: str
    reconciliation_failure_count: int
    source_sha256_before: str
    source_sha256_after: str
    validation: ValidationResult
    file_checksums: dict[str, str]


def reconstruct_database(
    database_path: str | Path,
    output_path: str | Path,
) -> ReconstructDatabaseResult:
    """Reconstruct analyst-facing system inventory into portable derived outputs."""

    resolved_database = _require_existing_database(database_path)
    source_sha256_before = _sha256_file(resolved_database)
    created_output: Path | None = None
    try:
        with closing(connect_readonly_database(resolved_database)) as connection:
            source_validation = validate_dataset(connection)
            if not source_validation.passed:
                details = _validation_details(source_validation)
                raise DataValidationError(f"Source database failed validation: {details}")

            legacy_repository = Phase1DatasetRepository(connection)
            sqlite_user_version = legacy_repository.user_version()
            if sqlite_user_version == 2:
                run_metadata = _single_run_metadata(legacy_repository)
                if run_metadata.schema_version != PHASE2_SCHEMA_VERSION:
                    raise DataValidationError(f"Schema-2 metadata is not {PHASE2_SCHEMA_VERSION}")
                source: ReconstructionSourceData | WmsReconstructionSourceData = (
                    ReconstructionSourceData(
                        run_id=run_metadata.run_id,
                        source_schema_version=run_metadata.schema_version,
                        sqlite_user_version=sqlite_user_version,
                        table_counts=legacy_repository.table_counts(),
                        tables=ReconstructionSourceRepository(connection).source_tables(),
                    )
                )
                reconstruction_kind = "legacy"
            elif sqlite_user_version == 3:
                wms_repository = WmsFoundationRepository(connection)
                run_metadata = wms_repository.run_metadata()
                source = WmsReconstructionSourceData(
                    run_id=run_metadata.run_id,
                    source_schema_version=run_metadata.schema_version,
                    sqlite_user_version=sqlite_user_version,
                    table_counts=wms_repository.table_counts(),
                    tables=WmsReconstructionSourceRepository(connection).source_tables(),
                )
                reconstruction_kind = "wms"
            else:
                raise DataValidationError(
                    "Reconstruction requires a Phase 2/3 schema-2 database or a "
                    f"schema-3 WMS; found user_version={sqlite_user_version}"
                )

        if reconstruction_kind == "wms":
            assert isinstance(source, WmsReconstructionSourceData)
            derived = build_wms_reconstruction_tables(source)
            reconstruction_validation = validate_wms_reconstruction_tables(source, derived)
            reconstruction_version = WMS_RECONSTRUCTION_VERSION
            table_columns = WMS_OUTPUT_TABLE_COLUMNS
            file_names = WMS_OUTPUT_FILE_NAMES
        else:
            assert isinstance(source, ReconstructionSourceData)
            derived = build_reconstruction_tables(source)
            reconstruction_validation = validate_reconstruction_tables(source, derived)
            reconstruction_version = RECONSTRUCTION_VERSION
            table_columns = None
            file_names = None
        if not reconstruction_validation.passed:
            details = _validation_details(reconstruction_validation)
            raise DataValidationError(f"Reconstruction output failed validation: {details}")

        source_sha256_after_read = _sha256_file(resolved_database)
        if source_sha256_after_read != source_sha256_before:
            raise DataValidationError("Source database changed during read-only reconstruction")

        reconciliation_failures = sum(
            1
            for row in derived.tables["inventory_reconciliation"]
            if row["reconciliation_status"] != "PASS"
        )
        manifest = _build_manifest(
            database_path=resolved_database,
            source_sha256=source_sha256_before,
            run_metadata=run_metadata,
            row_counts=derived.row_counts,
            validation=reconstruction_validation,
            reconstruction_version=reconstruction_version,
        )
        if table_columns is None or file_names is None:
            write_result = write_reconstruction_outputs(output_path, derived, manifest)
        else:
            write_result = write_reconstruction_outputs(
                output_path,
                derived,
                manifest,
                table_columns=table_columns,
                file_names=file_names,
            )
        created_output = write_result.output_path

        source_sha256_after = _sha256_file(resolved_database)
        if source_sha256_after != source_sha256_before:
            _remove_output_directory(created_output)
            raise DataValidationError("Source database changed during reconstruction output write")

        return ReconstructDatabaseResult(
            database_path=resolved_database,
            output_path=write_result.output_path,
            run_metadata=run_metadata,
            row_counts=derived.row_counts,
            reconciliation_status="PASS" if reconciliation_failures == 0 else "FAIL",
            reconciliation_failure_count=reconciliation_failures,
            source_sha256_before=source_sha256_before,
            source_sha256_after=source_sha256_after,
            validation=reconstruction_validation,
            file_checksums=write_result.file_checksums,
        )
    except Exception as exc:
        if created_output is not None:
            _remove_output_directory(created_output)
        if isinstance(exc, ToolkitError):
            raise
        if isinstance(exc, sqlite3.DatabaseError):
            raise DatabaseError(
                f"Failed while reconstructing database at {resolved_database}: {exc}"
            ) from exc
        raise


def _build_manifest(
    *,
    database_path: Path,
    source_sha256: str,
    run_metadata: RunMetadata | WmsRunMetadata,
    row_counts: dict[str, int],
    validation: ValidationResult,
    reconstruction_version: str,
) -> dict[str, object]:
    source_metadata: dict[str, object] = {
        "path": str(database_path),
        "sha256": source_sha256,
        "schema_version": run_metadata.schema_version,
        "configuration_sha256": run_metadata.config_hash,
        "generator_version": run_metadata.generator_version,
        "run_id": run_metadata.run_id,
        "seed": run_metadata.seed,
        "simulation_start_utc": run_metadata.simulation_start_utc,
        "simulation_end_utc": run_metadata.simulation_end_utc,
        "facility_timezone": run_metadata.facility_timezone,
    }
    if isinstance(run_metadata, RunMetadata):
        source_metadata.update(
            {
                "scenario_name": run_metadata.scenario_name,
                "scenario_version": run_metadata.scenario_version,
            }
        )
    return {
        "artifact_type": "analysis_reconstruction",
        "generated_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "reconstruction_version": reconstruction_version,
        "row_counts": row_counts,
        "source": source_metadata,
        "validation": {
            "status": "PASS" if validation.passed else "FAIL",
            "hard_failures": [issue.message for issue in validation.hard_failures],
            "warnings": [issue.message for issue in validation.warnings],
        },
    }


def _single_run_metadata(repository: Phase1DatasetRepository) -> RunMetadata:
    rows = repository.run_metadata_rows()
    if len(rows) != 1:
        raise DataValidationError(f"Expected exactly one simulation_run row, found {len(rows)}")
    return rows[0]


def _require_existing_database(database_path: str | Path) -> Path:
    resolved_path = Path(database_path)
    if not resolved_path.exists():
        raise DatabaseError(f"Database does not exist: {resolved_path}")
    if not resolved_path.is_file():
        raise DatabaseError(f"Database path is not a file: {resolved_path}")
    return resolved_path


def _validation_details(validation: ValidationResult) -> str:
    return "; ".join(f"[{issue.category}] {issue.message}" for issue in validation.hard_failures)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_output_directory(output_path: Path) -> None:
    try:
        if output_path.exists():
            shutil.rmtree(output_path)
    except OSError as exc:
        raise DatabaseError(f"Failed to remove incomplete analysis output: {output_path}") from exc
