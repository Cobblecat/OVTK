"""SQLite database initialization and schema lifecycle helpers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.domain.run import build_neutral_run_id, build_run_record
from operational_variance_toolkit.errors import DatabaseError, OutputExistsError
from operational_variance_toolkit.storage.schema import (
    SCHEMA_BY_VERSION,
    SCHEMA_VERSION,
    WMS_SCHEMA_VERSION,
)
from operational_variance_toolkit.version import get_version


def initialize_database(
    output_path: str | Path,
    config: ProjectConfig,
    *,
    schema_version: str = SCHEMA_VERSION,
    generated_at_utc: datetime | None = None,
) -> Path:
    """Create a fresh Phase 1 SQLite database and its initial schema."""

    database_path = Path(output_path)
    if database_path.exists():
        raise OutputExistsError(f"Database already exists: {database_path}")
    if schema_version not in SCHEMA_BY_VERSION:
        raise DatabaseError(f"Unsupported schema version for initialization: {schema_version}")

    schema_sql, user_version = SCHEMA_BY_VERSION[schema_version]

    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = connect_database(database_path)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("BEGIN")
            connection.executescript(schema_sql)
            connection.execute(f"PRAGMA user_version = {user_version}")
            _write_run_metadata(
                connection,
                config,
                schema_version=schema_version,
                generated_at_utc=generated_at_utc,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except Exception as exc:
        if database_path.exists():
            try:
                database_path.unlink()
            except OSError:
                pass
        if isinstance(exc, (OutputExistsError, DatabaseError)):
            raise
        raise DatabaseError(f"Failed to initialize database at {database_path}: {exc}") from exc

    return database_path


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open a database connection with foreign keys enabled."""

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def connect_readonly_database(path: str | Path) -> sqlite3.Connection:
    """Open an existing database in read-only/query-only mode."""

    database_path = Path(path).resolve()
    uri = f"{database_path.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA query_only = ON")
    return connection


def database_user_version(path: str | Path) -> int:
    """Return the SQLite user version for an existing readable database."""

    database_path = Path(path)
    if not database_path.is_file():
        raise DatabaseError(f"Database does not exist: {database_path}")
    try:
        connection = connect_readonly_database(database_path)
        try:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to inspect database {database_path}: {exc}") from exc


def remove_database_artifacts(database_path: str | Path) -> None:
    """Remove a newly created incomplete SQLite artifact and its sidecars."""

    path = Path(database_path)
    for candidate in (
        path,
        path.with_name(f"{path.name}-wal"),
        path.with_name(f"{path.name}-shm"),
    ):
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError as exc:
            raise DatabaseError(
                f"Failed to remove incomplete database artifact: {candidate}"
            ) from exc


def _write_run_metadata(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    *,
    schema_version: str,
    generated_at_utc: datetime | None,
) -> None:
    if generated_at_utc is None:
        generated_at_utc = datetime.now(tz=UTC)
    if generated_at_utc.tzinfo is None:
        raise DatabaseError("generated_at_utc must be timezone-aware")

    if schema_version == WMS_SCHEMA_VERSION:
        _write_wms_run_metadata(
            connection,
            config,
            generated_at_utc=generated_at_utc,
        )
        return

    run_record = build_run_record(config, generated_at_utc=generated_at_utc)
    connection.execute(
        """
        INSERT INTO schema_metadata(schema_version, created_at_utc) VALUES (?, ?)
        """,
        (schema_version, run_record.generated_at_utc.isoformat()),
    )
    connection.execute(
        """
        INSERT INTO simulation_run(
            run_id,
            scenario_name,
            scenario_version,
            seed,
            schema_version,
            generator_version,
            config_hash,
            facility_timezone,
            simulation_start_utc,
            simulation_end_utc,
            generated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_record.run_id,
            run_record.scenario_name,
            run_record.scenario_version,
            run_record.seed,
            schema_version,
            run_record.generator_version,
            run_record.config_hash,
            run_record.facility_timezone,
            run_record.simulation_start_utc.isoformat(),
            run_record.simulation_end_utc.isoformat(),
            run_record.generated_at_utc.isoformat(),
        ),
    )
    connection.execute(
        """
        INSERT INTO facility(run_id, facility_id, facility_name, timezone)
        VALUES (?, ?, ?, ?)
        """,
        (
            run_record.run_id,
            config.facility.facility_id,
            config.facility.name,
            config.run.facility_timezone,
        ),
    )


def _write_wms_run_metadata(
    connection: sqlite3.Connection,
    config: ProjectConfig,
    *,
    generated_at_utc: datetime,
) -> None:
    run_id = build_neutral_run_id(
        config_hash=config.configuration_hash,
        seed=config.run.seed,
        schema_version=WMS_SCHEMA_VERSION,
    )
    generated_at = generated_at_utc.isoformat()
    connection.execute(
        """
        INSERT INTO schema_metadata(
            schema_version, sqlite_user_version, created_at_utc
        ) VALUES (?, ?, ?)
        """,
        (WMS_SCHEMA_VERSION, 3, generated_at),
    )
    connection.execute(
        """
        INSERT INTO simulation_run(
            run_id,
            seed,
            schema_version,
            generator_version,
            config_hash,
            facility_timezone,
            simulation_start_utc,
            simulation_end_utc,
            generated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            config.run.seed,
            WMS_SCHEMA_VERSION,
            get_version(),
            config.configuration_hash,
            config.run.facility_timezone,
            config.run.start_utc.isoformat(),
            config.run.end_utc.isoformat(),
            generated_at,
        ),
    )
    connection.execute(
        """
        INSERT INTO facility(run_id, facility_id, facility_name, timezone)
        VALUES (?, ?, ?, ?)
        """,
        (
            run_id,
            config.facility.facility_id,
            config.facility.name,
            config.run.facility_timezone,
        ),
    )
