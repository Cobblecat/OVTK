from __future__ import annotations

import base64
import json

import pytest

from operational_variance_toolkit.errors import AnalyticalFormatError
from operational_variance_toolkit.storage.csv_codec import (
    CSV_PREFIX,
    decode_csv_text,
    manifest_csv_codec,
)


def _manifest():
    return {
        "artifact_type": "analysis_reconstruction",
        "reconstruction_version": "2.0.0",
        "source": {"schema_version": "3.0.0"},
    }


@pytest.mark.parametrize(
    "text",
    [
        "",
        "ordinary",
        "=1",
        "'=1",
        "\t+formula",
        "OVTK1_",
        "OVTK1_Zm9v",
        "漢字 café 😀",
        "\x00\x1b\r\n\t\x7f\x80\x9f",
    ],
)
def test_declared_strict_decode_round_trip_and_legacy_prefix_is_raw(text):
    token = CSV_PREFIX + base64.urlsafe_b64encode(text.encode()).decode()
    assert decode_csv_text(token, "codec-v1") == text
    assert decode_csv_text(token, None) == token
    assert decode_csv_text(text, None) == text
    if not text.startswith(CSV_PREFIX):
        assert decode_csv_text(text, "codec-v1") == text


@pytest.mark.parametrize(
    "token", ["Zg", "Zh==", "Zg===", "Zg==\n", "////", "_w==", "Zg==junk", "é", "?", "Zm 9v"]
)
def test_noncanonical_or_invalid_tokens_fail_closed(token):
    with pytest.raises(AnalyticalFormatError):
        decode_csv_text(CSV_PREFIX + token, "codec-v1")


def test_manifest_discriminator_and_no_prefix_guessing():
    manifest = _manifest()
    assert manifest_csv_codec(manifest, kind="reconstruction") is None
    manifest.update(csv_codec="codec-v1", artifact_format_version="2.0.0")
    assert manifest_csv_codec(manifest, kind="reconstruction") == "codec-v1"
    assert json.loads(json.dumps(manifest)) == manifest


@pytest.mark.parametrize(
    "change",
    [
        {"csv_codec": "codec-v1"},
        {"artifact_format_version": "2.0.0"},
        {"csv_codec": "codec-v2", "artifact_format_version": "2.0.0"},
        {"csv_codec": None},
        {"reconstruction_version": []},
        {"reconstruction_version": "9.0.0"},
        {"source": {"schema_version": "3.1.0"}},
        {"artifact_type": "other"},
    ],
)
def test_unsupported_manifests_are_controlled_nonpass(change):
    with pytest.raises(AnalyticalFormatError):
        manifest_csv_codec(_manifest() | change, kind="reconstruction")


def test_legacy_tuple_does_not_broaden_workflow_routes():
    legacy = _manifest() | {
        "reconstruction_version": "1.0.0",
        "source": {"schema_version": "2.0.0"},
    }
    with pytest.raises(AnalyticalFormatError):
        manifest_csv_codec(legacy, kind="reconstruction")
    assert (
        manifest_csv_codec(legacy, kind="reconstruction", reconstruction_versions=("1.0.0",))
        is None
    )
