# Project Status

**Project:** Operational Variance Investigation Toolkit
**Status:** Release 0.2.0 Phase 3 engineering complete; Phase 4 pending
**Current phase:** Release 0.2.0 - Phase 3 protected sandbox lifecycle
**Next checkpoint:** Phase 4 CSV usefulness review at Owner Checkpoint B
**Data policy:** Synthetic data only

## Completed legacy capabilities

The current repository has completed and verified:

- Phase 0 project foundation, configuration, CLI, errors, Pytest, Ruff, and deterministic primitives.
- Phase 1 relational foundation, warehouse master data, opening inventory, schema lifecycle, and CLI workflows.
- Phase 2 normal transaction generation for trips, picks, replenishments, QA events, adjustments, system events, and closing snapshots.
- Phase 3 controlled failure patterns:
  - replenishment timing gap;
  - QA damage masking; and
  - selector false lead through differential exposure.
- A separate restricted JSON ground-truth artifact.
- Phase 4 read-only reconstruction and deterministic exports:
  - `inventory_event_ledger.csv`;
  - `inventory_reconciliation.csv`;
  - `pick_context.csv`;
  - `replenishment_context.csv`;
  - `qa_adjustment_context.csv`;
  - `selector_exposure.csv`; and
  - `analysis_manifest.json`.
- Legacy Phase 4 acceptance with:
  - zero closing-snapshot reconciliation differences;
  - byte-for-byte source preservation;
  - no hidden-truth leakage;
  - deterministic reconstruction; and
  - 106 passing tests at the recorded checkpoint.

## Material domain correction addressed

The legacy implementation was analytically coherent but did not behave like a
credible miniature WMS in several core respects. Phase 4A corrects these issues
in schema 3 while retaining schema-1/2 compatibility paths:

- there is no authoritative live `inventory_master` file keyed by warehouse location;
- current recorded inventory primarily exists in simulator state and opening/closing snapshots;
- item case dimensions are not retained even though cube is modeled;
- location profiles contain fixed case capacity despite item-dependent case size;
- the current handling-unit model adds lifecycle concepts without a complete pallet-tracking implementation;
- inventory-affecting actions do not yet update a persisted live inventory file and immutable audit file as one atomic WMS transaction;
- controlled failures are implemented as overlays inside the operations generator rather than as independent scenario drivers using ordinary WMS commands; and
- standard WMS inquiry and scheduled-report surfaces are incomplete.

## Approved corrected model

The corrected architecture requires:

1. An independent mini-WMS that functions without scenario modules.
2. A stable `item_master` containing case dimensions and system-calculated cube.
3. A stable `location_master` containing physical location metadata and pallet capacity, but no live assignment, current quantity, fixed case capacity, or equipment-area field.
4. A live mutable `inventory_master` keyed by `location_id` and containing current item assignment, recorded quantity, code date, replenishment controls, and last-change references.
5. An immutable `inventory_transaction` audit file for every recorded quantity change.
6. Atomic WMS command services for picks, transfers, replenishment confirmation, adjustments, QA recording, and snapshots.
7. A separate physical warehouse simulator.
8. External baseline and investigation scenario drivers that submit ordinary WMS commands and cannot write WMS storage directly.
9. Standard reports and SQL views derived from the same operational tables available to ad hoc analysts.
10. Three-way reconciliation:

```text
opening recorded inventory
+ immutable inventory transaction replay
= reconstructed closing inventory
= live inventory_master
= scheduled closing snapshot
```

## Phase 4A objective

> Replace the analytics-first operational core with a coherent schema-version `3.0.0` mini-WMS while preserving deterministic generation, the three investigation patterns, restricted ground truth, source-preserving reconstruction, and all useful existing capabilities.

## Immediate work boundary

Phases 4A, 5, and 6 passed their full technical and owner acceptance gates. The
truth-blind statistical findings are frozen, and release 0.1.0 adds the executed
notebook, traceable exhibits, executive report, technical appendix, SQL/user
guides, MIT license, and separate leakage-checked source and optional truth ZIPs.

