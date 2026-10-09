"""Deterministic local release packaging and leakage verification."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.version import get_version

SOURCE_DIRECTORIES = ("configs", "docs", "notebooks", "reference", "src", "tests")
SOURCE_FILES = (
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.md",
    "PROJECT_STATUS.md",
    "README.md",
    "RELEASE_NOTES_0.1.0.md",
    "pyproject.toml",
    "uv.lock",
)
EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".ipynb_checkpoints",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "scratch",
    "tmp",
}
GENERATED_TRUTH_TOKENS = (
    "affected_pick_ids",
    "affected_qa_event_ids",
    "physical_completed_utc",
    "replenishment_timing_gap",
    "qa_damage_masking",
    "selector_false_lead",
    "true_root_cause",
    "is_injected_anomaly",
)
FORBIDDEN_DATABASE_NAMES = {
    "ground_truth",
    "scenario_target",
    "physical_completion",
    "true_mechanism",
    "is_injected_anomaly",
    "true_root_cause",
}


@dataclass(frozen=True, slots=True)
class PackageReleaseResult:
    version: str
    source_archive_path: Path
    source_archive_sha256: str
    source_checksum_path: Path
    truth_archive_path: Path
    truth_archive_sha256: str
    truth_checksum_path: Path
    combined_checksum_path: Path
    source_file_count: int
    truth_file_count: int
    leakage_status: str


def package_release(
    workspace_path: str | Path,
    output_path: str | Path,
    baseline_database_path: str | Path,
    investigation_database_path: str | Path,
    baseline_reconstruction_path: str | Path,
    investigation_reconstruction_path: str | Path,
    statistics_path: str | Path,
    standard_reports_path: str | Path,
    reporting_path: str | Path,
    restricted_ground_truth_path: str | Path,
) -> PackageReleaseResult:
    """Create separate deterministic source and optional truth archives."""

    workspace = Path(workspace_path).resolve()
    output = Path(output_path).resolve()
    version = get_version()
    source_name = f"operational-variance-toolkit-{version}-source.zip"
    truth_name = f"operational-variance-toolkit-{version}-ground-truth-optional.zip"
    source_archive = output / source_name
    truth_archive = output / truth_name
    source_checksum = output / f"{source_name}.sha256"
    truth_checksum = output / f"{truth_name}.sha256"
    combined_checksum = output / "SHA256SUMS.txt"
    for path in (
        source_archive,
        truth_archive,
        source_checksum,
        truth_checksum,
        combined_checksum,
    ):
        if path.exists():
            raise OutputExistsError(f"Release output already exists: {path}")

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ovt-release-") as temporary:
        temporary_root = Path(temporary)
        source_root = temporary_root / f"operational-variance-toolkit-{version}"
        truth_root = temporary_root / (
            f"operational-variance-toolkit-{version}-ground-truth-optional"
        )
        _stage_source_files(workspace, source_root)
        _stage_release_artifacts(
            source_root,
            baseline_database_path,
            investigation_database_path,
            baseline_reconstruction_path,
            investigation_reconstruction_path,
            statistics_path,
            standard_reports_path,
            reporting_path,
        )
        _write_primary_metadata(source_root, version)
        _verify_primary_stage(source_root, workspace)
        source_file_count = sum(path.is_file() for path in source_root.rglob("*"))
        _write_deterministic_zip(source_root, source_archive)
        _verify_archive_inventory(source_archive, "RELEASE_MANIFEST.json", "SHA256SUMS.txt")

        _stage_truth_archive(truth_root, restricted_ground_truth_path, version)
        truth_file_count = sum(path.is_file() for path in truth_root.rglob("*"))
        _write_deterministic_zip(truth_root, truth_archive)
        _verify_archive_inventory(truth_archive, "GROUND_TRUTH_MANIFEST.json", "SHA256SUMS.txt")

    source_hash = _sha256(source_archive)
    truth_hash = _sha256(truth_archive)
    source_checksum.write_text(f"{source_hash}  {source_name}\n", encoding="utf-8")
    truth_checksum.write_text(f"{truth_hash}  {truth_name}\n", encoding="utf-8")
    combined_checksum.write_text(
        f"{source_hash}  {source_name}\n{truth_hash}  {truth_name}\n",
        encoding="utf-8",
    )
    return PackageReleaseResult(
        version=version,
        source_archive_path=source_archive,
        source_archive_sha256=source_hash,
        source_checksum_path=source_checksum,
        truth_archive_path=truth_archive,
        truth_archive_sha256=truth_hash,
        truth_checksum_path=truth_checksum,
        combined_checksum_path=combined_checksum,
        source_file_count=source_file_count,
        truth_file_count=truth_file_count,
        leakage_status="PASS",
    )


def _stage_source_files(workspace: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for relative in SOURCE_FILES:
        source = workspace / relative
        if not source.is_file():
            raise DataValidationError(f"Required release source file is missing: {relative}")
        _copy_file(source, destination / relative)
    for directory in SOURCE_DIRECTORIES:
        source_root = workspace / directory
        if not source_root.is_dir():
            raise DataValidationError(f"Required release source directory is missing: {directory}")
        for source in sorted(source_root.rglob("*")):
            relative = source.relative_to(workspace)
            if source.is_file() and not EXCLUDED_PARTS.intersection(relative.parts):
                _copy_file(source, destination / relative)


def _stage_release_artifacts(
    destination: Path,
    baseline_database_path: str | Path,
    investigation_database_path: str | Path,
    baseline_reconstruction_path: str | Path,
    investigation_reconstruction_path: str | Path,
    statistics_path: str | Path,
    standard_reports_path: str | Path,
    reporting_path: str | Path,
) -> None:
    artifacts = destination / "release_artifacts"
    data = artifacts / "data"
    data.mkdir(parents=True)
    _copy_required_file(
        baseline_database_path, data / "schema3_baseline.sqlite3", "baseline database"
    )
    _copy_required_file(
        investigation_database_path,
        data / "schema3_investigation.sqlite3",
        "investigation database",
    )
    _copy_required_tree(
        baseline_reconstruction_path,
        artifacts / "reconstruction" / "baseline",
        "baseline reconstruction",
    )
    _copy_required_tree(
        investigation_reconstruction_path,
        artifacts / "reconstruction" / "investigation",
        "investigation reconstruction",
    )
    statistics_destination = artifacts / "statistics"
    _copy_required_tree(statistics_path, statistics_destination, "frozen statistics")
    _sanitize_statistics_manifest(statistics_destination / "analysis_manifest.json")
    _copy_required_tree(standard_reports_path, artifacts / "standard_reports", "standard reports")
    _copy_required_tree(reporting_path, artifacts / "reporting", "Phase 6 reporting")
    (artifacts / "README.md").write_text(
        "# Accepted Synthetic Example Artifacts\n\n"
        "These files are deterministic analyst-facing examples for release 0.1.0. They contain "
        "synthetic data only. Restricted ground truth, hidden physical timing, and true mechanism "
        "labels are intentionally absent. The canonical workflow can regenerate each artifact.\n",
        encoding="utf-8",
    )


def _sanitize_statistics_manifest(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["source"]["path"] = "release_artifacts/data/schema3_investigation.sqlite3"
    payload["source"]["reconstruction_path"] = "release_artifacts/reconstruction/investigation"
    if "comparison_source" in payload:
        payload["comparison_source"]["path"] = "release_artifacts/data/schema3_baseline.sqlite3"
        payload["comparison_source"]["reconstruction_path"] = (
            "release_artifacts/reconstruction/baseline"
        )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_primary_metadata(root: Path, version: str) -> None:
    entries = _inventory(root)
    manifest = {
        "artifact_type": "open_source_release",
        "project": "Operational Variance Investigation Toolkit",
        "version": version,
        "license": "MIT",
        "python_requires": ">=3.14",
        "synthetic_data_only": True,
        "ground_truth_policy": "separate optional spoiler archive",
        "xlsx_included": False,
        "files": entries,
    }
    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksums = _checksum_lines(root, exclude={"SHA256SUMS.txt"})
    (root / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")


def _stage_truth_archive(root: Path, truth_path: str | Path, version: str) -> None:
    source = Path(truth_path)
    if not source.is_file():
        raise DataValidationError(f"Restricted ground-truth artifact is missing: {source}")
    root.mkdir(parents=True)
    warning = (
        "# SPOILER / REVEAL WARNING\n\n"
        "STOP: this optional archive reveals the synthetic scenario answer key, including target "
        "identities, true mechanism mappings, affected records, and hidden physical timing. Open "
        "it only for developer validation or after completing the ordinary blind analysis.\n\n"
        "Do not place this file in an analyst-facing WMS database, standard-report directory, "
        "notebook input directory, or ordinary analysis workflow.\n"
    )
    (root / "SPOILER_WARNING.md").write_text(warning, encoding="utf-8")
    destination = root / "restricted_ground_truth.json"
    _copy_file(source, destination)
    truth = json.loads(destination.read_text(encoding="utf-8"))
    manifest = {
        "artifact_type": "optional_restricted_ground_truth",
        "version": version,
        "spoiler_warning": True,
        "intended_use": "developer validation or post-analysis comparison only",
        "ordinary_analysis_input": False,
        "matched_run_id": truth.get("run_id"),
        "files": _inventory(root),
    }
    (root / "GROUND_TRUTH_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "SHA256SUMS.txt").write_text(
        _checksum_lines(root, exclude={"SHA256SUMS.txt"}), encoding="utf-8"
    )


def _verify_primary_stage(root: Path, workspace: Path) -> None:
    artifacts = root / "release_artifacts"
    if any(
        token in path.name.lower()
        for path in artifacts.rglob("*")
        for token in ("ground_truth", "restricted_truth")
    ):
        raise DataValidationError("Primary release contains a restricted-truth path")
    for database in sorted((artifacts / "data").glob("*.sqlite3")):
        _verify_database_has_no_truth(database)
    for path in artifacts.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".sqlite", ".sqlite3", ".png", ".pdf"}:
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        for token in GENERATED_TRUTH_TOKENS:
            if token in content:
                raise DataValidationError(
                    f"Primary release generated artifact contains restricted token {token}: {path}"
                )
    workspace_marker = str(workspace).lower()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {
            ".sqlite",
            ".sqlite3",
            ".png",
            ".pdf",
        }:
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        generic_markers = ("c:\\users\\", "c:/users/") if artifacts in path.parents else ()
        if workspace_marker in content or any(marker in content for marker in generic_markers):
            raise DataValidationError(f"Primary release contains a machine-specific path: {path}")


def _verify_database_has_no_truth(path: Path) -> None:
    try:
        with closing(
            sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
        ) as connection:
            names = {
                str(row[0]).lower()
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                )
            }
            columns = set()
            for name in names:
                quoted = name.replace('"', '""')
                columns.update(
                    str(row[1]).lower()
                    for row in connection.execute(f'PRAGMA table_info("{quoted}")')
                )
    except sqlite3.Error as exc:
        raise DataValidationError(f"Cannot inspect release database {path}: {exc}") from exc
    leaked = FORBIDDEN_DATABASE_NAMES.intersection(names | columns)
    if leaked:
        raise DataValidationError(f"Release database contains truth fields: {sorted(leaked)}")


def _verify_archive_inventory(archive: Path, manifest_name: str, checksums_name: str) -> None:
    with zipfile.ZipFile(archive) as handle:
        names = handle.namelist()
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise DataValidationError(f"Release archive has an unsafe path: {archive}")
        matches = [name for name in names if name.endswith(f"/{manifest_name}")]
        checksum_matches = [name for name in names if name.endswith(f"/{checksums_name}")]
        if len(matches) != 1 or len(checksum_matches) != 1:
            raise DataValidationError(f"Release archive metadata is incomplete: {archive}")
        prefix = matches[0].removesuffix(manifest_name)
        expected: dict[str, str] = {}
        for line in handle.read(checksum_matches[0]).decode("utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            expected[prefix + relative] = digest
        for name, digest in expected.items():
            if name not in names:
                raise DataValidationError(f"Archive checksum names a missing file: {name}")
            if hashlib.sha256(handle.read(name)).hexdigest() != digest:
                raise DataValidationError(f"Archive member checksum mismatch: {name}")


def _write_deterministic_zip(source_root: Path, destination: Path) -> None:
    compression = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(destination, "w", compression=compression, compresslevel=9) as archive:
        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            relative = Path(source_root.name) / path.relative_to(source_root)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=compression, compresslevel=9)


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _checksum_lines(root: Path, *, exclude: set[str]) -> str:
    return "".join(
        f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in exclude
    )


def _copy_required_file(source: str | Path, destination: Path, label: str) -> None:
    source_path = Path(source)
    if not source_path.is_file():
        raise DataValidationError(f"Required {label} does not exist: {source_path}")
    _copy_file(source_path, destination)


def _copy_required_tree(source: str | Path, destination: Path, label: str) -> None:
    source_root = Path(source)
    if not source_root.is_dir() or not any(source_root.iterdir()):
        raise DataValidationError(f"Required {label} directory is missing or empty: {source_root}")
    for path in sorted(source_root.rglob("*")):
        if path.is_file() and not EXCLUDED_PARTS.intersection(path.relative_to(source_root).parts):
            _copy_file(path, destination / path.relative_to(source_root))


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
