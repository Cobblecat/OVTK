"""Manifest-selected analytical text decoding; WMS presentation CSV is separate."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from typing import Any, Literal

from operational_variance_toolkit.errors import AnalyticalFormatError

CSV_CODEC_V1 = "codec-v1"
CSV_FORMAT_VERSION = "2.0.0"
CSV_PREFIX = "OVTK1_"


def manifest_csv_codec(
    manifest: Mapping[str, Any],
    *,
    kind: Literal["reconstruction", "statistics"],
    reconstruction_versions: tuple[str, ...] = ("2.0.0",),
) -> str | None:
    """Recognize approved producer tuples before opening analytical CSV data.

    Producer versions describe computation. artifact_format_version describes
    serialization; new and raw artifacts cannot share that format version.
    """
    if not isinstance(manifest, Mapping):
        raise AnalyticalFormatError("Expected an analytical manifest object")
    if kind == "reconstruction":
        if not isinstance(manifest.get("reconstruction_version"), str):
            raise AnalyticalFormatError("Unsupported reconstruction analytical manifest")
        valid = (
            manifest.get("artifact_type") == "analysis_reconstruction"
            and manifest.get("reconstruction_version") in reconstruction_versions
            and manifest.get("reconstruction_version") in {"1.0.0", "2.0.0"}
        )
        source = manifest.get("source")
        expected_schema = {"1.0.0": "2.0.0", "2.0.0": "3.0.0"}.get(
            manifest.get("reconstruction_version")
        )
        valid = (
            valid and isinstance(source, dict) and source.get("schema_version") == expected_schema
        )
    elif kind == "statistics":
        valid = (
            manifest.get("artifact_type") == "frozen_statistical_analysis"
            and manifest.get("statistics_version") == "1.0.0"
            and manifest.get("analysis_contract_version") == "1.0.0"
        )
    else:
        valid = False
    if not valid:
        raise AnalyticalFormatError(f"Unsupported {kind} analytical manifest")
    if "csv_codec" not in manifest and "artifact_format_version" not in manifest:
        return None
    if (
        manifest.get("csv_codec") != CSV_CODEC_V1
        or manifest.get("artifact_format_version") != CSV_FORMAT_VERSION
    ):
        raise AnalyticalFormatError("Unsupported or contradictory analytical CSV format")
    return CSV_CODEC_V1


def decode_csv_text(value: str, codec_version: str | None) -> str:
    """Decode declared v1 text strictly; legacy text is never prefix-guessed."""
    if codec_version is None:
        return value
    if codec_version != CSV_CODEC_V1:
        raise AnalyticalFormatError("Unsupported analytical CSV codec")
    if not value.startswith(CSV_PREFIX):
        return value
    token = value[len(CSV_PREFIX) :]
    try:
        raw = base64.b64decode(token.encode("ascii"), altchars=b"-_", validate=True)
        decoded = raw.decode("utf-8", errors="strict")
        if base64.urlsafe_b64encode(raw).decode("ascii") != token:
            raise ValueError("Noncanonical encoding")
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise AnalyticalFormatError("Malformed or noncanonical codec-v1 text") from exc
    return decoded