Phase 4A Slice 0 from `docs/18_PHASE_4A_WMS_OPERATIONAL_FIDELITY_PLAN.md` is complete:

- preserve the legacy checkpoint;
- install and reconcile the replacement specifications;
- audit current modules and tests against the new architecture;
- produce a concrete code migration inventory; and
- retain a green legacy baseline.

Slice 0 created `docs/24_PHASE_4A_CURRENT_CODE_AUDIT.md`.

Slice 0 review decisions are now recorded:

- `wms-remediation-safety-checkpoint` is the single canonical preservation tag;
- docs 10 and 14 are restored as historical traceability and active statistical governance, respectively;
- schema-3 WMS run metadata contains neutral provenance only;
- `init-wms` is canonical for schema 3 and `init-db` remains a labeled legacy schema-1/2 path;
- standard WMS reconciliation is live master versus selected snapshot, while full transaction replay remains external analysis.

## Phase 4A Slice 0 safety checkpoint

The mixed Phase 1-4 implementation plus WMS remediation documentation checkpoint is preserved at:

- active branch: `refactor/wms-operational-fidelity`;
- safety branch: `rescue/phase4-remediation-mixed-checkpoint`;
- safety tag: `wms-remediation-safety-checkpoint`;
- checkpoint commit: `6f6b49a`.

## Phase 4A final acceptance

Approved: Item master, PICK/RESERVE location scope, normalized transaction
trace, and standard report set. Owner-facing report terminology is
implemented without changing canonical technical fields. The inventory master
was approved after one bounded deterministic realism calibration.

Definitive safe artifacts were generated at new ignored paths:

- `artifacts/data/schema3_baseline_accepted.sqlite3`;
- `artifacts/data/schema3_investigation_accepted.sqlite3`;
- `artifacts/restricted_ground_truth/schema3_investigation_accepted.json`;
- `artifacts/reports/schema3_baseline_accepted`; and
- `artifacts/analysis/schema3_baseline_accepted` and
  `artifacts/analysis/schema3_investigation_accepted`.

Both databases remain schema `3.0.0` with 96 items, 96 pick locations, 96
reserve locations, and 192 live inventory rows. Baseline closes with 14 empty
reserves (14.6%), 4 assigned zero-quantity picks, 3 near-maximum picks, 82
stocked reserves, and 3,057 reserve cases. Investigation closes with 18 empty
reserves (18.8%), 5 assigned zero-quantity picks, 3 near-maximum picks, 78
stocked reserves, and 2,764 reserve cases.

Baseline operational counts are 120 trips, 969 picks, 59 replenishments, 8 QA
events, 4 adjustments, 4 system events, 1,091 immutable inventory transaction
lines, and 384 snapshot lines. Investigation counts are 140 trips, 1,133 picks,
78 replenishments, 18 QA events, 22 adjustments, 4 system events, 1,307 audit
lines, and 384 snapshot lines. Physical and recorded closing quantities are
equal in both artifacts.

All 12 standard baseline reports passed. Row counts are: inventory by location
192, inventory by item 96, location profile 192, empty locations 18, code-date
inventory 174, replenishment needs 12, open replenishment tasks 0, transaction
inquiry 1,091, adjustment history 4, QA activity 8, recorded inventory snapshot
192, and live-versus-snapshot reconciliation 192. Empty-location output contains
only `Unassigned Empty Reserve` and `Assigned Zero-Quantity Pick Slot`.

Investigation calibration remains unchanged: 28 Pattern A shorts, 2 delayed
physical completions, 8 recovery adjustments, 10 Pattern B QA events with 10
generic corrections, and 28/229 Pattern C target trips/picks. Scenario check
passed with no failures or warnings.

Baseline reconstruction produced 1,283 ledger rows; investigation produced
1,499. Both produced 192 reconciliation rows with zero replay/live/snapshot
differences and preserved source bytes. Source SHA-256 values are baseline
`4225d8472887037b73d8d50f0eb3756961f1bf46939522d89b97ac89918c83d4` and
investigation `104e2b903777b91ecdbde16fe5d4a7852925658c7e228a707416ac1ad7238aff`.

