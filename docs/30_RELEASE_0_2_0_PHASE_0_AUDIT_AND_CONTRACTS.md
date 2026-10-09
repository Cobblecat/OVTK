# Release 0.2.0 Phase 0 Audit and Contracts

**Status:** Engineering work complete; owner checkpoint pending  
**Branch:** `feature/release-0.2.0-console`  
**Starting release:** accepted `v0.1.0`  
**Scope:** preservation, current-interface audit, dependency and packaging proof, and contract freeze only

## 1. Outcome

Release 0.1.0 remains unchanged. Phase 0 established an implementation-ready
starting point for the interactive console, protected sandboxes, two CSV
maintenance workflows, and a portable Windows x64 distribution. No production
console, sandbox, CSV-apply, schema-upgrade, or release-0.2.0 runtime behavior
was implemented.

The selected focused dependencies are:

- `prompt-toolkit` 3.0.53 or later within the 3.x line for persistent input,
  history, completion, and Windows terminal behavior; and
- PyInstaller 6.21 or later within the 6.x line as a development/build tool for
  the portable one-folder Windows distribution.

Application-owned rendering remains the default. Rich is not selected for
Phase 1. The formatting decision may be revisited only if width-aware output in
Phase 2 cannot meet its acceptance contract without another focused library.

## 2. Preservation Evidence

| Check | Result |
|---|---|
| Starting branch | `refactor/wms-operational-fidelity` |
| Development branch | `feature/release-0.2.0-console` |
| Accepted commit | `3460339e5be7fb15556195fa670c6aafccbe5350` |
| Dereferenced `v0.1.0` target | `3460339e5be7fb15556195fa670c6aafccbe5350` |
| Source ZIP SHA-256 | `d8a930d35ee451a837fdafe4364af6b2f1f4b2ddb19030ae3db961fb039690a6` |
| Optional truth ZIP SHA-256 | `cd6cf4a42cafb0ce3582ae03e37ee9222f329f81cdfa6e88903d33520d63835b` |
| Pre-change tests | 180 passed, 1 warning, 179.38 seconds |
| Pre-change Ruff lint | PASS |
| Pre-change Ruff format | PASS, 146 files formatted |
| Pre-change `git diff --check` | PASS |

The warning is the accepted Windows ZMQ event-loop warning from the Phase 6
executed-notebook test. Neither accepted archive nor the `v0.1.0` tag was
modified.

## 3. Current Interface Audit

### 3.1 Entry points and versioning

| Surface | Current implementation | Release 0.2.0 use |
|---|---|---|
| Console script | `pyproject.toml` -> `operational_variance_toolkit.cli:main` | Keep one executable entry point; add a `console` subcommand in Phase 1. |
| Parser and dispatch | `src/operational_variance_toolkit/cli.py` | Retain one-shot behavior; move interactive parsing/dispatch into a console package. |
| Version | `src/operational_variance_toolkit/version.py` via installed metadata | Reuse in source and frozen executables; copy distribution metadata into the bundle. |
| Source execution | `src/operational_variance_toolkit/__main__.py` | Preserve. |
| Canonical release version | `0.1.0` in `pyproject.toml` | Do not bump until the Phase 8 release gate. |

The current CLI is centralized and large. Phase 1 must not duplicate its
business workflows. Interactive handlers call application functions and turn
expected `ToolkitError` instances into concise session messages.

### 3.2 Schema routing and read-only access

- SQLite `PRAGMA user_version` values 1, 2, and 3 route legacy and schema-3
  validation in `validation/dataset.py`.
- `init-db` remains the legacy schema-1/2 path; `init-wms` is canonical schema 3.
- `connect_readonly_database()` opens with SQLite `mode=ro` and
  `PRAGMA query_only=ON`.
- Schema-3 reports validate the source before querying ordinary WMS tables.
- `immutable=1` is not appropriate for a general console session because an
  externally active WAL database must remain visible. Accepted source files are
  protected by application mode, not by assuming every database is immutable.

Phase 1 must add focused tests that writes fail through the read-only helper and
that repeated console inquiry preserves source bytes.

### 3.3 WMS commands, units of work, and history

