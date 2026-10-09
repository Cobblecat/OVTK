# Operational Variance Investigation Toolkit 0.1.0

Version `0.1.0` is the initial local open-source portfolio release. It is licensed under the MIT
License and requires Python `>=3.14`. The release was developed and acceptance-tested with Python
3.14.

## Included

- Deterministic baseline and investigation generation for a synthetic grocery-distribution WMS.
- Schema-3 SQLite examples, standard WMS reports, independent reconstruction, and frozen
  statistical outputs.
- A thin executed notebook, four traceable figures, exhibit tables, an executive PDF, and a
  technical appendix.
- Source code, tests, configuration, documentation, dependency lockfile, release manifest,
  SHA-256 checksums, and clean reproduction instructions.

## Finding Boundary

The accepted investigation contains 1,133 eligible picks and 33 short lines. The crude target-minus-
peer selector difference is 9.9638 percentage points. It attenuates to 0.8477 points after the frozen
measured-exposure adjustment, with a 95% interval from -1.1213 to 2.8167 points. The evidence does
not support a generalized selector-accuracy conclusion. Localized operating context and QA/
adjustment sequences are mechanism-consistent, not causal proof.

These figures trace to `release_artifacts/statistics/selector_adjusted.csv` and
`release_artifacts/statistics/descriptive_metrics.csv` in the source archive.

## Restricted Ground Truth

The primary source archive contains no restricted ground-truth artifact, hidden physical timing,
true mechanism mapping, or run-specific answer key. Those materials are available only in the
separately named optional ground-truth ZIP, which carries a prominent spoiler warning, its own
manifest, and its own SHA-256 checksums. It is intended only for developer validation or deliberate
post-analysis comparison.

## Deliberate Limits

- Synthetic single-run evidence cannot establish real-world causality.
- Recorded WMS confirmation time does not reveal physical availability timing.
- The primary model has 33 short events; one leave-Item-out sensitivity exposes limited overlap.
- No XLSX packet, GUI, production deployment, pallet lifecycle, or live-system integration is
  included.
- Compatibility below Python 3.14 is not claimed.

See `docs/28_RELEASE_AND_REPRODUCTION_GUIDE.md` for the complete local workflow.
