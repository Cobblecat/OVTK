"""Phase 1 application workflows."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import DatabaseError, DataValidationError, ToolkitError
from operational_variance_toolkit.generation.master_data import generate_master_data
from operational_variance_toolkit.generation.opening_inventory import generate_opening_inventory
from operational_variance_toolkit.storage.database import connect_database, initialize_database
from operational_variance_toolkit.storage.repositories import (
    Phase1DatasetRepository,
    RunMetadata,
)
from operational_variance_toolkit.validation.dataset import validate_dataset
from operational_variance_toolkit.validation.phase1 import validate_phase1_dataset
from operational_variance_toolkit.validation.result import ValidationResult


@dataclass(frozen=True, slots=True)
class InitializeDatabaseResult:
    database_path: Path
    run_metadata: RunMetadata
    config_hash: str
    counts: dict[str, int]
    validation: ValidationResult


@dataclass(frozen=True, slots=True)
class ValidateDatasetResult:
    database_path: Path
    validation: ValidationResult


@dataclass(frozen=True, slots=True)
class DescribeDatasetResult:
    database_path: Path
    run_metadata: RunMetadata
    table_counts: dict[str, int]
    opening_totals_by_zone: list[tuple[str, int]]
    closing_totals_by_zone: list[tuple[str, int]]
    validation: ValidationResult


def initialize_phase1_database(config_path: str | Path) -> InitializeDatabaseResult:
    """Create a fresh Phase 1 database from a validated configuration."""

    config = load_project_config(config_path)
    database_path = config.storage.database_path
    created_path: Path | None = None

    try:
        created_path = initialize_database(database_path, config)
        with closing(connect_database(created_path)) as connection:
            repository = Phase1DatasetRepository(connection)
            run_id = _single_run_metadata(repository).run_id
            with connection:
                generate_master_data(connection, config, run_id)
                generate_opening_inventory(connection, config, run_id)
                validation = validate_phase1_dataset(connection)
                if not validation.passed:
                    raise DataValidationError("Generated Phase 1 database failed validation")

        with closing(connect_database(created_path)) as connection:
            repository = Phase1DatasetRepository(connection)
            run_metadata = _single_run_metadata(repository)
            counts = repository.table_counts()
        return InitializeDatabaseResult(
            database_path=created_path,
            run_metadata=run_metadata,
            config_hash=config.configuration_hash,
            counts=counts,
            validation=validation,
        )
    except Exception as exc:
        if created_path is not None:
            _remove_database_artifacts(created_path)
        if isinstance(exc, ToolkitError):
            raise
        if isinstance(exc, sqlite3.DatabaseError):
            raise DatabaseError(
                f"Failed while writing Phase 1 database at {database_path}: {exc}"
            ) from exc
        raise


def validate_phase1_database(database_path: str | Path) -> ValidateDatasetResult:
    """Validate an existing supported database."""

    resolved_path = _require_existing_database(database_path)
    try:
        with closing(_connect_existing_database(resolved_path)) as connection:
            validation = validate_dataset(connection)
    except DatabaseError as exc:
        raise DatabaseError(f"Unable to validate database at {resolved_path}: {exc}") from exc
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to validate database at {resolved_path}: {exc}") from exc
    return ValidateDatasetResult(database_path=resolved_path, validation=validation)


def describe_phase1_database(database_path: str | Path) -> DescribeDatasetResult:
    """Return factual metadata and validation status for an existing supported database."""

    resolved_path = _require_existing_database(database_path)
    try:
        with closing(_connect_existing_database(resolved_path)) as connection:
            repository = Phase1DatasetRepository(connection)
            validation = validate_dataset(connection)
            if not validation.passed:
                raise DataValidationError(
                    "Cannot describe a database with hard validation failures"
                )
            return DescribeDatasetResult(
                database_path=resolved_path,
                run_metadata=_single_run_metadata(repository),
                table_counts=repository.table_counts(),
                opening_totals_by_zone=repository.opening_totals_by_zone(),
                closing_totals_by_zone=repository.closing_totals_by_zone(),
                validation=validation,
            )
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to describe database at {resolved_path}: {exc}") from exc


def canonical_phase1_content(database_path: str | Path) -> dict[str, list[tuple[Any, ...]]]:
    """Return deterministic table content for reproducibility comparisons."""

    resolved_path = _require_existing_database(database_path)
    try:
        with closing(_connect_existing_database(resolved_path)) as connection:
            repository = Phase1DatasetRepository(connection)
            return repository.canonical_table_rows()
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to read database at {resolved_path}: {exc}") from exc


def _single_run_metadata(repository: Phase1DatasetRepository) -> RunMetadata:
    rows = repository.run_metadata_rows()
    if len(rows) != 1:
        raise DatabaseError(f"Expected exactly one simulation_run row, found {len(rows)}")
    return rows[0]


def _require_existing_database(database_path: str | Path) -> Path:
    resolved_path = Path(database_path)
    if not resolved_path.exists():
        raise DatabaseError(f"Database does not exist: {resolved_path}")
    if not resolved_path.is_file():
        raise DatabaseError(f"Database path is not a file: {resolved_path}")
    return resolved_path


def _connect_existing_database(database_path: Path) -> sqlite3.Connection:
    try:
        connection = connect_database(database_path)
        connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        return connection
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to open database at {database_path}: {exc}") from exc


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
