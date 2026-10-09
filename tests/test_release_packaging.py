import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from operational_variance_toolkit.application.release import package_release
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


@pytest.fixture
def release_fixture(tmp_path: Path) -> dict[str, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for relative in SOURCE_FILES:
        (workspace / relative).write_text("synthetic release fixture\n", encoding="utf-8")
    for directory in SOURCE_DIRECTORIES:
        path = workspace / directory / "fixture.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")

    databases = []
    for name in ("baseline.sqlite3", "investigation.sqlite3"):
        path = tmp_path / name
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE inventory_master (location_id TEXT PRIMARY KEY)")
        databases.append(path)

    artifact_trees = []
    for name in (
        "baseline_reconstruction",
        "investigation_reconstruction",
        "statistics",
        "reports",
        "reporting",
    ):
        path = tmp_path / name
        path.mkdir()
        (path / "artifact.txt").write_text("analyst-facing synthetic artifact\n", encoding="utf-8")
        artifact_trees.append(path)
    (artifact_trees[2] / "analysis_manifest.json").write_text(
        json.dumps({"source": {"path": "original.sqlite3", "reconstruction_path": "original"}}),
        encoding="utf-8",
    )

    truth = tmp_path / "truth.json"
    truth.write_text(
        json.dumps({"run_id": "fixture-run", "true_root_cause": "fixture"}), encoding="utf-8"
    )
    return {
        "workspace": workspace,
        "output": tmp_path / "release",
        "baseline": databases[0],
        "investigation": databases[1],
        "baseline_reconstruction": artifact_trees[0],
        "investigation_reconstruction": artifact_trees[1],
        "statistics": artifact_trees[2],
        "reports": artifact_trees[3],
        "reporting": artifact_trees[4],
        "truth": truth,
    }


def _package(paths: dict[str, Path], output: Path | None = None):
    return package_release(
        paths["workspace"],
        output or paths["output"],
        paths["baseline"],
        paths["investigation"],
        paths["baseline_reconstruction"],
        paths["investigation_reconstruction"],
        paths["statistics"],
        paths["reports"],
        paths["reporting"],
        paths["truth"],
    )


def test_release_creates_separate_deterministic_archives_and_metadata(
    release_fixture: dict[str, Path],
) -> None:
    first = _package(release_fixture)
    first_source = first.source_archive_path.read_bytes()
    first_truth = first.truth_archive_path.read_bytes()
    second = _package(release_fixture, release_fixture["output"].parent / "release-second")

    assert first_source == second.source_archive_path.read_bytes()
    assert first_truth == second.truth_archive_path.read_bytes()
    assert first.source_file_count > 0
    assert first.truth_file_count == 4
    with zipfile.ZipFile(first.source_archive_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(
            archive.read(next(name for name in names if name.endswith("RELEASE_MANIFEST.json")))
        )
        assert manifest["license"] == "MIT"
        assert manifest["version"] == get_version()
        assert not any("truth" in name.lower() for name in names)
    with zipfile.ZipFile(first.truth_archive_path) as archive:
        names = set(archive.namelist())
        assert any(name.endswith("SPOILER_WARNING.md") for name in names)
        assert any(name.endswith("restricted_ground_truth.json") for name in names)
    assert first.source_archive_sha256 == hashlib.sha256(first_source).hexdigest()
    assert first.source_checksum_path.read_text(encoding="utf-8").startswith(
        first.source_archive_sha256
    )
    assert first.combined_checksum_path.read_text(encoding="utf-8").count("\n") == 2


def test_release_refuses_to_overwrite_existing_outputs(release_fixture: dict[str, Path]) -> None:
    _package(release_fixture)
    with pytest.raises(OutputExistsError):
        _package(release_fixture)


def test_release_rejects_truth_leakage_in_primary_artifacts(
    release_fixture: dict[str, Path],
) -> None:
    (release_fixture["reports"] / "leak.txt").write_text("true_root_cause", encoding="utf-8")
    with pytest.raises(DataValidationError, match="restricted token"):
        _package(release_fixture)


def test_release_rejects_truth_fields_in_primary_database(release_fixture: dict[str, Path]) -> None:
    with sqlite3.connect(release_fixture["baseline"]) as connection:
        connection.execute("CREATE TABLE ground_truth (value TEXT)")
    with pytest.raises(DataValidationError, match="truth fields"):
        _package(release_fixture)
