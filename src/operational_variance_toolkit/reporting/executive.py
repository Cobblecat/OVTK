"""Executive and technical reporting from frozen, validated evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from operational_variance_toolkit.reporting.exhibits import Exhibit
from operational_variance_toolkit.reporting.frozen import FrozenStatistics
from operational_variance_toolkit.version import get_version

INK = colors.HexColor("#20262D")
BLUE = colors.HexColor("#356A8A")
GOLD = colors.HexColor("#C38A21")
PALE = colors.HexColor("#EDF1F4")
GRID = colors.HexColor("#D9DEE3")


def build_executive_report(
    statistics: FrozenStatistics,
    summary: dict[str, Any],
    exhibits: tuple[Exhibit, ...],
    output_path: str | Path,
) -> tuple[Path, Path, Path, Path]:
    """Build auditable Markdown, PDF, appendix, and claim-source notes."""

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    markdown_path = output / "executive_report.md"
    pdf_path = output / "executive_report.pdf"
    appendix_path = output / "technical_appendix.md"
    source_notes_path = output / "source_notes.json"
    markdown_path.write_text(_markdown(summary, statistics), encoding="utf-8")
    appendix_path.write_text(_appendix(summary, statistics, exhibits), encoding="utf-8")
    source_notes_path.write_text(
        json.dumps(_source_notes(summary, exhibits), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _pdf(pdf_path, summary, statistics, exhibits, output.parent / "figures")
    return markdown_path, pdf_path, appendix_path, source_notes_path


def _markdown(summary: dict[str, Any], statistics: FrozenStatistics) -> str:
    hypotheses = statistics.tables["hypothesis_evidence.csv"]
    lines = [
        "# Inventory Variance Investigation",
        "",
        "**Synthetic data only. This study does not use records from a real employer or WMS.**",
        "",
        "## Executive Summary",
        "",
        (
            f"**The crude selector signal does not persist at the same magnitude after measured "
            f"exposure adjustment.** {summary['target_selector']} recorded a "
            f"{_pct(summary['target_crude_rate'])} short-line rate versus "
            f"{_pct(summary['peer_crude_rate'])} for peers. The crude difference of "
            f"{summary['crude_risk_difference_pp']:.2f} percentage points fell to "
            f"{summary['adjusted_risk_difference_pp']:.2f} points after adjustment, with a 95% "
            f"interval from {summary['adjusted_ci_lower_pp']:.2f} to "
            f"{summary['adjusted_ci_upper_pp']:.2f} points."
        ),
        "",
        (
            "**The evidence points to localized operating context, not a generalized individual "
            "accuracy conclusion.** High-velocity chilled work, recorded replenishment context, "
            "and later QA/adjustment sequences are mechanism-consistent signals. They remain "
            "observational and do not prove a hidden physical cause."
        ),
        "",
        (
            f"**The recorded inventory closes exactly.** All {summary['reconciliation_rows']} "
            "locations agree across transaction replay, live inventory, and the closing snapshot; "
            "this eventual agreement does not establish point-in-time physical availability."
        ),
        "",
        "## The complaint is real, but the raw ranking is incomplete",
        "",
        (
            f"The investigation includes {summary['eligible_picks']:,} eligible picks, "
            f"{summary['requested_cases']:,} requested cases, {summary['short_lines']} short "
            f"lines, and {summary['short_cases']} short cases. The target selector handled "
            f"{summary['target_picks']} eligible picks and recorded "
            f"{summary['target_short_lines']} short lines. Raw totals therefore describe the "
            "complaint, but they do not separate selector identity from work mix and exposure."
        ),
        "",
        "![Selector crude and adjusted contrast](../figures/selector_crude_adjusted.png)",
        "",
        (
            "The adjusted interval crosses zero, and the proportional attenuation is "
            f"{summary['proportional_attenuation']:.1%}. This contradicts a generalized selector "
            "attribution; it does not prove that selector behavior never matters."
        ),
        "",
        "## Recorded operating context deserves the next process check",
        "",
        (
            f"Within 120 minutes of a recorded replenishment confirmation, "
            f"{summary['replenishment_near_shorts']} of "
            f"{summary['replenishment_near_picks']} eligible picks were short "
            f"({_pct(summary['replenishment_near_rate'])}). Outside that window, "
            f"{summary['replenishment_away_shorts']} of "
            f"{summary['replenishment_away_picks']} were short "
            f"({_pct(summary['replenishment_away_rate'])}). The WMS confirmation clock is only "
            "recorded context; it cannot show when product became physically available."
        ),
        "",
        "![Recorded operational context](../figures/operational_context_short_rates.png)",
        "",
        (
            f"The QA review found {summary['qa_candidates']} candidate events among "
            f"{summary['qa_events']} observations under the frozen four-hour, same-Item/location "
            f"rule, including {summary['qa_generic_corrections']} generic corrections. Timing and "
            "quantity compatibility make these useful review candidates, not causal links."
        ),
        "",
        "![QA adjustment candidates](../figures/qa_adjustment_candidates.png)",
        "",
        "## Recommended Next Steps",
        "",
        "1. **Audit replenishment handoff at the process point.** Operations and inventory-control "
        "owners should observe chilled, high-velocity work for two comparable operating weeks. "
        "Track eligible picks, short lines, recorded confirmations, later positive corrections, "
        "and recurrence by Item/location. Escalate if exposure-adjusted short rates do not improve "
        "or if observed handoff timing contradicts the recorded sequence.",
        "2. **Review QA-to-adjustment candidates as a control-design sample.** Inventory control "
        f"should trace the {summary['qa_candidates']} candidate observations without treating a "
        "temporal match as proof. "
        "The leading measure is documented disposition completeness; the lagging measure is the "
        "rate of later generic negative corrections after QA observations.",
        "3. **Retire raw selector totals as a performance conclusion.** Continue monitoring "
        "selector results only with eligible-pick denominators, operating-condition exposure, "
        "uncertainty, and minimum event thresholds. Do not use this synthetic study for labor "
        "discipline or individual scoring.",
        "",
        "## Further Questions",
        "",
        "- Does direct observation confirm a gap between recorded confirmation and physical "
        "availability in the affected operating condition?",
        "- Do candidate QA/adjustment sequences persist after disposition capture is improved?",
        "- Does the adjusted selector contrast remain small across additional deterministic runs "
        "with greater overlap and more short events?",
        "",
        "## Caveats and Assumptions",
        "",
        "- The data are synthetic and represent one facility-scale run.",
        "- Assignment is observational; adjustment does not establish causality.",
        f"- Only {summary['model_events']} short events support the primary model.",
        "- The leave-ITEM-0005-out sensitivity removes all exposed-peer condition events and uses "
        "the documented fallback, yielding an unstable "
        f"{summary['leave_item_out_estimate_pp']:.2f}-point residual.",
        "- Recorded WMS timestamps do not reveal hidden physical inventory timing.",
        "- Candidate QA relationships are not causal links.",
        "",
        "## Provenance",
        "",
        f"Run `{summary['run_id']}`; schema `{summary['schema_version']}`; frozen statistics "
        "validated PASS; ordinary analysis loaded ground truth: false. Exact claim-to-source "
        "references are in `source_notes.json` and the technical appendix.",
        "",
        "## Hypothesis Dispositions",
        "",
    ]
    lines.extend(
        f"- **{row['hypothesis_id']}:** {row['disposition']} ({row['evidence_status']})."
        for row in hypotheses
    )
    return "\n".join(lines) + "\n"


def _appendix(
    summary: dict[str, Any], statistics: FrozenStatistics, exhibits: tuple[Exhibit, ...]
) -> str:
    manifest = statistics.manifest
    lines = [
        "# Technical Appendix",
        "",
        "**Synthetic data only. Ordinary analysis is isolated from restricted ground truth.**",
        "",
        "## Source Identity",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Schema: `{summary['schema_version']}`",
        f"- Source SHA-256: `{manifest['source']['sha256']}`",
        f"- Analysis configuration SHA-256: `{manifest['analysis_configuration_sha256']}`",
        f"- Statistics version: `{manifest['statistics_version']}`",
        f"- Study period: `{summary['simulation_start_utc']}` to `{summary['simulation_end_utc']}`",
        "- Source, reconstruction, analytical grain, and reconciliation validation: PASS",
        "- Ordinary analysis loaded ground truth: false",
        "",
        "## Population and Model",
        "",
        f"- Unit: eligible pick line; observations: {summary['eligible_picks']:,}",
        f"- Requested-case exposure: {summary['requested_cases']:,}",
        f"- Events: {summary['model_events']}; trip clusters: {summary['model_clusters']}",
        f"- Model: `{summary['model_kind']}` with `{summary['covariance']}` uncertainty",
        "- Frozen covariates: target selector, operational condition, requested quantity, active "
        "replenishment at pick, high velocity, shift, and operating-day index",
        "",
        "## Three-Way Reconciliation",
        "",
        f"- Location rows: {summary['reconciliation_rows']}",
        f"- Reconstructed closing cases: {summary['reconstructed_closing_cases']}",
        f"- Live closing cases: {summary['live_closing_cases']}",
        f"- Closing snapshot cases: {summary['snapshot_closing_cases']}",
        f"- Difference rows: {summary['reconciliation_difference_rows']}",
        "",
        "## Exhibit Traceability",
        "",
    ]
    for exhibit in exhibits:
        lines.extend(
            [
                f"### {exhibit.title}",
                "",
                f"- File: `{exhibit.file_name}`",
                f"- Population: {exhibit.population}",
                f"- Denominator: {exhibit.denominator}",
                f"- Source: `{exhibit.source}`",
                f"- Claim boundary: {exhibit.claim_boundary}",
                "",
            ]
        )
    lines.extend(
        [
            "## Sensitivity Boundary",
            "",
            "The primary, short-case, no-day-index, and HC3 specifications retain the attenuated "
            "selector contrast. Removing ITEM-0005 eliminates all exposed-peer short events in the "
            "condition, destabilizes binomial-logit estimation, and invokes the frozen linear "
            "probability fallback. This is a limited-overlap warning, not evidence for an "
            "individual performance conclusion.",
            "",
            "## Restricted Truth Policy",
            "",
            "Restricted truth is not an input to this appendix, notebook, figures, WMS database, "
            "or ordinary analysis directory. It is published only in a separately named optional "
            "spoiler archive for developer validation or post-analysis comparison.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_notes(summary: dict[str, Any], exhibits: tuple[Exhibit, ...]) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "synthetic_data": True,
        "ordinary_analysis_ground_truth_loaded": False,
        "claims": [
            {
                "claim": "Crude selector contrast materially attenuates after measured adjustment",
                "source": "selector_adjusted.csv",
                "fields": [
                    "crude_risk_difference_pp",
                    "adjusted_risk_difference_pp",
                    "adjusted_ci_lower",
                    "adjusted_ci_upper",
                    "proportional_attenuation",
                ],
            },
            {
                "claim": "Recorded replenishment context is associated with short concentration",
                "source": "replenishment_evidence.csv",
                "boundary": "Recorded confirmation proximity is not physical delay.",
            },
            {
                "claim": "QA-adjustment relationships are candidates, not causal links",
                "source": "qa_adjustment_evidence.csv",
            },
            {
                "claim": "Replay, live master, and closing snapshot reconcile",
                "source": "inventory_reconciliation.csv",
            },
        ],
        "exhibits": [
            {field: getattr(exhibit, field) for field in Exhibit.__dataclass_fields__}
            for exhibit in exhibits
        ],
    }


def _pdf(
    path: Path,
    summary: dict[str, Any],
    statistics: FrozenStatistics,
    exhibits: tuple[Exhibit, ...],
    figure_path: Path,
) -> None:
    styles = _styles()
    document = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.65 * inch,
        title="Inventory Variance Investigation",
        author="Operational Variance Investigation Toolkit",
        subject="Synthetic-data executive investigation report",
    )
    story: list[Any] = [
        Paragraph("Inventory Variance Investigation", styles["Title"]),
        Paragraph(
            f"Synthetic grocery-distribution WMS | Release {get_version()}", styles["Subtitle"]
        ),
        Spacer(1, 0.18 * inch),
        Paragraph(
            "SYNTHETIC DATA ONLY. This study contains no real employer records, names, "
            "screenshots, or proprietary WMS details.",
            styles["Notice"],
        ),
        Spacer(1, 0.18 * inch),
        Paragraph("Executive Summary", styles["H1"]),
        Paragraph(
            f"<b>The raw selector signal is not a sufficient performance conclusion.</b> "
            f"The crude target-minus-peer short-line difference was "
            f"{summary['crude_risk_difference_pp']:.2f} percentage points. After the frozen "
            f"measured-exposure adjustment, it was {summary['adjusted_risk_difference_pp']:.2f} "
            f"points (95% interval {summary['adjusted_ci_lower_pp']:.2f} to "
            f"{summary['adjusted_ci_upper_pp']:.2f}), a "
            f"{summary['proportional_attenuation']:.1%} attenuation.",
            styles["Body"],
        ),
        Paragraph(
            "<b>The strongest ordinary-WMS evidence is localized and process-oriented.</b> "
            "High-velocity chilled work, recorded replenishment context, and later QA/adjustment "
            "sequences are mechanism-consistent. They do not establish a hidden physical cause.",
            styles["Body"],
        ),
        Paragraph(
            f"<b>Recorded inventory closes cleanly.</b> All {summary['reconciliation_rows']} "
            "locations agree across transaction replay, the live inventory master, and the closing "
            "snapshot. Eventual agreement does not prove point-in-time availability.",
            styles["Body"],
        ),
        Spacer(1, 0.1 * inch),
        _metrics_table(summary, styles),
        PageBreak(),
        Paragraph("The complaint is real, but the raw ranking is incomplete", styles["H1"]),
        Paragraph(
            f"The investigation contains {summary['eligible_picks']:,} eligible picks and "
            f"{summary['short_lines']} short lines across {summary['model_clusters']} trips. "
            f"{escape(str(summary['target_selector']))} handled "
            f"{summary['target_picks']} picks and "
            f"{summary['target_short_lines']} short lines. Denominators and work-mix exposure are "
            "therefore essential to interpretation.",
            styles["Body"],
        ),
        _report_image(figure_path / exhibits[0].file_name, exhibits[0], styles),
        Paragraph(
            "The adjusted interval crosses zero. The result contradicts a generalized selector "
            "attribution, but it does not prove that selector behavior is irrelevant in every "
            "setting.",
            styles["Body"],
        ),
        PageBreak(),
        Paragraph("Recorded operating context deserves the next process check", styles["H1"]),
        Paragraph(
            f"Within 120 minutes of recorded confirmation, "
            f"{summary['replenishment_near_shorts']} of "
            f"{summary['replenishment_near_picks']} picks were short "
            f"({_pct(summary['replenishment_near_rate'])}); outside that window, "
            f"{summary['replenishment_away_shorts']} of "
            f"{summary['replenishment_away_picks']} were short "
            f"({_pct(summary['replenishment_away_rate'])}). These are recorded WMS relationships, "
            "not observations of physical delay.",
            styles["Body"],
        ),
        _report_image(figure_path / exhibits[1].file_name, exhibits[1], styles),
        _report_image(figure_path / exhibits[2].file_name, exhibits[2], styles),
        PageBreak(),
        Paragraph("Sensitivity narrows the claim", styles["H1"]),
        _report_image(figure_path / exhibits[3].file_name, exhibits[3], styles),
        Paragraph(
            "Most prespecified alternatives retain a small adjusted contrast. Removing ITEM-0005 "
            "eliminates every exposed-peer condition short event and forces the frozen fallback, "
            "producing an unstable "
            f"{summary['leave_item_out_estimate_pp']:.2f}-point residual. That overlap limitation "
            "is material and "
            "precludes an individual-fault conclusion.",
            styles["Body"],
        ),
        Paragraph("Recommended Next Steps", styles["H1"]),
        _recommendation_table(styles),
        PageBreak(),
        Paragraph("Hypothesis Evidence", styles["H1"]),
        _hypothesis_table(statistics, styles),
        Paragraph("Further Questions", styles["H1"]),
        Paragraph(
            "1. Does direct observation confirm a replenishment handoff gap in the localized "
            "condition?<br/>2. Do QA/adjustment candidates persist after disposition capture is "
            "improved?<br/>3. Does the adjusted contrast remain small in additional runs with "
            "greater overlap and more events?",
            styles["Body"],
        ),
        Paragraph("Caveats and Assumptions", styles["H1"]),
        Paragraph(
            "The data are synthetic and represent one facility-scale run. Assignment is "
            f"observational. Only {summary['model_events']} short events support the primary "
            "model. WMS confirmation time "
            "does not reveal hidden physical timing. QA/adjustment matches are candidates. "
            "Trip-clustered uncertainty does not remove all item/location dependence.",
            styles["Body"],
        ),
        Paragraph("Technical Provenance", styles["H1"]),
        Paragraph(
            f"Run {escape(str(summary['run_id']))}; "
            f"schema {escape(str(summary['schema_version']))}; source SHA-256 "
            f"{escape(str(statistics.manifest['source']['sha256']))}; statistics version "
            f"{escape(str(statistics.manifest['statistics_version']))}. "
            "Source identity, reconstruction "
            "identity, analytical grain, and reconciliation validation passed. Ordinary analysis "
            "loaded ground truth: false.",
            styles["Small"],
        ),
    ]
    document.build(story, onFirstPage=_page, onLaterPages=_page)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=7,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=BLUE,
        ),
        "Notice": ParagraphStyle(
            "Notice",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=INK,
            backColor=colors.HexColor("#FFF3D6"),
            borderColor=GOLD,
            borderWidth=0.8,
            borderPadding=7,
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=7,
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=5,
            spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13.2,
            textColor=INK,
            spaceAfter=8,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK,
            spaceAfter=4,
        ),
        "Caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "Cell": ParagraphStyle(
            "Cell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.7,
            leading=10,
            textColor=INK,
        ),
        "CellHead": ParagraphStyle(
            "CellHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.7,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def _metrics_table(summary: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        ["Eligible picks", "Short lines", "Crude difference", "Adjusted difference"],
        [
            f"{summary['eligible_picks']:,}",
            str(summary["short_lines"]),
            f"{summary['crude_risk_difference_pp']:.2f} pp",
            f"{summary['adjusted_risk_difference_pp']:.2f} pp",
        ],
    ]
    table = Table(data, colWidths=[1.55 * inch] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, 1), PALE),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _report_image(path: Path, exhibit: Exhibit, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    return KeepTogether(
        [
            Image(str(path), width=6.8 * inch, height=3.7 * inch, kind="proportional"),
            Paragraph(
                escape(
                    f"Population: {exhibit.population}. Denominator: {exhibit.denominator}. "
                    f"Source: {exhibit.source}. {exhibit.claim_boundary}"
                ),
                styles["Caption"],
            ),
        ]
    )


def _recommendation_table(styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["Process point", "Owner and window", "Measures and decision rule"],
        [
            "Chilled replenishment handoff",
            "Operations + inventory control; two comparable operating weeks",
            "Eligible picks, shorts, confirmations, later positive corrections. Escalate if "
            "exposure-adjusted rates do not improve or observation contradicts recorded sequence.",
        ],
        [
            "QA disposition and adjustment trace",
            "Inventory control; complete candidate review cycle",
            "Disposition completeness and generic negative corrections after QA. Expand controls "
            "only if candidate recurrence remains above the observed baseline.",
        ],
        [
            "Selector monitoring",
            "Operations analytics; ongoing with minimum event threshold",
            "Exposure-adjusted rate and interval. No raw-total ranking, discipline, or "
            "labor score.",
        ],
    ]
    rendered = [
        [Paragraph(value, styles["CellHead"] if index == 0 else styles["Cell"]) for value in row]
        for index, row in enumerate(rows)
    ]
    table = Table(rendered, colWidths=[1.55 * inch, 2.1 * inch, 3.05 * inch], repeatRows=1)
    table.setStyle(_table_style())
    return table


def _hypothesis_table(statistics: FrozenStatistics, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [["ID", "Disposition", "Boundary"]]
    rows.extend(
        [row["hypothesis_id"], row["disposition"], row["limitation"]]
        for row in statistics.tables["hypothesis_evidence.csv"]
    )
    rendered = [
        [
            Paragraph(escape(str(value)), styles["CellHead"] if index == 0 else styles["Cell"])
            for value in row
        ]
        for index, row in enumerate(rows)
    ]
    table = Table(rendered, colWidths=[0.35 * inch, 3.15 * inch, 3.2 * inch], repeatRows=1)
    table.setStyle(_table_style())
    return table


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, GRID),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _page(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(GRID)
    canvas.line(0.7 * inch, 0.48 * inch, 7.8 * inch, 0.48 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK)
    canvas.drawString(
        0.7 * inch,
        0.31 * inch,
        "Operational Variance Investigation Toolkit | Synthetic data",
    )
    canvas.drawRightString(7.8 * inch, 0.31 * inch, f"Page {document.page}")
    canvas.restoreState()


def _pct(value: float) -> str:
    return f"{value:.2%}"
