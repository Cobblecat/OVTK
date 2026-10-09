"""Persistence and validation adapters for sandbox-only schema extensions."""

from __future__ import annotations

import sqlite3

from operational_variance_toolkit.sandbox.domain import SandboxManifest
from operational_variance_toolkit.sandbox.schema import SANDBOX_SCHEMA_STATEMENTS, SANDBOX_TABLES
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult


class SandboxRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def install_schema(self, manifest: SandboxManifest) -> None:
        for statement in SANDBOX_SCHEMA_STATEMENTS:
            self._connection.execute(statement)
        self._connection.execute(
            """
            INSERT INTO sandbox_identity(
                sandbox_id, run_id, manifest_version, source_database_path,
                source_database_sha256, source_schema_version,
                sandbox_schema_version, created_at_utc,
                created_by_application_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.sandbox_id,
                manifest.source_run_id,
                manifest.manifest_version,
                manifest.source_database_path,
                manifest.source_database_sha256,
                manifest.source_schema_version,
                manifest.sandbox_schema_version,
                manifest.created_at_utc,
                manifest.created_by_application_version,
            ),
        )

    def identity(self) -> dict[str, object] | None:
        self._connection.row_factory = sqlite3.Row
        row = self._connection.execute("SELECT * FROM sandbox_identity").fetchone()
        return dict(row) if row is not None else None

    def table_names(self) -> set[str]:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {str(row[0]) for row in rows}

    def user_version(self) -> int:
        return int(self._connection.execute("PRAGMA user_version").fetchone()[0])

    def integrity_check(self) -> str:
        return str(self._connection.execute("PRAGMA integrity_check").fetchone()[0])

    def latest_applied_batch_id(self) -> str | None:
        row = self._connection.execute(
            """
            SELECT batch_id FROM maintenance_batch
            WHERE status = 'APPLIED'
            ORDER BY applied_at_utc DESC, batch_id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row[0]) if row is not None else None


def validate_sandbox_extension(connection: sqlite3.Connection) -> ValidationResult:
    repository = SandboxRepository(connection)
    failures: list[ValidationIssue] = []
    missing = sorted(set(SANDBOX_TABLES) - repository.table_names())
    if missing:
        failures.append(
            ValidationIssue("sandbox_schema", f"Missing sandbox table(s): {', '.join(missing)}")
        )
        return ValidationResult(tuple(failures))
    if repository.user_version() != 4:
        failures.append(
            ValidationIssue(
                "sandbox_schema",
                f"Unsupported sandbox SQLite user_version: {repository.user_version()}",
            )
        )
    identity = repository.identity()
    if identity is None:
        failures.append(ValidationIssue("sandbox_identity", "Sandbox identity is missing"))
    elif identity["sandbox_schema_version"] != "3.1.0":
        failures.append(ValidationIssue("sandbox_identity", "Sandbox identity schema is not 3.1.0"))
    if repository.integrity_check() != "ok":
        failures.append(ValidationIssue("sandbox_integrity", "SQLite integrity check failed"))
    return ValidationResult(tuple(failures))