Reproducibility tests passed for same configuration/seed WMS content, restricted
truth, and reconstruction. Changed-seed outputs differ and remain valid.

Known limitations remain deliberate:

- physical state is external and in memory during a run;
- there are no pallet IDs or handling-unit lifecycle;
- one live row supports one item and one code date per location;
- full transaction replay remains external to the WMS report registry; and
- plausible synthetic grocery descriptions remain a Phase 6 presentation task.

Final quality gate:

- baseline/investigation validation: PASS, no failures or warnings;
- all 12 reports: PASS;
- scenario check: PASS;
- both reconstructions: PASS, zero differences;
- `uv run pytest`: 160 passed in 68.26 seconds;
- `uv run ruff check .`: passed (`All checks passed!`);
- `uv run ruff format --check .`: passed (124 files already formatted);
- `git diff --check`: passed (line-ending conversion warnings only).

## Next milestone

Phase 4 covers templates, validation, and deterministic non-mutating preview.
Owner Checkpoint B review and template approval are prerequisites to any
inventory-adjustment apply behavior.

## Release 0.2.0 Phase 0

The active integrated roadmap is
`docs/29_RELEASE_0_2_0_INTERACTIVE_CONSOLE_AND_CSV_WORKFLOWS_ROADMAP.md`.
The implementation-ready current-interface audit and frozen contracts are in
`docs/30_RELEASE_0_2_0_PHASE_0_AUDIT_AND_CONTRACTS.md`.

Preservation is complete:

- development branch: `feature/release-0.2.0-console`;
- accepted `v0.1.0` commit:
  `3460339e5be7fb15556195fa670c6aafccbe5350`;
- source ZIP SHA-256:
  `d8a930d35ee451a837fdafe4364af6b2f1f4b2ddb19030ae3db961fb039690a6`;
- optional truth ZIP SHA-256:
  `cd6cf4a42cafb0ce3582ae03e37ee9222f329f81cdfa6e88903d33520d63835b`.

Phase 0 selected `prompt-toolkit` 3.x for interactive input and PyInstaller 6.x
for a portable one-folder Windows build. A disposable Python 3.14.6 proof ran
outside the repository with no Python or `uv` on the execution path. It imported
`prompt-toolkit` 3.0.53, reported project version 0.1.0, opened a schema-3 source
read-only, exported all 192 inventory-by-location rows, and emitted no ANSI
escape bytes when redirected. The proof bundle contained 703 files and
71,294,922 bytes. No proof source or bundle is tracked.

The existing WMS command/history design is retained. Writable sandboxes will
use a narrow additive schema `3.1.0` for sandbox identity, batch audit,
row-to-command mapping, and immutable replenishment-control change history.
Accepted schema `3.0.0` sources remain read-only. CSV contract 1.0 headers,
expected-state semantics, deterministic IDs, preview artifacts, confirmation,
and drift/idempotency rules are frozen in the Phase 0 audit.

Phase 0 verification:

- pre-change `uv sync --frozen`: PASS;
- pre-change `uv run pytest`: 180 passed, 1 accepted warning, in 179.38 seconds;
- pre-change `uv run ruff check .`: PASS;
- pre-change `uv run ruff format --check .`: PASS, 146 files already formatted;
- pre-change `git diff --check`: PASS;
- post-change `uv sync --frozen`: PASS, 63 packages checked;
- post-change `uv run pytest`: 180 passed, 1 accepted warning, in 175.79 seconds;
- post-change `uv run ruff check .`: PASS (`All checks passed!`);
- post-change `uv run ruff format --check .`: PASS, 148 files already formatted;
- post-change `git diff --check`: PASS.

## Release 0.2.0 Phase 1

The source command `operational-variance-toolkit console` now launches a
persistent `prompt-toolkit` session on an interactive terminal and a plain
stream fallback when input or output is redirected. The approved no-database
menu requires explicit sample or path selection. Session prompts are
`WMS[NO DB]>` and `WMS[RO:<database-stem>]>`.

