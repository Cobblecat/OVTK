from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest

from operational_variance_toolkit.console.commands import CommandDispatcher
from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleMode, ConsoleSession
from operational_variance_toolkit.errors import (
    DataValidationError,
    OutputExistsError,
)
from operational_variance_toolkit.sandbox.application import (
    clone_sandbox,
    sandbox_manifest_path,
    verify_sandbox,
)
from operational_variance_toolkit.sandbox.schema import SANDBOX_TABLES
from operational_variance_toolkit.sandbox.storage import SandboxRepository
from operational_variance_toolkit.storage.database import (
    connect_readonly_database,
    database_user_version,
)
from operational_variance_toolkit.wms.application.reports import (
    available_reports,
    run_wms_report,
)
from operational_variance_toolkit.wms.storage.repositories import WmsFoundationRepository

NOW = datetime(2026, 8, 2, 16, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_clone_uses_additive_schema_and_preserves_canonical_wms_content(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "Sandbox Folder" / "Operations Copy.sqlite3"
    source_hash = _sha256(phase2_wms_path)

    result = clone_sandbox(
        phase2_wms_path,
        destination,
        created_at_utc=NOW,
    )

    assert _sha256(phase2_wms_path) == source_hash
    assert result.database_path == destination.resolve()
    assert result.manifest_path == sandbox_manifest_path(destination.resolve())
    assert result.manifest.source_database_sha256 == source_hash
    assert result.manifest.initial_sandbox_sha256 == _sha256(destination)
    assert result.manifest.created_at_utc == "2026-08-02T16:00:00Z"
    assert database_user_version(destination) == 4
    with connect_readonly_database(phase2_wms_path) as source_connection:
        source_rows = WmsFoundationRepository(source_connection).canonical_wms_rows()
    with connect_readonly_database(destination) as sandbox_connection:
        sandbox_rows = WmsFoundationRepository(sandbox_connection).canonical_wms_rows()
        assert set(SANDBOX_TABLES) <= SandboxRepository(sandbox_connection).table_names()
    assert sandbox_rows == source_rows
    with sqlite3.connect(destination) as writable:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            writable.execute("UPDATE sandbox_identity SET manifest_version = 'changed'")


def test_verified_sandbox_reopens_in_explicit_rw_mode_with_query_only_session(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "restart.sqlite3"
    clone_sandbox(phase2_wms_path, destination, created_at_utc=NOW)

    first = ConsoleSession(tmp_path, tmp_path / "workspace")
    first.open_sandbox(destination)
    assert first.mode is ConsoleMode.SANDBOX
    assert first.prompt == "WMS[RW:restart]> "
    assert first.schema_version == "3.1.0"
    assert first.connection.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
        first.connection.execute("CREATE TABLE forbidden_direct_write(value INTEGER)")
    first.close()

    second = ConsoleSession(tmp_path, tmp_path / "workspace")
    second.open_sandbox(destination)
    assert second.validate_database().passed
    assert second.describe_database().validation.passed
    second.close()


def test_ordinary_source_renamed_copy_and_implicit_open_never_gain_write_mode(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    renamed = tmp_path / "looks-like-a-sandbox.sqlite3"
    shutil.copy2(phase2_wms_path, renamed)
    session = ConsoleSession(tmp_path, tmp_path / "workspace")

    with pytest.raises(DataValidationError, match="manifest is missing"):
        session.open_sandbox(phase2_wms_path)
    with pytest.raises(DataValidationError, match="manifest is missing"):
        session.open_sandbox(renamed)

    real_sandbox = tmp_path / "real.sqlite3"
    clone_sandbox(phase2_wms_path, real_sandbox, created_at_utc=NOW)
    with pytest.raises(DataValidationError, match="console requires schema 3.0.0"):
        session.open_database(real_sandbox)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sandbox_id", "SANDBOX-TAMPERED", "identity does not match"),
        ("sandbox_database_filename", "other.sqlite3", "filename does not match"),
        ("sandbox_schema_version", "9.0.0", "Unsupported sandbox schema"),
        ("initial_sandbox_sha256", "bad", "SHA-256 is invalid"),
    ],
)
def test_tampered_manifest_is_rejected(
    field: str,
    value: str,
    message: str,
    phase2_wms_path: Path,
    tmp_path: Path,
) -> None:
    destination = tmp_path / f"tamper-{field}.sqlite3"
    result = clone_sandbox(phase2_wms_path, destination, created_at_utc=NOW)
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    payload[field] = value
    result.manifest_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError, match=message):
        verify_sandbox(destination)


def test_unapproved_database_change_is_detected_before_any_batch_exists(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "changed.sqlite3"
    clone_sandbox(phase2_wms_path, destination, created_at_utc=NOW)
    with sqlite3.connect(destination) as connection:
        connection.execute("CREATE TABLE unapproved_change(value TEXT)")

    with pytest.raises(DataValidationError, match="changed outside"):
        verify_sandbox(destination)


def test_clone_refuses_existing_same_path_and_cleans_failed_upgrade(
    phase2_wms_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(DataValidationError, match="different files"):
        clone_sandbox(phase2_wms_path, phase2_wms_path)

    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"keep")
    with pytest.raises(OutputExistsError):
        clone_sandbox(phase2_wms_path, existing)
    assert existing.read_bytes() == b"keep"

    failed = tmp_path / "failed.sqlite3"

    def fail_install(_self, _manifest):
        raise sqlite3.DatabaseError("injected schema failure")

    monkeypatch.setattr(SandboxRepository, "install_schema", fail_install)
    with pytest.raises(Exception, match="injected schema failure"):
        clone_sandbox(phase2_wms_path, failed)
    assert not failed.exists()
    assert not sandbox_manifest_path(failed).exists()
    assert not failed.with_name(f"{failed.name}-wal").exists()
    assert not failed.with_name(f"{failed.name}-shm").exists()


def test_all_reports_run_against_verified_sandbox(phase2_wms_path: Path, tmp_path: Path) -> None:
    destination = tmp_path / "reports.sqlite3"
    clone_sandbox(phase2_wms_path, destination, created_at_utc=NOW)
    with connect_readonly_database(destination) as connection:
        closing_batch = connection.execute(
            "SELECT snapshot_batch_id FROM inventory_snapshot "
            "WHERE snapshot_type = 'CLOSING_SYSTEM' LIMIT 1"
        ).fetchone()[0]
    required = {
        "code-date-inventory": {"as_of_date": "2026-05-14"},
        "inventory-snapshot": {"snapshot_batch": closing_batch},
        "inventory-reconciliation": {"snapshot_batch": closing_batch},
    }

    for spec in available_reports():
        result = run_wms_report(destination, spec.code, required.get(spec.code, {}))
        assert result.spec.code == spec.code


def test_console_clone_status_close_and_reopen_keep_source_separate(
    phase2_wms_path: Path, tmp_path: Path
) -> None:
    stdout, stderr = StringIO(), StringIO()
    session = ConsoleSession(tmp_path, tmp_path / "workspace")
    session.open_database(phase2_wms_path)
    source_connection = session.connection
    dispatcher = CommandDispatcher(
        session,
        ConsoleRenderer(stdout, stderr, no_style=True),
        ResourceResolver(tmp_path),
    )
    destination = tmp_path / "Console Sandbox.sqlite3"

    assert dispatcher.dispatch_line(f'clone "{destination}"').succeeded
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        source_connection.execute("SELECT 1")
    assert session.mode is ConsoleMode.SANDBOX
    assert dispatcher.dispatch_line("status").succeeded
    assert dispatcher.dispatch_line("close").succeeded
    assert dispatcher.dispatch_line(f'open-sandbox "{destination}"').succeeded
    session.close()

    output = stdout.getvalue()
    assert "Sandbox created and verified." in output
    assert "Mode: WRITABLE SANDBOX" in output
    assert "Source SHA-256:" in output
    assert "Current sandbox SHA-256:" in output
    assert "Latest applied batch: none" in output
    assert "Supported write workflows: none at the Phase 3 checkpoint" in output
    assert stderr.getvalue() == ""
