"""Application and user-resource path resolution for console sessions."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from operational_variance_toolkit.errors import DatabaseError

SAMPLE_RELATIVE_PATH = Path("sample-data") / "schema3_baseline.sqlite3"
SOURCE_SAMPLE_RELATIVE_PATH = Path("artifacts") / "data" / "schema3_baseline_accepted.sqlite3"


@dataclass(frozen=True, slots=True)
class ResourceResolver:
    """Resolve packaged resources independently from the process working directory."""

    application_root: Path

    @classmethod
    def discover(cls) -> ResourceResolver:
        if getattr(sys, "frozen", False):
            return cls(Path(sys.executable).resolve().parent)

        module_path = Path(__file__).resolve()
        for parent in module_path.parents:
            if (parent / "pyproject.toml").is_file():
                return cls(parent)
        return cls(module_path.parents[2])

    def sample_database(self) -> Path:
        candidates = (
            self.application_root / SAMPLE_RELATIVE_PATH,
            self.application_root / SOURCE_SAMPLE_RELATIVE_PATH,
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise DatabaseError(
            "Included sample WMS is unavailable. Use open <database> to select a schema-3 file."
        )

    def resolve_user_path(self, value: str | Path, working_directory: Path) -> Path:
        raw_value = str(value)
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {'"', "'"}:
            raw_value = raw_value[1:-1]
        path = Path(raw_value).expanduser()
        if not path.is_absolute():
            path = working_directory / path
        return path.resolve()

    def history_path(self) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data) / "OperationalVarianceToolkit"
        else:
            base = Path.home() / ".operational-variance-toolkit"
        return base / "console-history.jsonl"
