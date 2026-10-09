"""Safe clone and verification workflows for writable sandbox copies."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from dataclasses import fields, replace
from datetime import UTC, datetime
from pathlib import Path

from operational_variance_toolkit.errors import (
    DatabaseError,
    DataValidationError,
    OutputExistsError,
    ToolkitError,
)
from operational_variance_toolkit.sandbox.domain import (
    SANDBOX_MANIFEST_VERSION,
    SANDBOX_SCHEMA_VERSION,
    SANDBOX_SQLITE_USER_VERSION,
    CloneSandboxResult,
    SandboxManifest,
    VerifiedSandbox,
)
from operational_variance_toolkit.sandbox.storage import (
    SandboxRepository,
    validate_sandbox_extension,
)
from operational_variance_toolkit.storage.database import (
    connect_database,
    connect_readonly_database,
    remove_database_artifacts,
)
from operational_variance_toolkit.storage.schema import WMS_SCHEMA_VERSION
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.version import get_version
from operational_variance_toolkit.wms.storage.repositories import WmsFoundationRepository


def sandbox_manifest_path(database_path: str | Path) -> Path:
    path = Path(database_path)
    return path.with_name(f"{path.name}.sandbox.json")


def clone_sandbox(
    source_database: str | Path,
    destination_database: str | Path,
    *,
    created_at_utc: datetime | None = None,
) -> CloneSandboxResult:
    source = Path(source_database).resolve()
    destination = Path(destination_database).resolve()
    manifest_path = sandbox_manifest_path(destination)
    if source == destination:
        raise DataValidationError("Sandbox source and destination must be different files")
    if not source.is_file():
        raise DatabaseError(f"Sandbox source database does not exist: {source}")
    if destination.exists():
        raise OutputExistsError(f"Sandbox database already exists: {destination}")
    if manifest_path.exists():
        raise OutputExistsError(f"Sandbox manifest already exists: {manifest_path}")
    created_at = created_at_utc or datetime.now(tz=UTC)
    if created_at.tzinfo is None:
        raise DataValidationError("Sandbox creation time must be timezone-aware")

    source_sha256 = _sha256(source)
    try:
        with closing(connect_readonly_database(source)) as source_connection:
            if int(source_connection.execute("PRAGMA user_version").fetchone()[0]) != 3:
                raise DataValidationError(
                    "Sandbox cloning requires an accepted schema-3.0.0 source database"
                )
            validation = validate_wms_dataset(source_connection)
            if not validation.passed:
                raise DataValidationError("Sandbox source WMS validation failed")
            metadata = WmsFoundationRepository(source_connection).run_metadata()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(destination)) as destination_connection:
                source_connection.backup(destination_connection)
        if _sha256(source) != source_sha256:
            raise DataValidationError("Sandbox source changed during cloning; try again")

        manifest = SandboxManifest(
            manifest_version=SANDBOX_MANIFEST_VERSION,
            sandbox_id=f"SANDBOX-{uuid.uuid4().hex[:24].upper()}",
            sandbox_database_filename=destination.name,
            source_database_path=str(source),
            source_database_sha256=source_sha256,
            source_schema_version=WMS_SCHEMA_VERSION,
            source_run_id=metadata.run_id,
            sandbox_schema_version=SANDBOX_SCHEMA_VERSION,
            created_at_utc=_iso_utc(created_at),
            created_by_application_version=get_version(),
            initial_sandbox_sha256="",
        )
        with closing(connect_database(destination)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                SandboxRepository(connection).install_schema(manifest)
                connection.execute(f"PRAGMA user_version = {SANDBOX_SQLITE_USER_VERSION}")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            validation = validate_wms_dataset(connection, allow_sandbox=True)
            sandbox_validation = validate_sandbox_extension(connection)
            if not validation.passed or not sandbox_validation.passed:
                raise DataValidationError("New sandbox failed schema or WMS validation")
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        manifest = replace(manifest, initial_sandbox_sha256=_database_state_sha256(destination))
        _write_manifest_atomic(manifest_path, manifest)
        verified = verify_sandbox(destination)
        return CloneSandboxResult(
            database_path=verified.database_path,
            manifest_path=verified.manifest_path,
            manifest=verified.manifest,
        )
    except ToolkitError:
        _cleanup_incomplete(destination, manifest_path)
        raise
    except (OSError, sqlite3.DatabaseError, ValueError, TypeError) as exc:
        _cleanup_incomplete(destination, manifest_path)
        raise DatabaseError(f"Failed to clone sandbox at {destination}: {exc}") from exc


def verify_sandbox(database_path: str | Path) -> VerifiedSandbox:
    path = Path(database_path).resolve()
    manifest_path = sandbox_manifest_path(path)
    if not path.is_file():
        raise DatabaseError(f"Sandbox database does not exist: {path}")
    if not manifest_path.is_file():
        raise DataValidationError(f"Sandbox provenance manifest is missing: {manifest_path}")
    manifest = _load_manifest(manifest_path)
    if manifest.sandbox_database_filename != path.name:
        raise DataValidationError("Sandbox manifest database filename does not match")
    source_path = Path(manifest.source_database_path).resolve()
    if source_path == path:
        raise DataValidationError("Sandbox manifest reuses the source database path")
    if manifest.manifest_version != SANDBOX_MANIFEST_VERSION:
        raise DataValidationError("Unsupported sandbox manifest version")
    if manifest.sandbox_schema_version != SANDBOX_SCHEMA_VERSION:
        raise DataValidationError("Unsupported sandbox schema version")
    if manifest.source_schema_version != WMS_SCHEMA_VERSION:
        raise DataValidationError("Sandbox source schema version is not 3.0.0")
    _require_sha256(manifest.source_database_sha256, "source database SHA-256")
    _require_sha256(manifest.initial_sandbox_sha256, "initial sandbox SHA-256")

    try:
        with closing(connect_readonly_database(path)) as connection:
            wms_validation = validate_wms_dataset(connection, allow_sandbox=True)
            sandbox_validation = validate_sandbox_extension(connection)
            if not wms_validation.passed:
                raise DataValidationError("Sandbox WMS validation failed")
            if not sandbox_validation.passed:
                message = sandbox_validation.hard_failures[0].message
                raise DataValidationError(f"Sandbox extension validation failed: {message}")
            repository = SandboxRepository(connection)
            identity = repository.identity()
            assert identity is not None
            metadata = WmsFoundationRepository(connection).run_metadata()
            expected = {
                "sandbox_id": manifest.sandbox_id,
                "run_id": manifest.source_run_id,
                "manifest_version": manifest.manifest_version,
                "source_database_path": manifest.source_database_path,
                "source_database_sha256": manifest.source_database_sha256,
                "source_schema_version": manifest.source_schema_version,
                "sandbox_schema_version": manifest.sandbox_schema_version,
                "created_at_utc": manifest.created_at_utc,
                "created_by_application_version": manifest.created_by_application_version,
            }
            if any(identity.get(key) != value for key, value in expected.items()):
                raise DataValidationError("Sandbox database identity does not match its manifest")
            if metadata.run_id != manifest.source_run_id:
                raise DataValidationError("Sandbox run ID does not match its manifest")
            latest_batch = repository.latest_applied_batch_id()
        current_sha256 = _database_state_sha256(path)
        if latest_batch is None and current_sha256 != manifest.initial_sandbox_sha256:
            raise DataValidationError(
                "Sandbox changed outside an approved maintenance batch; re-clone it"
            )
        return VerifiedSandbox(
            database_path=path,
            manifest_path=manifest_path,
            manifest=manifest,
            current_sha256=current_sha256,
            latest_applied_batch_id=latest_batch,
        )
    except ToolkitError:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise DatabaseError(f"Unable to verify sandbox {path}: {exc}") from exc


def _load_manifest(path: Path) -> SandboxManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"Sandbox manifest is unreadable: {path}") from exc
    required = {field.name for field in fields(SandboxManifest)}
    if not isinstance(payload, dict) or set(payload) != required:
        raise DataValidationError("Sandbox manifest structure is invalid")
    if not all(isinstance(payload[name], str) for name in required):
        raise DataValidationError("Sandbox manifest values must be strings")
    return SandboxManifest(**payload)


def _write_manifest_atomic(path: Path, manifest: SandboxManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(manifest.as_dict(), handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise OutputExistsError(f"Sandbox manifest already exists: {path}") from exc
        temporary.unlink()
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _cleanup_incomplete(database_path: Path, manifest_path: Path) -> None:
    manifest_path.unlink(missing_ok=True)
    remove_database_artifacts(database_path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _database_state_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    wal_path = path.with_name(f"{path.name}-wal")
    if wal_path.is_file() and wal_path.stat().st_size:
        digest.update(b"\0WAL\0")
        digest.update(wal_path.read_bytes())
    return digest.hexdigest()


def _require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise DataValidationError(f"Sandbox manifest {label} is invalid")


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