`WmsService` is the canonical public command boundary. It is independent of the
simulator and scenario modules and currently supports assignment, clearing,
picks, replenishment lifecycle, direct transfers, adjustments, QA, system
events, and snapshots.

`WmsCommandRepository.unit_of_work()` uses `BEGIN IMMEDIATE`, commits only on
success, and rolls back on failure. Each accepted command is recorded in
`wms_command` with a stable payload hash and result reference. Duplicate command
IDs are rejected before mutation. Quantity changes write immutable
`inventory_transaction` rows and update `inventory_master` in the same unit of
work.

Important gap: every public service method currently owns its transaction.
Phase 5 batch atomicity therefore requires a controlled refactor that lets a
batch application workflow execute command cores under one outer unit of work
without changing single-command behavior. It must not loop over independently
committed service calls.

### 3.4 Adjustment and replenishment controls

Canonical adjustment command fields are:

```text
run_id, command_id, event_utc, recorded_utc, item_id, location_id,
operator_id, qty_delta_cases, reason_code, reference_code
```

The result is traceable through `wms_command`, `inventory_adjustment`,
`inventory_transaction`, and updated `inventory_master`.

Canonical replenishment-control fields on `inventory_master` are:

```text
minimum_qty_cases, reorder_trigger_cases, target_qty_cases, maximum_qty_cases
```

The existing assignment command validates these fields but is not a truthful
maintenance command for an already assigned pick slot. There is no current
control-change history record. Release 0.2.0 therefore requires a narrow public
maintenance command and immutable before/after control history in writable
sandboxes.

### 3.5 Reports, snapshots, and exports

- `wms/domain/reports.py` is the stable report registry and owner-facing label
  map.
- `wms/application/reports.py` validates report codes, allowed filters, required
  filters, source schema, and source WMS state.
- `wms/storage/reports.py` owns SQL and deterministic row order.
- `export_report_csv()` refuses overwrite and emits the registered full display
  column set.
- Snapshot capture copies live `inventory_master` into immutable batch/line
  records. Full transaction replay remains an external analytical workflow.

Phase 2 should add a registry-to-handler completeness test. Report parameter
types and defaults are currently implicit in application validation and query
methods; the console command layer must use explicit adapters rather than infer
types from help text.

### 3.6 Resources, release packaging, and tests

The installed wheel currently has no package-resource registry and no bundled
sample/template discovery. Phase 1 requires a bundle-aware resource resolver;
Phase 7 will populate the final sample and documentation layout.

The 0.1.0 release packager already provides deterministic ZIP timestamps,
ordering, manifests, checksums, overwrite refusal, and truth-leak checks. It is
the base for source packaging, but the Windows bundle needs a separate staged
layout and PyInstaller build specification. Source staging also needs a
symlink/containment guard before reuse for a public 0.2.0 archive.

Reusable tests include `tests/test_cli.py`, `tests/test_wms_reports.py`,
`tests/test_release_packaging.py`, and the subprocess fixture in
`tests/conftest.py`.

## 4. Canonical Name Mapping

| Roadmap concept | Canonical schema-3 name |
|---|---|
| signed adjustment quantity | `qty_delta_cases` |
| adjustment source/note reference | `reference_code`; CSV `user_note` remains separately identified |
| current quantity | `qty_on_hand_cases` |
| expected last-change token | `last_transaction_id` plus the expected row values |
| minimum cases | `minimum_qty_cases` |
| reorder trigger | `reorder_trigger_cases` |
| target cases | `target_qty_cases` |
| maximum cases | `maximum_qty_cases` |
| physical case maximum | calculated `pallet_capacity * cases_per_pallet` |
| snapshot identity | `snapshot_batch_id` |
| snapshot quantity | `qty_on_hand_cases` on `inventory_snapshot` |
| transaction group | `transaction_group_id` |
| command identity/history | `command_id` and `wms_command` |

Legacy `capacity_cases`, `minimum_cases`, `target_cases`, and `maximum_cases`
must not leak into the 0.2.0 schema-3 maintenance contract.

## 5. Dependency and Packaging Decisions

### 5.1 Console input