Implemented commands are limited to `open`, `sample`, `close`, `status`,
`validate`, `describe`, `version`, `help`, `history`, `clear`, `exit`, and
`quit`. Parsing is case-insensitive for verbs, preserves path case, and accepts
quoted paths and paths containing spaces. Session state explicitly owns the
active connection, schema/run/facility metadata, validation state, working and
output directories, display defaults, provenance, and bounded command history.

Every accepted database is schema `3.0.0` and opens through SQLite URI
`mode=ro` with `PRAGMA query_only=ON`. Tests prove write attempts fail, repeated
open/close closes prior connections, malformed/legacy/unsupported sources are
rejected, and failed replacement opens preserve the existing session. The
representative sample session ran `status`, `validate`, `describe`, and `exit`;
its SHA-256 remained
`4225d8472887037b73d8d50f0eb3756961f1bf46939522d89b97ac89918c83d4`
before and after, and redirected output contained no ANSI escape bytes.

Phase 1 verification:

- `uv sync --frozen`: PASS, 63 packages checked;
- focused console tests: 37 passed in 5.80 seconds;
- full `uv run pytest`: 217 passed, 1 accepted Windows/ZMQ warning, in 149.61 seconds;
- `uv run ruff check .`: PASS (`All checks passed!`);
- `uv run ruff format --check .`: PASS, 155 files already formatted;
- `git diff --check`: PASS with line-ending conversion warnings only;
- representative redirected sample session: PASS, exit 0, validation PASS,
  description PASS, no ANSI, source SHA-256 unchanged.

Phase 1 owner-review correction:

- submissions containing LF, CR, or CRLF are rejected before parsing, dispatch,
  session-history insertion, or persistent-history acceptance;
- the rejection renders exactly `Multiple commands in one submission are not
  supported.` followed by `Enter or paste one command at a time.`;
- tests cover multiline commands, CRLF, numbered copied-history text, no
  dispatch, no history insertion, unchanged session/connection state, unchanged
  source SHA-256, and single-line defensive history rendering;
- normal single-line commands, quoted paths, Ctrl+C, EOF, redirected LF/CRLF
  input, and all existing one-shot commands remain green;
- correction `uv sync --frozen`: PASS, 63 packages checked;
- correction-focused console tests: 47 passed in 4.99 seconds;
- correction full `uv run pytest`: 227 passed, 1 accepted Windows/ZMQ warning,
  in 143.42 seconds;
- correction `uv run ruff check .`: PASS (`All checks passed!`);
- correction `uv run ruff format --check .`: PASS, 155 files already formatted;
- correction `git diff --check`: PASS with line-ending conversion warnings only.

Deliberate Phase 1 limitations:

- the displayed package version remains `0.1.0` until the Release 0.2.0 release gate;
- source `sample` resolution uses the accepted ignored baseline artifact, while
  the final bundled `sample-data/schema3_baseline.sqlite3` is a later packaging deliverable;
- sandbox/write mode, inquiry, reports, exports, trace, CSV, schema `3.1.0`, and
  production Windows packaging are not implemented.

## Release 0.2.0 Phase 2

The source console now provides typed, read-only inquiry for items, locations,
live recorded inventory, trips, picks, replenishments, QA events, adjustments,
and inventory transactions by item, location, transaction group, or command.
Detail output defaults to owner-facing vertical labels and supports an optional
`--technical` field-name view. Multi-row output is width-aware, reports shown
and total rows, applies the active default limit of 25, and gives continuation
and export guidance. Session commands implement `set limit`, `set format`,
`set timestamps`, and `show settings`.

`reports` lists the accepted 12-report registry and `report` executes each
report through the existing application workflow. Required date, timestamp,
and snapshot parameters remain enforced; timestamp filters are normalized to
UTC before SQLite text comparison. No report arithmetic was added to the
console.

CSV export covers all registered reports plus the canonical item, location,
inventory, and filtered inventory-transaction field sets. Exports use stable
UTF-8 columns and row order, refuse overwrite, write and flush a same-directory
temporary file before atomic no-overwrite promotion, remove temporary files,
report destination/row count/SHA-256, and escape formula-leading free text
without changing numeric or identifier values. Identical source data produces
byte-identical CSV files.

