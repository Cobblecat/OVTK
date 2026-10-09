"""Explicit state and read-only database lifecycle for console sessions."""

from __future__ import annotations

import sqlite3
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from operational_variance_toolkit.console.output import terminal_text
from operational_variance_toolkit.errors import DatabaseError, DataValidationError, ToolkitError
from operational_variance_toolkit.sandbox.application import verify_sandbox
from operational_variance_toolkit.sandbox.domain import VerifiedSandbox
from operational_variance_toolkit.sandbox.storage import validate_sandbox_extension
from operational_variance_toolkit.storage.database import connect_readonly_database
from operational_variance_toolkit.storage.repositories import Phase1DatasetRepository
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.describe import DescribeWmsResult, describe_wms
from operational_variance_toolkit.wms.storage.repositories import WmsFoundationRepository

DEFAULT_RESULT_LIMIT = 25
DEFAULT_DISPLAY_FORMAT = "vertical"
DEFAULT_TIMESTAMP_PREFERENCE = "utc"
MAX_SESSION_HISTORY = 500


class ConsoleMode(StrEnum):
    NO_DATABASE = "NO DB"
    READ_ONLY = "RO"
    SANDBOX = "RW"


@dataclass(slots=True)
class ConsoleSession:
    working_directory: Path
    output_directory: Path
    result_limit: int = DEFAULT_RESULT_LIMIT
    display_format: str = DEFAULT_DISPLAY_FORMAT
    timestamp_preference: str = DEFAULT_TIMESTAMP_PREFERENCE
    database_path: Path | None = None
    schema_version: str | None = None
    run_id: str | None = None
    facility_id: str | None = None
    facility_name: str | None = None
    facility_timezone: str | None = None
    provenance: str | None = None
    validation: ValidationResult | None = None
    validation_checked_at_utc: datetime | None = None
    command_history: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_SESSION_HISTORY))
    _connection: sqlite3.Connection | None = field(default=None, repr=False)
    _sandbox: VerifiedSandbox | None = field(default=None, repr=False)

    @property
    def mode(self) -> ConsoleMode:
        if self._sandbox is not None:
            return ConsoleMode.SANDBOX
        return ConsoleMode.READ_ONLY if self._connection is not None else ConsoleMode.NO_DATABASE

    @property
    def prompt(self) -> str:
        if self.database_path is None:
            return "WMS[NO DB]> "
        if self.mode is ConsoleMode.SANDBOX:
            return f"WMS[RW:{terminal_text(self.database_path.stem)}]> "
        return f"WMS[RO:{terminal_text(self.database_path.stem)}]> "

    @property
    def sandbox(self) -> VerifiedSandbox:
        if self._sandbox is None:
            raise DataValidationError("No verified sandbox is open")
        return self._sandbox

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DataValidationError("No database is open. Use open <database> or sample.")
        return self._connection

    def open_database(self, database_path: str | Path, *, provenance: str = "user") -> None:
        path = Path(database_path).resolve()
        if not path.exists():
            raise DatabaseError(f"Database does not exist: {path}")
        if not path.is_file():
            raise DatabaseError(f"Database path is not a file: {path}")

        candidate: sqlite3.Connection | None = None
        try:
            candidate = connect_readonly_database(path)
            user_version = Phase1DatasetRepository(candidate).user_version()
            if user_version != 3:
                label = "legacy" if user_version in {1, 2} else "unsupported"
                raise DataValidationError(
                    f"Cannot open {label} SQLite user_version {user_version}; "
                    "the console requires schema 3.0.0."
                )

            query_only = int(candidate.execute("PRAGMA query_only").fetchone()[0])
            if query_only != 1:
                raise DatabaseError("Read-only query protection was not enabled")

            validation = validate_wms_dataset(candidate)
            if not validation.passed:
                first_issue = validation.hard_failures[0]
                raise DataValidationError(
                    "Cannot open invalid schema-3 WMS: "
                    f"[{first_issue.category}] {first_issue.message}"
                )

            repository = WmsFoundationRepository(candidate)
            metadata = repository.run_metadata()
            facility_id, facility_name = repository.facility_identity()
        except ToolkitError:
            if candidate is not None:
                candidate.close()
            raise
        except sqlite3.DatabaseError as exc:
            if candidate is not None:
                candidate.close()
            raise DatabaseError(f"Unable to open database {path}: {exc}") from exc

        self.close_database()
        self._connection = candidate
        self.database_path = path
        self.schema_version = metadata.schema_version
        self.run_id = metadata.run_id
        self.facility_id = facility_id
        self.facility_name = facility_name
        self.facility_timezone = metadata.facility_timezone
        self.provenance = provenance
        self.validation = validation
        self.validation_checked_at_utc = datetime.now(tz=UTC)

    def open_sandbox(self, database_path: str | Path) -> None:
        verified = verify_sandbox(database_path)
        candidate: sqlite3.Connection | None = None
        try:
            candidate = connect_readonly_database(verified.database_path)
            validation = validate_wms_dataset(candidate, allow_sandbox=True)
            extension = validate_sandbox_extension(candidate)
            if not validation.passed or not extension.passed:
                raise DataValidationError("Cannot open an invalid schema-3.1.0 sandbox")
            repository = WmsFoundationRepository(candidate)
            metadata = repository.run_metadata()
            facility_id, facility_name = repository.facility_identity()
        except ToolkitError:
            if candidate is not None:
                candidate.close()
            raise
        except sqlite3.DatabaseError as exc:
            if candidate is not None:
                candidate.close()
            raise DatabaseError(f"Unable to open sandbox {verified.database_path}: {exc}") from exc

        self.close_database()
        self._connection = candidate
        self._sandbox = verified
        self.database_path = verified.database_path
        self.schema_version = verified.manifest.sandbox_schema_version
        self.run_id = metadata.run_id
        self.facility_id = facility_id
        self.facility_name = facility_name
        self.facility_timezone = metadata.facility_timezone
        self.provenance = "verified sandbox"
        self.validation = ValidationResult(
            validation.hard_failures + extension.hard_failures,
            validation.warnings + extension.warnings,
        )
        self.validation_checked_at_utc = datetime.now(tz=UTC)

    def close_database(self) -> bool:
        had_database = self._connection is not None
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._sandbox = None
        self.database_path = None
        self.schema_version = None
        self.run_id = None
        self.facility_id = None
        self.facility_name = None
        self.facility_timezone = None
        self.provenance = None
        self.validation = None
        self.validation_checked_at_utc = None
        return had_database

    def validate_database(self) -> ValidationResult:
        if self.mode is ConsoleMode.SANDBOX:
            wms_result = validate_wms_dataset(self.connection, allow_sandbox=True)
            extension = validate_sandbox_extension(self.connection)
            result = ValidationResult(
                wms_result.hard_failures + extension.hard_failures,
                wms_result.warnings + extension.warnings,
            )
        else:
            result = validate_wms_dataset(self.connection)
        self.validation = result
        self.validation_checked_at_utc = datetime.now(tz=UTC)
        return result

    def describe_database(self) -> DescribeWmsResult:
        if self.database_path is None:
            raise DataValidationError("No database is open. Use open <database> or sample.")
        return describe_wms(self.database_path)

    def record_command(self, command: str) -> None:
        value = command.strip()
        if value:
            self.command_history.append(value)

    def close(self) -> None:
        self.close_database()

    def __enter__(self) -> ConsoleSession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