`prompt-toolkit` is selected because it directly supplies persistent prompts,
history, completion, interrupt/EOF handling, and tested Windows terminal
behavior. It is BSD-licensed. Standard-library `input()` remains the degraded
fallback for noninteractive or unsupported terminals. Rendering remains plain
text and application-owned so redirected output contains no control sequences.

### 5.2 Windows packager

PyInstaller is selected for a one-folder build. Version 6.21.0 supports the
project's Python 3.14.6 environment and carries the GPL exception permitting
distribution of the bundled application. Its direct build dependencies in the
proof were MIT or BSD-3-Clause licensed. Phase 7 must generate
`THIRD_PARTY_NOTICES.txt` from locked package metadata and bundled license files.

The release does not select single-file compression, Nuitka, an installer, or
code signing. Nuitka remains a fallback only if a later full-dependency bundle
uncovers a PyInstaller blocker.

### 5.3 Feasibility proof

The disposable proof was built and executed outside the repository in a fresh
temporary directory:

| Property | Result |
|---|---|
| Python | 3.14.6 |
| PyInstaller | 6.21.0 |
| `prompt-toolkit` | 3.0.53, bundled and imported |
| Build form | one-folder Windows x64 executable |
| Version metadata | `0.1.0` printed from copied distribution metadata |
| Database | schema-3 baseline opened read-only |
| Report | `inventory-by-location`, 192 rows |
| CSV | 192 data rows written in fresh output directory |
| Execution path | `C:\Windows\System32;C:\Windows` only |
| Python/`uv` on execution path | none |
| Redirected ANSI escape bytes | none |
| Proof bundle | 703 files, 71,294,922 bytes |

The temporary proof is not a release artifact and is not tracked.

## 6. Frozen Console Contract

### 6.1 Modes and prompts

```text
WMS[NO DB]>
WMS[RO:<database-stem>]>
WMS[RW:<sandbox-stem>]>
```

Every existing database opens read-only. Write mode is available only after a
verified sandbox open. Filesystem writability and a filename containing
`sandbox` are never permission signals.

### 6.2 Commands and defaults

The high-level vocabulary in the release roadmap is canonical. Verbs are
case-insensitive; identifiers are normalized only by existing WMS rules. Phase
1 implements only lifecycle commands: `open`, `sample`, `close`, `status`,
`validate`, `describe`, `version`, `help`, `history`, `clear`, `exit`, and
`quit`. Later phases add inquiry, trace, sandbox, export, and CSV commands.

The default multi-row result limit is 25. Detail output defaults to vertical
key/value presentation. Multi-row output defaults to plain width-aware tables.
`--no-style` disables optional terminal styling, and redirected output is always
plain.

### 6.3 Paths and startup

- Relative user paths resolve from the session working directory shown by
  `status`.
- Bundle resources resolve from the frozen application root, never from the
  process current directory.
- User-created outputs default under `workspace/` and never under private
  runtime directories.
- Paths with spaces are first-class inputs.
- Existing outputs are refused; no implicit overwrite or `--force` is added.
- No-argument standalone launch presents the compact start menu in the roadmap.
- The recommended sample behavior is explicit menu selection, not automatic
  opening.

## 7. Frozen Sandbox and Schema Contract

### 7.1 Clone and protection

Sandbox creation validates the source read-only, hashes it, copies it through
the SQLite backup API, applies an additive upgrade transaction, validates the
copy, closes it, hashes the upgraded copy, and atomically writes its sidecar
manifest. Any failure removes the new database, sidecars, and incomplete
manifest. Existing destinations are refused.

Write mode requires all of:

1. supported sandbox schema `3.1.0` (`PRAGMA user_version = 4`);
2. one valid `sandbox_identity` row;
3. a sidecar manifest with the same sandbox ID, run ID, schema, and source
   provenance;
4. successful WMS and sandbox-extension validation; and
5. an explicit `open-sandbox` action.

Accepted schema `3.0.0` databases remain read-only and are never upgraded in
place.

### 7.2 Manifest format

The UTF-8 JSON sidecar uses sorted keys and compact canonical serialization for
hashing. Required fields are:

```text
manifest_version, sandbox_id, sandbox_database_filename,
source_database_path, source_database_sha256, source_schema_version,
source_run_id, sandbox_schema_version, created_at_utc,
created_by_application_version, initial_sandbox_sha256
```

