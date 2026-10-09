"""Typed sandbox provenance and lifecycle results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

SANDBOX_SCHEMA_VERSION = "3.1.0"
SANDBOX_SQLITE_USER_VERSION = 4
SANDBOX_MANIFEST_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SandboxManifest:
    manifest_version: str
    sandbox_id: str
    sandbox_database_filename: str
    source_database_path: str
    source_database_sha256: str
    source_schema_version: str
    source_run_id: str
    sandbox_schema_version: str
    created_at_utc: str
    created_by_application_version: str
    initial_sandbox_sha256: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CloneSandboxResult:
    database_path: Path
    manifest_path: Path
    manifest: SandboxManifest


@dataclass(frozen=True, slots=True)
class VerifiedSandbox:
    database_path: Path
    manifest_path: Path
    manifest: SandboxManifest
    current_sha256: str
    latest_applied_batch_id: str | None
