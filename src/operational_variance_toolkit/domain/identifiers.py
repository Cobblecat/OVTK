"""Deterministic and human-readable identifier helpers."""

from __future__ import annotations

import re
from typing import Final

from operational_variance_toolkit.errors import IdentityError

_IDENTIFIER_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")


def generate_identifier(prefix: str, value: int, *, width: int = 4) -> str:
    """Return a stable readable identifier like ``ITEM-0001``."""

    if not isinstance(prefix, str) or not prefix.strip():
        raise IdentityError("prefix must be a nonempty string")
    if not _IDENTIFIER_PREFIX_RE.fullmatch(prefix):
        raise IdentityError(
            "prefix must contain only uppercase letters, digits, underscores, or hyphens"
        )
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise IdentityError("value must be a positive integer")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise IdentityError("width must be a positive integer")

    return f"{prefix}-{value:0{width}d}"


def generate_code_identifier(prefix: str, code: str) -> str:
    """Return a stable code-based identifier such as ``ZONE-FRZ``."""

    if not isinstance(prefix, str) or not prefix.strip():
        raise IdentityError("prefix must be a nonempty string")
    if not isinstance(code, str) or not code.strip():
        raise IdentityError("code must be a nonempty string")
    if not _IDENTIFIER_PREFIX_RE.fullmatch(prefix):
        raise IdentityError(
            "prefix must contain only uppercase letters, digits, underscores, or hyphens"
        )

    return f"{prefix}-{code.upper()}"


def generate_identifier_sequence(
    prefix: str, count: int, *, start: int = 1, width: int = 4
) -> list[str]:
    """Return a sequence of stable identifiers for a single run."""

    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise IdentityError("count must be a nonnegative integer")
    if not isinstance(start, int) or isinstance(start, bool) or start <= 0:
        raise IdentityError("start must be a positive integer")

    return [
        generate_identifier(prefix, index, width=width) for index in range(start, start + count)
    ]