The source path is provenance for a local sandbox manifest and must not enter a
public portable release manifest. The sandbox ID is also stored in the database.
The initial sandbox hash is evidence of the clone/upgrade checkpoint; it is not
expected to equal the database after approved writes.

### 7.3 Additive sandbox schema

Schema `3.1.0` adds only:

- `sandbox_identity` for the database-side provenance marker;
- `maintenance_batch` for accepted/applied batch audit;
- `maintenance_batch_row` for row-to-command/result mapping; and
- `replenishment_control_change` for immutable before/after control history.

Inventory adjustments continue to use ordinary `inventory_adjustment` and
`inventory_transaction` records. A new typed replenishment-control command uses
`wms_command` and `replenishment_control_change`; it does not create an
inventory transaction because no quantity moves. Update/delete triggers protect
the new audit tables. Preview artifacts remain external and do not mutate the
database.

## 8. Frozen CSV Contract

### 8.1 Contract version and encoding

Both workflows begin at CSV contract `1.0`. Input accepts UTF-8 with or without
a BOM and RFC 4180 quoting. Headers are exact and case-sensitive after BOM
removal. Extra, missing, or duplicate headers reject the file. Integer fields
use base-10 syntax without decimals, grouping characters, or formulas.

`row_reference` is required, unique after surrounding-space trimming, and
limited to a documented safe identifier length. Operational IDs are uppercased
only through their existing canonical normalizers. `user_note` preserves text
but is never used as an operational identifier. CSV artifacts escape
formula-leading text cells when written for spreadsheet consumption without
changing the canonical value used for hashing.

### 8.2 Inventory-adjustment headers

```text
csv_contract_version,row_reference,location_id,item_id,operator_id,
qty_delta_cases,reason_code,user_note,expected_qty_on_hand_cases,
expected_item_id,expected_last_transaction_id
```

`qty_delta_cases` is required and nonzero. `operator_id` must exist with an
accepted adjustment role. `user_note` is optional and maps to a bounded
reference/note adapter, not to an ID. Every expected-state field is required as
a comparison. A blank `expected_last_transaction_id` means the current value is
expected to be SQL NULL; it never means ignore state.

### 8.3 Replenishment-control headers

```text
csv_contract_version,row_reference,pick_location_id,item_id,operator_id,
minimum_qty_cases,reorder_trigger_cases,target_qty_cases,maximum_qty_cases,
user_note,expected_item_id,expected_qty_on_hand_cases,
expected_minimum_qty_cases,expected_reorder_trigger_cases,
expected_target_qty_cases,expected_maximum_qty_cases,
expected_last_transaction_id
```

All proposed and expected control values are required nonnegative integers.
The proposed values must satisfy minimum <= trigger <= target <= maximum, and
maximum must not exceed the item-dependent physical maximum. Location type,
assignment, operator role, current quantity, current controls, and last
transaction token must still match at preview and immediately before apply.

### 8.4 Blank semantics

- Required operational fields and proposed numeric values: blank rejects.
- `user_note`: blank normalizes to an empty string.
- Expected item/quantity/control values: blank rejects.
- Expected nullable transaction token: blank means expected NULL.
- Blank never means wildcard or skip validation.

### 8.5 Batch and row identity

Canonical JSON contains the workflow type, CSV contract version, source run ID,
sandbox ID, schema version, normalized rows sorted by `row_reference`, and a
SHA-256 fingerprint of every relevant current WMS row. Paths, timestamps,
filesystem metadata, and source row order are excluded.

```text
batch_id  = BATCH-<first 24 uppercase hex characters of SHA-256(canonical JSON)>
command_id = CSV-<batch digest prefix>-<SHA-256(row_reference) prefix>
```

Collision detection compares the complete stored digest and rejects any
different payload using an existing shortened ID.

### 8.6 Preview and apply

Preview writes the roadmap's six-file batch directory and sets
`database_modified` to `false`. `preview_manifest.json` records full checksums,
database/sandbox identity, the relevant-state fingerprint, normalized row
digest, validation counts, batch ID, and confirmation token.

