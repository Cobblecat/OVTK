"""Validation result objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One validation finding."""

    category: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Hard failures and warnings from dataset validation."""

    hard_failures: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.hard_failures
