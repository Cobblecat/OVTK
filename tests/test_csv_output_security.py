from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from operational_variance_toolkit.wms.application.export import write_csv_atomic


@pytest.mark.parametrize(
    "column",
    [
        "item_id",
        "command_id",
        "source_reference",
        "Source Reference",
        "transaction_group",
        "snapshot_batch",
        "item_description",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "=1+1",
        "+1",
        "-1",
        "@SUM(1)",
        " \t=1",
        "\r\n+1",
        "\x00\x85\u2003=1",
        "\tordinary",
        "\nordinary",
    ],
)
def test_every_hazardous_string_column_is_literal_csv_data(
    column: str, value: str, tmp_path: Path
) -> None:
    results = [
        write_csv_atomic(
            tmp_path / f"copy-{index}.csv",
            (column, "quantity", "ordinary"),
            ((value, -3, 'café, "quoted"\nsecond line'),),
        )
        for index in range(2)
    ]
    with results[0].path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["'" + value, "-3", 'café, "quoted"\nsecond line']
    assert results[0].path.read_bytes() == results[1].path.read_bytes()
    assert results[0].sha256 == hashlib.sha256(results[0].path.read_bytes()).hexdigest()


def test_csv_preserves_ordinary_text_numbers_and_existing_literal_prefix(tmp_path: Path) -> None:
    values = ("ITEM-0001", "", "'=1", "café & tea", "a\nb", -3, 2.5, None)
    result = write_csv_atomic(tmp_path / "ordinary.csv", tuple(map(str, range(8))), (values,))
    with result.path.open(encoding="utf-8", newline="") as handle:
        assert list(csv.reader(handle))[1] == [
            "ITEM-0001",
            "",
            "'=1",
            "café & tea",
            "a\nb",
            "-3",
            "2.5",
            "",
        ]