`trace` resolves a command ID, transaction-group ID, or source-record ID. It
shows accepted command chronology, operation and workflow type, source
reference, operational and WMS-recorded times, workflow facts, inventory lines,
before/delta/after arithmetic, final live recorded balances, net quantity, and
strict reciprocal transfer conservation. Replenishment task tracing includes
create, start, and confirm commands. QA, system/workflow, and recorded-snapshot
events correctly state that no inventory delta was recorded; no external
physical state, scenario target, or restricted truth is queried or displayed.

Every Phase 2 service uses the active SQLite URI `mode=ro` connection protected
by `PRAGMA query_only=ON`, or the existing validated read-only report workflow.
Filters select only allowlisted fixed queries with bound values. Representative
inquiry, report, export, and trace sessions preserved source SHA-256
`4225d8472887037b73d8d50f0eb3756961f1bf46939522d89b97ac89918c83d4`
before and after. Redirected output contained no ANSI escape bytes.

Phase 2 verification:

- `uv sync --frozen`: PASS, 63 packages checked;
- focused inquiry, console, session, export, trace, and report tests: 68 passed
  in 17.73 seconds;
- full `uv run pytest`: 271 passed, 1 accepted Windows/ZMQ warning, in 141.86
  seconds;
- `uv run ruff check .`: PASS (`All checks passed!`);
- `uv run ruff format --check .`: PASS, 160 files already formatted;
- `git diff --check`: PASS with line-ending conversion warnings only;
- representative redirected console acceptance: PASS, exit 0, 12-row
  replenishment-needs CSV, SHA-256
  `cde659192a48eeaee28af4013dad37eb4a27e1e274b9c912d0a7f37fecbdb73b`,
  no ANSI output, balanced replenishment trace, source checksum unchanged.

Deliberate Phase 2 limitations:

- accepted schema `3.0.0` databases remain read-only;
- the displayed package version remains `0.1.0` until the Release 0.2.0 release
  gate;
- arbitrary SQL, protected sandboxes, schema `3.1.0`, write mode, CSV
  maintenance templates/preview/apply, operational mutation, final Windows
  packaging, and GUI work remain unimplemented; and
- full transaction-replay reconstruction remains the separate analytical
  workflow rather than a WMS console operation.

## Release 0.2.0 Phase 3

Schema `3.1.0` sandboxes now use SQLite `user_version = 4` as a narrow additive
extension over an unchanged schema-3.0.0 WMS. The extension adds immutable
`sandbox_identity`, `maintenance_batch`, `maintenance_batch_row`, and
`replenishment_control_change` tables plus update/delete protection triggers.
The accepted source tables, run identity, reports, transactions, and snapshots
are copied without migration or mutation.

`clone` validates and hashes a schema-3.0.0 source, uses the SQLite backup API,
installs the extension transactionally, validates WMS and sandbox state, writes
a canonical sidecar manifest through atomic no-overwrite promotion, and removes
the database, WAL/SHM files, and manifest after any failed clone. Existing
destinations and source/destination aliases are refused. The source checksum is
checked before and after backup.

`open-sandbox` requires schema 3.1.0, one matching database identity row, an
exact sidecar structure, matching run/source/schema provenance, integrity and
foreign-key validation, and a valid current state fingerprint. Renaming or
copying an ordinary source does not confer write capability, and schema-3.1.0
sandboxes cannot be opened through the ordinary `open` path. The prompt is
`WMS[RW:<sandbox-stem>]>` and `status` shows sandbox/source identities,
checksums, creation version/time, latest batch, and supported workflows.

The active console connection remains SQLite URI read-only with
`PRAGMA query_only=ON` even in verified sandbox mode. Future write workflows
must open a separately verified transactional connection; direct SQL writes are
not a sandbox permission signal. All Phase 2 inquiry, describe, validate,
report, export, and trace operations continue to work on the sandbox. Phase 3
adds no operational mutation.

Phase 3 verification:

