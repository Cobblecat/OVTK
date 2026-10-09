"""Phase 2 application workflows."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import (
    ConfigurationError,
    DatabaseError,
    DataValidationError,
    ToolkitError,
)
from operational_variance_toolkit.generation.master_data import generate_master_data
from operational_variance_toolkit.generation.opening_inventory import generate_opening_inventory
from operational_variance_toolkit.generation.operations import (
    OperationGenerationCounts,
    generate_normal_operations,
)
from operational_variance_toolkit.storage.database import connect_database, initialize_database
from operational_variance_toolkit.storage.ground_truth import write_ground_truth_artifact
from operational_variance_toolkit.storage.repositories import Phase1DatasetRepository, RunMetadata
from operational_variance_toolkit.storage.schema import PHASE2_SCHEMA_VERSION
from operational_variance_toolkit.validation.dataset import validate_dataset
from operational_variance_toolkit.validation.result import ValidationResult


@dataclass(frozen=True, slots=True)
class GeneratePhase2Result:
    database_path: Path
    ground_truth_path: Path | None
    run_metadata: RunMetadata
    config_hash: str
    counts: dict[str, int]
    operation_counts: OperationGenerationCounts
    validation: ValidationResult


def generate_phase2_database(
    config_path: str | Path,
    output_path: str | Path,
    ground_truth_path: str | Path | None = None,
) -> GeneratePhase2Result:
    """Create a fresh Phase 2/3 database from a validated configuration."""

    config = load_project_config(config_path)
    database_path = Path(output_path)
    resolved_ground_truth_path = Path(ground_truth_path) if ground_truth_path is not None else None
    if config.failures.any_enabled and resolved_ground_truth_path is None:
        raise ConfigurationError(
            "A separate --ground-truth path is required when failure overlays are enabled."
        )
    if not config.failures.any_enabled and resolved_ground_truth_path is not None:
        raise ConfigurationError(
            "--ground-truth is only supported when failure overlays are enabled."
        )
    if resolved_ground_truth_path is not None and resolved_ground_truth_path.exists():
        from operational_variance_toolkit.errors import OutputExistsError

        raise OutputExistsError(
            f"Ground-truth artifact already exists: {resolved_ground_truth_path}"
        )

    created_path: Path | None = None
    created_ground_truth_path: Path | None = None

    try:
        created_path = initialize_database(
            database_path,
            config,
            schema_version=PHASE2_SCHEMA_VERSION,
        )
        with closing(connect_database(created_path)) as connection:
            repository = Phase1DatasetRepository(connection)
            run_id = _single_run_metadata(repository).run_id
            with connection:
                generate_master_data(connection, config, run_id)
                generate_opening_inventory(connection, config, run_id)
                operation_counts = generate_normal_operations(connection, config, run_id)
                validation = validate_dataset(connection)
                if not validation.passed:
                    details = "; ".join(
                        f"[{issue.category}] {issue.message}" for issue in validation.hard_failures
                    )
                    raise DataValidationError(
                        f"Generated Phase 2 database failed validation: {details}"
                    )

        with closing(connect_database(created_path)) as connection:
            repository = Phase1DatasetRepository(connection)
            run_metadata = _single_run_metadata(repository)
            counts = repository.table_counts()
        if resolved_ground_truth_path is not None:
            payload = {
                **operation_counts.scenario_ground_truth,
                "artifact_type": "restricted_ground_truth",
                "table_counts": counts,
            }
            created_ground_truth_path = write_ground_truth_artifact(
                resolved_ground_truth_path, payload
            )
        return GeneratePhase2Result(
            database_path=created_path,
            ground_truth_path=created_ground_truth_path,
            run_metadata=run_metadata,
            config_hash=config.configuration_hash,
            counts=counts,
            operation_counts=operation_counts,
            validation=validation,
        )
    except Exception as exc:
        if created_path is not None:
            _remove_database_artifacts(created_path)
        if created_ground_truth_path is not None:
            _remove_file(created_ground_truth_path)
        if isinstance(exc, ToolkitError):
            raise
        if isinstance(exc, sqlite3.DatabaseError):
            raise DatabaseError(
                f"Failed while writing Phase 2 database at {database_path}: {exc}"
            ) from exc
        raise


def _single_run_metadata(repository: Phase1DatasetRepository) -> RunMetadata:
    rows = repository.run_metadata_rows()
    if len(rows) != 1:
        raise DatabaseError(f"Expected exactly one simulation_run row, found {len(rows)}")
    return rows[0]


def _remove_database_artifacts(database_path: Path) -> None:
    for candidate in (
        database_path,
        database_path.with_name(f"{database_path.name}-wal"),
        database_path.with_name(f"{database_path.name}-shm"),
    ):
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError as exc:
            raise DatabaseError(
                f"Failed to remove incomplete database artifact: {candidate}"
            ) from exc


def _remove_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        raise DatabaseError(f"Failed to remove incomplete artifact: {path}") from exc
