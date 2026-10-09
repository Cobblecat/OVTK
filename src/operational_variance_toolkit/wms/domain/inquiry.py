"""Typed read models for schema-3 inquiry, export, and trace workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InquiryResult:
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    total_count: int


@dataclass(frozen=True, slots=True)
class ExportResult:
    path: Path
    row_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class TraceResult:
    identifier: str
    resolved_by: str
    commands: InquiryResult
    workflow: InquiryResult
    transactions: InquiryResult
    live_inventory: InquiryResult
    net_quantity_delta_cases: int
    conservation_status: str