- `uv sync --frozen`: PASS, 63 packages checked;
- focused sandbox/console/report tests: 58 passed in 66.61 seconds;
- full `uv run pytest`: 283 passed, 1 accepted Windows/ZMQ warning, in 427.66
  seconds;
- `uv run ruff check .`: PASS (`All checks passed!`);
- `uv run ruff format --check .`: PASS, 166 files already formatted;
- `git diff --check`: PASS with line-ending conversion warnings only;
- all 12 standard reports on a verified schema-3.1.0 sandbox: PASS;
- source SHA-256 preservation, canonical WMS equivalence, restart, tamper,
  incomplete-clone cleanup, spaced paths, and immutable extension tables: PASS.

Phase 3 deliberately does not add adjustment/control commands, generic force
write, arbitrary SQL, partial provenance bypass, or any mutation workflow.

## Repository presentation cleanup

Obsolete repository-only development scaffolding and onboarding packets were
removed. Retained technical documents now use tool-neutral implementation
language, and the source-release allowlist no longer packages the removed
configuration or instruction files. Runtime behavior, schemas, dependencies,
accepted data artifacts, and analytical outputs were not changed.

Cleanup verification:

- focused release-packaging and CLI tests: 21 passed in 76.54 seconds;
- full `uv run pytest`: 180 passed, 1 accepted warning, in 153.71 seconds;
- `uv run ruff check .`: PASS (`All checks passed!`);
- `uv run ruff format --check .`: PASS, 144 files already formatted;
- `git diff --check`: PASS;
- tracked working-tree filename and text residue scan: no matches.

## Phase 5 final acceptance

Phase 5 Slices 0-10 are complete. The frozen contract is
`docs/26_PHASE_5_ANALYSIS_CONTRACT.md`; the public workflow is:

```powershell
uv run operational-variance-toolkit analyze --database <schema3.sqlite3> --reconstruction <analysis-dir> --config configs/phase5_analysis.toml --output <new-statistics-dir>
```

Definitive outputs are at
`artifacts/analysis/RUN-D4876095A8166078/statistics_accepted`. They contain 166
descriptive rows, 15 replenishment rows, 5 QA-adjustment rows, 18 crude selector
rows, 1 adjusted selector row, 18 sensitivity rows, and 6 hypothesis rows plus
the frozen configuration, diagnostics, and checksum manifest.

The investigation population is 1,133 eligible picks, 1,771 requested cases,
33 short lines, and 39 short cases over 140 trips and 18 selectors. `OP-0002`
has a 10.4317% crude short-line rate versus 0.4678% for peers, a 9.9638-point
crude difference. The predefined trip-clustered binomial logit converged with a
full-rank eight-column design. Adjusted probabilities are 3.5178% versus
2.6701%, a 0.8477-point difference with a 95% interval from -1.1213 to 2.8167
points. The absolute contrast attenuated 91.49%, passing both frozen criteria.

All six hypotheses are evaluated. Evidence contradicts a generalized selector
problem and supports localized operational-condition, high-velocity,
replenishment/availability, QA-adjustment, and eventual-correction explanations
only at descriptive or mechanism-consistent claim strength. The target outside
the condition differs from peers by 0.3413 points. The adjusted short-case
sensitivity is 0.8034 points (95% interval -0.5119 to 2.1188).

The main sensitivity limitation is a leave-`ITEM-0005`-out stress test: it
removes every exposed-peer short in the condition, makes logit estimation
unstable, and invokes the documented fallback with a 5.0811-point residual.
This limited-overlap result is disclosed and does not justify individual fault.
Baseline comparison has only three events and an imprecise -1.3825 to 8.1807
point interval.

Replenishment evidence shows 8.3333% short lines within 120 minutes of recorded
confirmation versus 3.2995% outside, 78/78 quantity-conserving transfers, and 9
later positive corrections. Recorded task duration is uniformly seven minutes,
so ordinary WMS timing cannot reveal hidden physical delay. QA evidence finds
13/18 same-item/location four-hour candidates, 10 generic corrections, and 13
quantity-compatible pairs; candidate fragility is not elevated. All 192
locations reconcile exactly and 30 short lines had sufficient recorded
pre-pick quantity.