The confirmation token is
`APPLY-<first 16 uppercase hex characters of the preview-manifest SHA-256>`.
Interactive apply requires the user to enter it. One-shot apply requires an
explicit `--confirm` value. Apply revalidates manifest/source checksums,
sandbox provenance, permissions, row state, and the batch's prior status before
opening one atomic batch unit of work. One invalid row or any state drift blocks
the whole batch. Reapplying an accepted batch returns its existing result map
without posting a second change.

## 9. Frozen Windows Bundle Contract

The release artifact is
`Operational-Variance-Toolkit-0.2.0-Windows-x64.zip`. It expands to the
user-facing layout in the release roadmap with:

- `OperationalVarianceToolkit.exe` and a private PyInstaller runtime;
- a safe read-only schema-3 baseline under `sample-data/`;
- CSV templates;
- writable `workspace/exports`, `workspace/sandboxes`, and
  `workspace/batches` directories;
- quick-start, command, and CSV workflow documentation;
- MIT license, third-party notices, version, manifest, and checksums; and
- no restricted truth, source checkout, Python, `uv`, or network requirement.

Private runtime placement may follow PyInstaller's one-folder conventions. The
public directories and filenames remain stable.

## 10. Risks and Sequencing Constraints

1. Batch atomicity cannot be implemented as repeated current service calls;
   Phase 5 needs a tested shared-transaction command execution path.
2. Replenishment-control maintenance needs schema `3.1.0` audit records before
   Phase 6; it must not masquerade as reassignment or inventory movement.
3. The final executable imports the full CLI dependency graph, unlike the
   bounded spike. Phase 7 must prove Pandas, Statsmodels, Matplotlib, notebook,
   and reporting compatibility and document bundle size/startup time.
4. A sidecar manifest is a provenance and safety mechanism, not an adversarial
   security boundary. The product remains single-user and local.
5. SQLite source cloning must account for WAL state by using the backup API.
6. Formula-safe CSV serialization must not silently alter the canonical batch
   payload.
7. Source release staging requires containment/symlink tests before reuse.
8. Existing schema-3 source and accepted 0.1.0 artifacts remain read-only
   throughout the release.

## 11. Exact Phase 1 Scope

Phase 1 may change only the console foundation and its documentation/tests.

Add:

```text
src/operational_variance_toolkit/console/__init__.py
src/operational_variance_toolkit/console/commands.py
src/operational_variance_toolkit/console/input.py
src/operational_variance_toolkit/console/rendering.py
src/operational_variance_toolkit/console/resources.py
src/operational_variance_toolkit/console/session.py
src/operational_variance_toolkit/console/startup.py
tests/test_console_commands.py
tests/test_console_session.py
tests/test_console_cli.py
tests/test_console_resources.py
```

Adapt:

```text
src/operational_variance_toolkit/cli.py
README.md
PROJECT_STATUS.md
docs/12_DECISION_LOG.md (only if implementation reveals a material decision)
```

Phase 1 implements source launch, no-argument start menu, optional startup
database/sample selection, read-only open/close, prompt labels, status,
validation, description, help, version, history, clear, Ctrl+C/EOF behavior,
and thin rendering. It adds no inquiry/report shortcuts, trace, sandbox, CSV,
schema, mutation, or production packaging behavior.

Phase 1 acceptance tests must cover quoted paths and paths with spaces, command
case behavior, missing/unknown commands, session transitions, default settings,
read-only enforcement, source checksum preservation, invalid/malformed/legacy
database handling, repeated open/close, help/version/status/validate/describe,
Ctrl+C/EOF, redirected output, no-style degradation, resource resolution from a
non-repository working directory, and continued one-shot CLI behavior.

## 12. Phase 0 Acceptance and Owner Checkpoint

Engineering acceptance is complete when the post-change gate recorded in
`PROJECT_STATUS.md` is green. Production console work remains blocked only on
review of these user-facing recommendations:

1. portable ZIP rather than an installer;
2. the start-menu wording shown in the release roadmap;
3. prompt labels `NO DB`, `RO`, and `RW`;
4. the roadmap's high-level command vocabulary; and
5. explicit sample selection through the start menu rather than automatic open.

Recommended defaults are result limit 25, explicit sample selection, and the
roadmap wording unchanged for Phase 1. These are reversible presentation choices
and do not alter the accepted WMS architecture.
