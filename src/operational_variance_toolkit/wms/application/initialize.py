"""Schema-3 WMS foundation initialization workflow."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import DatabaseError, DataValidationError, ToolkitError
from operational_variance_toolkit.generation.wms_master_data import generate_wms_foundation
from operational_variance_toolkit.storage.database import (
    connect_database,
    initialize_database,
    remove_database_artifacts,
)
from operational_variance_toolkit.storage.schema import WMS_SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.storage.repositories import (
    WmsFoundationRepository,
    WmsRunMetadata,
)


@dataclass(frozen=True, slots=True)
class InitializeWmsFoundationResult:
    database_path: Path
    run_metadata: WmsRunMetadata
    counts: dict[str, int]
    validation: ValidationResult


def initialize_wms_foundation(
    config_path: str | Path,
    output_path: str | Path,
    *,
    generated_at_utc: datetime | None = None,
) -> InitializeWmsFoundationResult:
    """Create and validate a fresh schema-3 WMS foundation database."""

    config = load_project_config(config_path)
    database_path = Path(output_path)
    created_path: Path | None = None
    try:
        created_path = initialize_database(
            database_path,
            config,
            schema_version=WMS_SCHEMA_VERSION,
            generated_at_utc=generated_at_utc,
        )
        with closing(connect_database(created_path)) as connection:
            repository = WmsFoundationRepository(connection)
            metadata = repository.run_metadata()
            records = generate_wms_foundation(config, metadata.run_id)
            with connection:
                repository.insert_foundation(records)
                validation = validate_wms_dataset(connection)
                if not validation.passed:
                    messages = "; ".join(issue.message for issue in validation.hard_failures[:3])
                    raise DataValidationError(
                        f"Generated schema-3 WMS foundation failed validation: {messages}"
                    )
            counts = repository.table_counts()
        return InitializeWmsFoundationResult(
            database_path=created_path,
            run_metadata=metadata,
            counts=counts,
            validation=validation,
        )
    except Exception as exc:
        if created_path is not None:
            remove_database_artifacts(created_path)
        if isinstance(exc, ToolkitError):
            raise
        if isinstance(exc, sqlite3.DatabaseError):
            raise DatabaseError(
                f"Failed while initializing schema-3 WMS at {database_path}: {exc}"
            ) from exc
        raise


def canonical_wms_foundation_content(
    database_path: str | Path,
) -> dict[str, list[tuple[object, ...]]]:
    """Return deterministic schema-3 foundation content for comparisons."""

    with closing(connect_database(database_path)) as connection:
        return WmsFoundationRepository(connection).canonical_foundation_rows()
