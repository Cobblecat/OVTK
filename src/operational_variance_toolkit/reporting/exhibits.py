"""Traceable static exhibits generated only from frozen Phase 5 outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from operational_variance_toolkit.reporting.frozen import FrozenStatistics

INK = "#20262D"
BLUE = "#356A8A"
GOLD = "#C38A21"
OLIVE = "#708249"
PINK = "#B75D78"
GRID = "#D9DEE3"
OPEN = "#EDF1F4"


@dataclass(frozen=True, slots=True)
class Exhibit:
    file_name: str
    title: str
    population: str
    denominator: str
    source: str
    claim_boundary: str


def build_exhibits(statistics: FrozenStatistics, output_path: str | Path) -> tuple[Exhibit, ...]:
    """Write the accepted release figures and exhibit evidence tables."""

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    exhibits = (
        _selector_exhibit(statistics, output),
        _operational_context_exhibit(statistics, output),
        _qa_exhibit(statistics, output),
        _sensitivity_exhibit(statistics, output),
    )
    _write_hypothesis_table(statistics, output / "hypothesis_evidence_matrix.csv")
    _write_catalog(exhibits, output / "exhibit_catalog.csv")
    (output / "exhibit_catalog.json").write_text(
        json.dumps([asdict(exhibit) for exhibit in exhibits], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return exhibits


def _selector_exhibit(statistics: FrozenStatistics, output: Path) -> Exhibit:
    row = statistics.tables["selector_adjusted.csv"][0]
    overall = statistics.one(
        "descriptive_metrics.csv", group_dimension="overall", group_value="all eligible picks"
    )
    eligible_picks = int(overall["eligible_picks"])
    crude = float(row["crude_risk_difference_pp"])
    adjusted = float(row["adjusted_risk_difference_pp"])
    lower = float(row["adjusted_ci_lower"]) * 100
    upper = float(row["adjusted_ci_upper"]) * 100
    figure, axis = _figure()
    axis.barh([1, 0], [crude, adjusted], color=[GOLD, BLUE], edgecolor=INK, linewidth=0.7)
    axis.errorbar(
        adjusted,
        0,
        xerr=[[adjusted - lower], [upper - adjusted]],
        fmt="none",
        color=INK,
        capsize=5,
        linewidth=1.4,
    )
    axis.axvline(0, color=INK, linewidth=0.8)
    axis.set_yticks([1, 0], ["Crude", "Adjusted"])
    axis.set_xlabel("Target-minus-peer short-line risk difference (percentage points)")
    axis.set_title("Selector contrast before and after measured exposure adjustment", loc="left")
    axis.text(
        0,
        -0.24,
        f"Population: {eligible_picks:,} eligible picks; adjusted interval uses "
        "trip-clustered uncertainty.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=INK,
    )
    _label_bars(axis, [crude, adjusted], [1, 0], suffix=" pp")
    _save(figure, output / "selector_crude_adjusted.png")
    return Exhibit(
        "selector_crude_adjusted.png",
        "Selector contrast before and after measured exposure adjustment",
        f"All {eligible_picks:,} eligible investigation picks",
        "Eligible pick lines; target selector versus all peers",
        "selector_adjusted.csv; selector_crude.csv",
        "Adjusted association is observational and does not establish causality.",
    )


def _operational_context_exhibit(statistics: FrozenStatistics, output: Path) -> Exhibit:
    rows = statistics.tables["replenishment_evidence.csv"]
    selected = [
        next(row for row in rows if row["exposure_group"] == label)
        for label in (
            "inside predefined condition",
            "outside predefined condition",
            "within 120 minutes",
            "outside 120 minutes",
        )
    ]
    labels = ["Inside condition", "Outside condition", "Within 120 min", "Outside 120 min"]
    rates = [float(row["short_line_rate"]) * 100 for row in selected]
    lowers = [float(row["ci_lower"]) * 100 for row in selected]
    uppers = [float(row["ci_upper"]) * 100 for row in selected]
    figure, axis = _figure(height=4.8)
    positions = list(range(len(labels)))
    axis.barh(
        positions,
        rates,
        color=[GOLD, OPEN, BLUE, OPEN],
        edgecolor=INK,
        linewidth=0.7,
    )
    axis.errorbar(
        rates,
        positions,
        xerr=[
            [rate - lower for rate, lower in zip(rates, lowers, strict=True)],
            [upper - rate for rate, upper in zip(rates, uppers, strict=True)],
        ],
        fmt="none",
        color=INK,
        capsize=4,
        linewidth=1.1,
    )
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Short lines per 100 eligible picks")
    axis.set_title("Recorded operational context and short-line rates", loc="left")
    axis.text(
        0,
        -0.24,
        "Recorded confirmation proximity is WMS context, not observed physical "
        "availability timing.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=INK,
    )
    _label_bars(axis, rates, positions, suffix="%")
    _save(figure, output / "operational_context_short_rates.png")
    return Exhibit(
        "operational_context_short_rates.png",
        "Recorded operational context and short-line rates",
        "Investigation picks with applicable recorded WMS context",
        "Eligible picks in each displayed context; Wilson 95% intervals",
        "replenishment_evidence.csv",
        "Confirmation time cannot reveal hidden physical availability.",
    )


def _qa_exhibit(statistics: FrozenStatistics, output: Path) -> Exhibit:
    row = statistics.one("qa_adjustment_evidence.csv", window_hours="4", same_location_required="1")
    labels = ["QA events", "Candidate QA events", "Generic corrections", "Negative control"]
    values = [
        int(row["qa_events"]),
        int(row["candidate_qa_events"]),
        int(row["generic_correction_pairs"]),
        int(row["negative_control_pairs"]),
    ]
    figure, axis = _figure()
    positions = list(range(len(labels)))
    axis.barh(positions, values, color=[OPEN, BLUE, OLIVE, PINK], edgecolor=INK, linewidth=0.7)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Event or candidate count")
    axis.set_title("QA observations and later adjustment candidates", loc="left")
    axis.text(
        0,
        -0.24,
        "Rule: same Item and location, QA before a negative adjustment, within four hours.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=INK,
    )
    _label_bars(axis, [float(value) for value in values], positions)
    _save(figure, output / "qa_adjustment_candidates.png")
    return Exhibit(
        "qa_adjustment_candidates.png",
        "QA observations and later adjustment candidates",
        f"{int(row['qa_events'])} investigation QA events",
        "QA events evaluated under the frozen four-hour same-location rule",
        "qa_adjustment_evidence.csv",
        "Temporal and quantity compatibility identifies candidates, not causal links.",
    )


def _sensitivity_exhibit(statistics: FrozenStatistics, output: Path) -> Exhibit:
    wanted = (
        ("primary", "Primary"),
        ("case_outcome", "Case outcome"),
        ("alternate_time_control", "No day control"),
        ("alternate_covariance", "HC3 covariance"),
        ("remove_high_leverage_item", "Remove ITEM-0005"),
    )
    rows = [statistics.one("sensitivity_results.csv", sensitivity_id=key) for key, _ in wanted]
    labels = [label for _, label in wanted]
    estimates = [float(row["estimate"]) * 100 for row in rows]
    lowers = [float(row["ci_lower"]) * 100 for row in rows]
    uppers = [float(row["ci_upper"]) * 100 for row in rows]
    positions = list(range(len(rows)))
    figure, axis = _figure(height=4.8)
    colors = [BLUE if row["conclusion_consistent"] == "1" else PINK for row in rows]
    axis.errorbar(
        estimates,
        positions,
        xerr=[
            [estimate - lower for estimate, lower in zip(estimates, lowers, strict=True)],
            [upper - estimate for estimate, upper in zip(estimates, uppers, strict=True)],
        ],
        fmt="o",
        color=INK,
        ecolor=INK,
        markeredgecolor=INK,
        markerfacecolor="white",
        capsize=4,
        linewidth=1.2,
    )
    for estimate, position, color in zip(estimates, positions, colors, strict=True):
        axis.scatter([estimate], [position], color=color, edgecolor=INK, zorder=3)
    axis.axvline(0, color=INK, linestyle="--", linewidth=0.9)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Target-minus-peer risk difference (percentage points)")
    axis.set_title("Selected sensitivity results", loc="left")
    axis.text(
        0,
        -0.24,
        "Intervals are specification-specific; ITEM-0005 removal invokes the frozen fallback.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=INK,
    )
    _save(figure, output / "selector_sensitivity.png")
    return Exhibit(
        "selector_sensitivity.png",
        "Selected sensitivity results",
        "Frozen selector specifications over eligible investigation picks",
        "Target-minus-peer risk difference; specification-specific 95% intervals",
        "sensitivity_results.csv",
        "Limited overlap makes the leave-ITEM-0005-out result unstable.",
    )


def _write_hypothesis_table(statistics: FrozenStatistics, path: Path) -> None:
    columns = (
        "hypothesis_id",
        "evidence_item",
        "evidence_status",
        "disposition",
        "limitation",
        "source_artifact_reference",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in statistics.tables["hypothesis_evidence.csv"]:
            writer.writerow({column: row[column] for column in columns})


def _write_catalog(exhibits: tuple[Exhibit, ...], path: Path) -> None:
    columns = tuple(Exhibit.__dataclass_fields__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for exhibit in exhibits:
            writer.writerow(asdict(exhibit))


def _figure(*, height: float = 4.3) -> tuple[Any, Any]:
    figure, axis = plt.subplots(figsize=(8.2, height), constrained_layout=True)
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")
    axis.grid(axis="x", color=GRID, linewidth=0.7)
    axis.set_axisbelow(True)
    axis.tick_params(colors=INK, labelsize=9)
    axis.xaxis.label.set_color(INK)
    axis.title.set_color(INK)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(INK)
        axis.spines[side].set_linewidth(0.8)
    return figure, axis


def _label_bars(axis: Any, values: list[float], positions: list[int], suffix: str = "") -> None:
    padding = max(values, default=1) * 0.02
    for value, position in zip(values, positions, strict=True):
        label = f"{value:.2f}{suffix}" if not value.is_integer() else f"{int(value)}{suffix}"
        axis.text(value + padding, position, label, va="center", fontsize=8.5, color=INK)


def _save(figure: Any, path: Path) -> None:
    figure.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "operational-variance-toolkit"},
    )
    plt.close(figure)
