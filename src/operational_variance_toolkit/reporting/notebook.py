"""Thin release notebook construction and clean-kernel execution."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOK_NAME = "operational_variance_investigation.ipynb"


def create_release_notebook(path: str | Path) -> Path:
    """Create the stable source notebook used by release and clean reproduction."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    notebook = nbformat.v4.new_notebook(
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.14"},
        }
    )
    notebook.cells = [
        nbformat.v4.new_markdown_cell(
            "# Inventory Variance Investigation\n\n"
            "**Synthetic data only.** This notebook uses a deterministic miniature WMS and "
            "contains no real employer records or proprietary system details."
        ),
        nbformat.v4.new_markdown_cell("## tl;dr"),
        nbformat.v4.new_code_cell(
            "import os\n"
            "from pathlib import Path\n\n"
            "from IPython.display import Image, Markdown, display\n\n"
            "from operational_variance_toolkit.reporting.frozen import (\n"
            "    load_frozen_statistics,\n"
            "    load_reconciliation_summary,\n"
            "    reporting_summary,\n"
            ")\n\n"
            "statistics = load_frozen_statistics(Path(os.environ['OVT_STATISTICS_DIR']))\n"
            "reconciliation = load_reconciliation_summary(\n"
            "    Path(os.environ['OVT_RECONSTRUCTION_DIR'])\n"
            ")\n"
            "reporting_dir = Path(os.environ['OVT_REPORTING_DIR'])\n"
            "summary = reporting_summary(statistics, reconciliation)\n\n"
            "display(Markdown(\n"
            "    f\"**Observed result.** {summary['target_selector']} had a crude \"\n"
            '    f"target-minus-peer short-line difference of "\n'
            "    f\"{summary['crude_risk_difference_pp']:.2f} percentage points. \"\n"
            '    f"After the frozen measured-exposure adjustment, the difference was "\n'
            "    f\"{summary['adjusted_risk_difference_pp']:.2f} points \"\n"
            "    f\"(95% interval {summary['adjusted_ci_lower_pp']:.2f} to \"\n"
            "    f\"{summary['adjusted_ci_upper_pp']:.2f}). The evidence does not support a \"\n"
            '    f"generalized individual-accuracy conclusion."\n'
            "))"
        ),
        nbformat.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "The operational question is whether a raw selector-level short signal survives "
            "comparison at a common measured work mix. The unit is an eligible pick line over the "
            "frozen simulation period. The package validates the Phase 5 manifest and checksums, "
            "then exposes accepted summary values. This notebook does not fit a model or redefine "
            "a metric.\n\n"
            "### Key Assumptions\n\n"
            "Assignment is observational. Recorded WMS confirmation time is not physical "
            "availability time. QA-adjustment proximity identifies candidates, not causal links."
        ),
        nbformat.v4.new_markdown_cell("## Data"),
        nbformat.v4.new_code_cell(
            "display(Markdown(\n"
            "    f\"Run `{summary['run_id']}` uses schema `{summary['schema_version']}` and \"\n"
            "    f\"contains **{summary['eligible_picks']:,} eligible picks**, \"\n"
            "    f\"**{summary['requested_cases']:,} requested cases**, \"\n"
            "    f\"**{summary['short_lines']} short lines**, and \"\n"
            "    f\"**{summary['short_cases']} short cases**. Source identity, analytical \"\n"
            '    f"grain, "\n'
            '    f"and frozen-output checks passed. Ordinary analysis loaded ground truth: "\n'
            "    f\"**{summary['ordinary_analysis_ground_truth_loaded']}**.\"\n"
            "))"
        ),
        nbformat.v4.new_markdown_cell("## Results\n\n### 1. Three-Way Reconciliation"),
        nbformat.v4.new_code_cell(
            "display(Markdown(\n"
            "    f\"All **{summary['reconciliation_rows']} locations** reconcile with \"\n"
            "    f\"**{summary['reconciliation_difference_rows']} difference rows**. \"\n"
            '    f"Transaction replay, live inventory, and closing snapshot each close at "\n'
            "    f\"**{summary['live_closing_cases']:,} cases**. Eventual recorded \"\n"
            '    f"agreement does "\n'
            '    f"not establish point-in-time physical availability."\n'
            "))"
        ),
        nbformat.v4.new_markdown_cell("### 2. Crude and Adjusted Selector Contrast"),
        nbformat.v4.new_code_cell(
            "display(Image(filename=str(reporting_dir / 'figures' / "
            "'selector_crude_adjusted.png')))"
        ),
        nbformat.v4.new_markdown_cell("### 3. Recorded Operational Context"),
        nbformat.v4.new_code_cell(
            "display(Image(filename=str(reporting_dir / 'figures' / "
            "'operational_context_short_rates.png')))\n"
            "display(Markdown(\n"
            '    f"Within 120 minutes of recorded confirmation, "\n'
            "    f\"{summary['replenishment_near_shorts']} of \"\n"
            "    f\"{summary['replenishment_near_picks']} picks were short; outside that \"\n"
            '    f"window, "\n'
            "    f\"{summary['replenishment_away_shorts']} of \"\n"
            "    f\"{summary['replenishment_away_picks']} were short. This is WMS context, not \"\n"
            '    f"an observation of physical delay."\n'
            "))"
        ),
        nbformat.v4.new_markdown_cell("### 4. QA and Adjustment Candidates"),
        nbformat.v4.new_code_cell(
            "display(Image(filename=str(reporting_dir / 'figures' / "
            "'qa_adjustment_candidates.png')))"
        ),
        nbformat.v4.new_markdown_cell("### 5. Sensitivity Checks"),
        nbformat.v4.new_code_cell(
            "display(Image(filename=str(reporting_dir / 'figures' / 'selector_sensitivity.png')))"
        ),
        nbformat.v4.new_markdown_cell("### 6. Hypothesis Evidence Matrix"),
        nbformat.v4.new_code_cell(
            "hypothesis_lines = ['| Hypothesis | Disposition | Evidence status |', "
            "'|---|---|---|']\n"
            "for row in statistics.tables['hypothesis_evidence.csv']:\n"
            "    hypothesis_lines.append(\n"
            "        f\"| {row['hypothesis_id']} | {row['disposition']} | "
            "{row['evidence_status']} |\"\n"
            "    )\n"
            "display(Markdown('\\n'.join(hypothesis_lines)))"
        ),
        nbformat.v4.new_markdown_cell("## Takeaways"),
        nbformat.v4.new_code_cell(
            "display(Markdown(\n"
            '    "1. **Investigate the process point first.** Observe replenishment "\n'
            '    "handoff in localized high-velocity chilled work and track eligible-pick "\n'
            '    "denominators.\\n"\n'
            '    "2. **Trace QA candidates without presuming cause.** Complete "\n'
            '    "disposition review "\n'
            '    "before changing controls.\\n"\n'
            '    "3. **Do not use raw selector totals for discipline or scoring.** The "\n'
            '    "primary adjusted contrast is small and imprecise, and the ITEM-0005 "\n'
            '    "sensitivity exposes "\n'
            '    "limited overlap."\n'
            "))"
        ),
    ]
    nbformat.validate(notebook)
    nbformat.write(notebook, destination)
    return destination


def execute_release_notebook(
    source_path: str | Path,
    output_path: str | Path,
    statistics_path: str | Path,
    reconstruction_path: str | Path,
    reporting_path: str | Path,
    *,
    working_directory: str | Path | None = None,
) -> Path:
    """Execute the release notebook top to bottom in a fresh Python kernel."""

    source = Path(source_path)
    destination = Path(output_path)
    notebook = nbformat.read(source, as_version=4)
    environment = {
        "OVT_STATISTICS_DIR": str(Path(statistics_path).resolve()),
        "OVT_RECONSTRUCTION_DIR": str(Path(reconstruction_path).resolve()),
        "OVT_REPORTING_DIR": str(Path(reporting_path).resolve()),
    }
    with _temporary_environment(environment):
        client = NotebookClient(
            notebook,
            timeout=300,
            kernel_name="python3",
            resources={"metadata": {"path": str(Path(working_directory or ".").resolve())}},
        )
        client.execute()
    nbformat.validate(notebook)
    destination.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, destination)
    return destination


@contextmanager
def _temporary_environment(values: dict[str, str]):
    original = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