Phase 5 acceptance evidence:

- `uv sync`: PASS, 16 packages resolved/checked;
- CLI help: PASS with `analyze` registered;
- investigation validation: PASS, no failures or warnings;
- safe-new reconstruction: PASS, 1,499 ledger rows and zero differences;
- safe-new frozen analysis: PASS; material attenuation and six hypotheses true;
- same-input canonical reproducibility: PASS in integration tests;
- changed valid source produces different output: PASS in integration tests;
- source database SHA-256 preserved as
  `104e2b903777b91ecdbde16fe5d4a7852925658c7e228a707416ac1ad7238aff`;
- ordinary analysis loaded ground truth: false; and
- `uv run pytest`: 173 passed in 368.14 seconds.

## Phase 6 final acceptance

Phase 6 Slices 0-6 are complete under the approved release policy:

- MIT License;
- Python `>=3.14`, developed and acceptance-tested with Python 3.14.6;
- no XLSX packet or spreadsheet dependency;
- a versioned local source ZIP;
- a separately named optional restricted-ground-truth spoiler ZIP;
- no push, hosted release, upload, or publication; and
- local Git tag `v0.1.0` after final acceptance.

Definitive reporting is at `artifacts/release/v0.1.0/reporting_release`:

- source and executed notebooks under `notebook/`;
- four PNG figures plus CSV/JSON exhibit catalogs under `figures/`;
- `executive_report.md` and the five-page `executive_report.pdf`;
- `technical_appendix.md` and `source_notes.json`; and
- `reporting_manifest.json` with SHA-256
  `f9d81d8d0e934fb125c5c8105869f194b13d91c8d0eec8a46cbb32b09dcab49b`.

All 12 standard reports were exported for both accepted schema-3 databases, for
24 CSV files total. The reporting workflow validated all frozen Phase 5 input
checksums and 192 reconciliation rows with zero differences. The executed
notebook contains 20 cells, 9 executed code cells, and zero error outputs. The
PDF opens as five pages and passed rendered-page visual inspection.

The clean-source-archive reproduction ran from a fresh temporary extraction
outside the repository. It passed frozen installation, CLI version/help, baseline and investigation
generation, both validations, scenario check, 24 standard report exports, both
reconstructions, statistical analysis, notebook execution, PDF opening,
repackaging, and external checksum verification. Nine frozen statistical files
were byte-identical to the accepted release examples; only
`analysis_manifest.json` was excluded for its execution timestamp and source
provenance. The clean investigation database SHA-256 remained
`8ac2ac847556814e2a956f8c4a04cd8580dbe54c0b10d39b69e4afda55299450`
before and after ordinary analysis.

Final quality evidence:

- primary local suite: 180 passed, 1 benign Windows/ZMQ warning, in 463.67 seconds;
- clean extracted suite: 180 passed, 1 benign Windows/ZMQ warning, in 474.05 seconds;
- `uv run ruff check .`: PASS;
- `uv run ruff format --check .`: PASS, 146 files already formatted;
- `git diff --check`: PASS with line-ending conversion warnings only;
- ordinary analysis loaded ground truth: false;
- primary source/truth leakage scan: PASS;
- primary archive paths are safe and contain no restricted generated truth;
- optional archive contains a prominent spoiler warning, its own manifest, and
  its own internal and external SHA-256 checksums; and
- source databases and ordinary analysis inputs remained unchanged.

Known limitations remain explicit: this is one synthetic facility-scale run,
the primary model has 33 short events, one leave-Item-out sensitivity exposes
limited overlap, recorded WMS confirmation does not observe physical
availability timing, candidate QA relationships are not causal links, and no
individual labor-performance conclusion is supported.

## Legacy artifacts

Existing schema `2.0.0` databases and Phase 4 exports are historical acceptance references. They must not be migrated or edited in place.

Corrected schema `3.0.0` baseline and investigation artifacts are regenerated
from configuration at new paths; they do not migrate legacy data in place.

## Continuity note

The Gwent Deck Workbench remains a separate paused project. Do not rename, repurpose, or overwrite it.
