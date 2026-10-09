from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from operational_variance_toolkit.application.wms_generation import generate_wms_baseline
from operational_variance_toolkit.wms.application.initialize import initialize_wms_foundation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_CONFIG = PROJECT_ROOT / "configs" / "baseline.toml"


@pytest.fixture(scope="session")
def baseline_config_path() -> Path:
    return BASELINE_CONFIG


@pytest.fixture(scope="session")
def console_wms_path(baseline_config_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("console-wms") / "schema3_console.sqlite3"
    initialize_wms_foundation(
        baseline_config_path,
        path,
        generated_at_utc=datetime(2026, 5, 4, 7, 0, tzinfo=UTC),
    )
    return path


@pytest.fixture(scope="session")
def phase2_wms_path(baseline_config_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("phase2-wms") / "phase2_baseline.sqlite3"
    generate_wms_baseline(
        baseline_config_path,
        path,
        generated_at_utc=datetime(2026, 8, 2, 12, tzinfo=UTC),
    )
    return path


@pytest.fixture()
def write_phase1_config(tmp_path: Path) -> Callable[[Path], Path]:
    def _write_phase1_config(database_path: Path) -> Path:
        config_path = tmp_path / f"{database_path.stem}.toml"
        config_path.write_text(
            f"""
[run]
scenario_name = "baseline"
scenario_version = "0.1.0"
seed = 20260801
start_local = "2026-05-04T03:00:00"
end_local = "2026-05-14T15:00:00"
facility_timezone = "America/New_York"

[facility]
facility_id = "FAC-001"
name = "Synthetic Grocery Distribution Center"

[dimensions]
zone_count = 3
item_count = 96
selector_count = 18
replenisher_count = 7
qa_operator_count = 3
shift_count = 10

[storage]
database_path = "{database_path.as_posix()}"
ground_truth_directory = "{(tmp_path / "restricted_ground_truth").as_posix()}"
export_directory = "{(tmp_path / "exports").as_posix()}"
""",
            encoding="utf-8",
        )
        return config_path

    return _write_phase1_config


@pytest.fixture(scope="session")
def run_tool() -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "operational_variance_toolkit", *args],
            capture_output=True,
            check=False,
            cwd=PROJECT_ROOT,
            text=True,
        )

    return _run_tool
