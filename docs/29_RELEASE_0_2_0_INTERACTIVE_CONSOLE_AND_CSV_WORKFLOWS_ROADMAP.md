# 29 — Release 0.2.0 Interactive WMS Console, CSV Workflows, and Standalone Windows Distribution

**Document status:** Active integrated roadmap; Phase 0 engineering work complete pending owner checkpoint  
**Target release:** `0.2.0`  
**Predecessor:** Accepted release `0.1.0`  
**Project:** Operational Variance Investigation Toolkit  
**Platform target:** Windows 10/11 x64, with the source project remaining runnable through Python and `uv`  
**Data policy:** Synthetic data only  
**Primary objective:** Turn the accepted miniature WMS into a practical, self-contained Windows application that can be launched without VS Code, Python, or `uv`, while preserving the existing WMS architecture and adding safe CSV-based maintenance workflows.

**Phase 0 execution record:** See `docs/30_RELEASE_0_2_0_PHASE_0_AUDIT_AND_CONTRACTS.md` for the current-interface audit, selected dependencies, packaging proof, frozen implementation contracts, and owner-review questions. Production console work has not begun.

---

## 1. Purpose of this document

This file is both:

1. the release-level roadmap for `0.2.0`; and
2. the detailed implementation outline for every phase in the release.

It replaces the earlier roadmap-only version of this document. Separate phase files are not required unless a later phase becomes materially more complex than expected.

The document supports implementation in controlled increments. User-facing WMS terminology, workflow feel, and final acceptance remain subject to product-owner review.

The central correction from the earlier roadmap is binding:

> **Release `0.2.0` must not require the user to live inside VS Code or operate a Python development environment.**

The source project will remain available for development and testing, but the primary user-facing deliverable is a portable Windows application that launches directly into the WMS console.

---

## 2. Release starting point

Release `0.1.0` is accepted and locally tagged as `v0.1.0`. It already provides:

- a deterministic schema-3 miniature WMS;
- stable `item_master` and `location_master` files;
- live `inventory_master` state keyed by location;
- immutable `inventory_transaction` audit history;
- atomic public WMS command services;
- standard operational reports;
- deterministic CSV report exports;
- independent physical simulation and scenario drivers;
- three-way inventory reconstruction;
- truth-blind statistical analysis;
- notebook, exhibits, executive reporting, and technical documentation;
- source and optional restricted-truth release archives;
- clean-environment reproduction; and
- a frozen, accepted Git checkpoint.

Release `0.2.0` must build on those capabilities rather than replace them.

The release is an **operability and distribution release**. Its purpose is to make the existing WMS comfortable to use, inspect, demonstrate, and safely modify in a sandbox.

---

## 3. Release product statement

> **Operational Variance Toolkit `0.2.0` is a self-contained Windows WMS console that opens schema-3 databases, provides readable inquiry and transaction tracing, runs and exports standard reports, creates protected sandboxes, and applies previewed CSV maintenance batches through the same tested WMS services used by the simulation engine.**

The release must support two equivalent launch paths.

### 3.1 Developer/source launch

```powershell
uv run operational-variance-toolkit console
```

This path remains useful for development, debugging, testing, and contributors.

### 3.2 Standalone Windows launch

```text
OperationalVarianceToolkit.exe
```

The standalone application must:

- launch by double-clicking the executable;
- launch from PowerShell or Command Prompt;
- require no separate installation of Python, `uv`, or VS Code;
- include all required runtime components in its portable release bundle;
- find bundled sample data, templates, and documentation through paths relative to the application bundle;
- operate without internet access after extraction; and
- expose the same console behavior as the source launch.

A single-file executable is **not** required. The target is a reliable portable Windows folder distributed as a ZIP. A one-folder package containing the executable and its private runtime dependencies is still a standalone application because the user does not install or manage those dependencies.

An installer, MSI, Start Menu registration, automatic updates, or Windows Store packaging are deferred.

---

## 4. Intended user experience

### 4.1 Double-click launch

Launching `OperationalVarianceToolkit.exe` without arguments should open a terminal window and present a compact start menu:

```text
Operational Variance Toolkit 0.2.0

1. Open the included sample WMS read-only
2. Open another WMS database
3. Create or open a sandbox
4. View quick help
5. Exit

Select an option:
```

The exact wording may be refined during owner review, but the user must not be dropped into an unexplained blank prompt.

### 4.2 Direct launch with a database

```powershell
.\OperationalVarianceToolkit.exe --database .\data\warehouse.sqlite3
```

The application should validate the database and enter read-only mode:

```text
Operational Variance Toolkit 0.2.0
Database: warehouse.sqlite3
Schema: 3.0.0
Mode: READ-ONLY
Validation: PASS

WMS[RO:warehouse]>
```

### 4.3 Read-only inquiry

```text
WMS[RO:warehouse]> item ITEM-0001
WMS[RO:warehouse]> location LOC-00001
WMS[RO:warehouse]> inventory location LOC-00001
WMS[RO:warehouse]> inventory item ITEM-0001
WMS[RO:warehouse]> transactions location LOC-00001
WMS[RO:warehouse]> report replenishment-needs
WMS[RO:warehouse]> trace TXG-000475
WMS[RO:warehouse]> export report inventory-by-location inventory.csv
```

### 4.4 Sandbox and CSV maintenance

```text
WMS[RO:warehouse]> clone training_sandbox.sqlite3
WMS[RW:training_sandbox]> csv template inventory-adjustments adjustments.csv
WMS[RW:training_sandbox]> csv validate adjustments.csv
WMS[RW:training_sandbox]> csv preview adjustments.csv
WMS[RW:training_sandbox]> csv apply <preview-batch-id>
WMS[RW:training_sandbox]> trace <new-command-id>
```

The user should be able to edit CSV files in Excel or another spreadsheet application and return to the console without writing SQL.

---

## 5. Binding architectural principles

These principles apply to every phase and are binding.

### 5.1 The console is a client of the WMS

```text
Standalone Windows executable ─┐
Interactive source console ────┤
One-shot CLI commands ─────────┤
CSV workflow services ─────────┼──> Public WMS application services
Scenario drivers ──────────────┘              |
                                                v
                                      Schema-3 SQLite WMS
```

The console must not become a parallel WMS implementation.

It must reuse existing services for:

- inventory validation;
- item and location rules;
- adjustment semantics;
- replenishment-control rules;
- transaction sequencing;
- idempotency;
- atomicity;
- report generation;
- snapshots; and
- audit persistence.

Interface code may parse commands and render results. It must not contain warehouse arithmetic or direct operational mutations.

### 5.2 CSV is an interface, not a database shortcut

```text
CSV row
    -> typed import record
    -> canonical normalization
    -> parse validation
    -> WMS-state validation
    -> proposed public WMS command
    -> dry-run preview
    -> approved public WMS command
    -> live state update and immutable audit
```

CSV workflows may read WMS state through approved repositories and read models. They may not issue ad hoc `INSERT`, `UPDATE`, or `DELETE` statements against operational tables.

### 5.3 Read-only is always the default

- Existing generated and accepted WMS databases open read-only.
- Filesystem writability does not imply application write permission.
- The prompt must show the current mode.
- Read-only database connections should use SQLite read-only and query-only protections where practical.
- Accepted `0.1.0` databases must never be edited in place.

### 5.4 Writes are limited to verified sandboxes

Write mode requires a database created or cloned through the application’s sandbox workflow.

A sandbox must have verifiable provenance containing at least:

- source database path or source identity;
- source SHA-256;
- source schema version;
- source run ID;
- sandbox creation time;
- application version that created it; and
- sandbox database SHA-256 immediately after cloning or upgrade.

The application must not enable write mode merely because a database filename contains “sandbox.”

### 5.5 Preview must precede apply

- A CSV file cannot be applied without a successful preview.
- Apply must reference the accepted preview batch or its manifest.
- The database state must be rechecked immediately before apply.
- Any relevant state drift invalidates the preview and requires a new preview.
- One invalid row blocks the complete batch.
- Any failure during apply rolls back the complete batch.

### 5.6 Batches are idempotent and traceable

Every normalized batch receives a deterministic batch ID. Every row receives a deterministic command ID derived from the batch and stable row identity.

Applying the same accepted batch twice must not double-post changes.

Every applied row must be traceable from:

```text
source CSV
    -> normalized row
    -> preview result
    -> WMS command ID
    -> workflow or maintenance record
    -> inventory transaction where applicable
    -> final live state
```

### 5.7 Existing `0.1.0` behavior remains supported

The following source workflows must continue to work:

- configuration checking;
- WMS initialization and generation;
- validation and description;
- standard reports;
- scenario checking;
- reconstruction;
- statistical analysis;
- reporting build;
- release packaging; and
- legacy schema compatibility already retained by `0.1.0`.

### 5.8 Standalone packaging is a distribution layer

The Windows packaging system must wrap the same Python package and entry points used by source execution. It must not contain a forked copy of business logic.

### 5.9 Synthetic-data and restricted-truth boundaries remain intact

- No real employer records or identities are introduced.
- Restricted ground truth is never bundled into the ordinary Windows application package.
- The standalone application must not expose or depend on hidden scenario data.
- The sample WMS included with the Windows package must be safe for ordinary analyst use.

### 5.10 No push or publication without a new approval

The release process may create local commits, archives, checksums, and tag `v0.2.0`. Pushing, publishing, uploading, or creating a hosted release requires separate explicit approval for that action.

---

## 6. Release scope

### 6.1 Included

Release `0.2.0` includes:

- persistent interactive WMS console;
- start menu for standalone launch;
- read-only database lifecycle;
- item, location, inventory, workflow, and transaction inquiry;
- all standard WMS reports;
- readable terminal tables and vertical detail output;
- deterministic CSV export;
- transaction and command tracing;
- protected sandbox clone/create workflow;
- CSV templates, validation, preview, and batch result artifacts;
- atomic inventory-adjustment CSV application;
- atomic replenishment-control CSV application;
- portable Windows x64 application bundle;
- source release archive;
- release manifests and SHA-256 checksums;
- clean source and clean standalone reproduction tests;
- user documentation and quick-start materials; and
- local Git tag `v0.2.0` after acceptance.

### 6.2 Writable CSV types

Only these CSV maintenance types are writable in `0.2.0`:

1. **Inventory adjustments**
   - signed case quantity changes;
   - approved adjustment reason;
   - location and item validation;
   - ordinary adjustment workflow;
   - immutable inventory transaction audit.

2. **Pick-location replenishment controls**
   - minimum quantity;
   - reorder trigger;
   - target quantity;
   - maximum quantity;
   - dynamic physical maximum validation;
   - no inventory movement.

### 6.3 Export-only data

The console may export, but may not bulk-update, the following in `0.2.0`:

- `item_master`;
- `location_master`;
- full `inventory_master` extracts;
- `inventory_transaction`;
- picks;
- replenishment tasks;
- QA events;
- adjustment history;
- snapshots; and
- standard-report outputs.

---

## 7. Explicit exclusions

Release `0.2.0` does not include:

- a graphical desktop or browser interface;
- web services or cloud hosting;
- authentication, user accounts, or enterprise authorization;
- multi-user concurrency;
- arbitrary SQL execution inside the console;
- direct CSV-to-table updates;
- item-master or location-master mutation;
- new item or location creation;
- item re-slotting or reassignment;
- code-date-only maintenance;
- receiving, ASN, putaway, shipping, route accounting, or carrier interfaces;
- pallet or handling-unit lifecycle;
- new investigation scenarios;
- model refitting or changes to frozen `0.1.0` findings;
- automatic ground-truth reveal;
- installer/MSI creation;
- automatic updates;
- telemetry; or
- claims that the toolkit is a production enterprise WMS.

---

## 8. Release phase roadmap

| Phase | Name | Primary outcome |
|---:|---|---|
| 0 | Preservation, audit, and release contracts | `0.1.0` remains safe; console, CSV, sandbox, and Windows packaging contracts are implementation-ready. |
| 1 | Interactive console foundation | Persistent console, launch menu, read-only database sessions, help, status, validation, and safe terminal behavior. |
| 2 | Inquiry, reports, export, and trace | Practical WMS exploration without SQL or long one-shot commands. |
| 3 | Sandbox lifecycle and write protection | Verified writable copies with clear provenance and structural source protection. |
| 4 | CSV templates, validation, and preview | Excel-friendly maintenance files with deterministic, non-mutating previews. |
| 5 | Inventory-adjustment batch application | Atomic, idempotent bulk adjustments through ordinary WMS commands. |
| 6 | Replenishment-control batch application | Atomic, auditable maintenance of pick-slot replenishment settings. |
| 7 | Standalone Windows application | Portable Windows x64 bundle requiring no Python, `uv`, or VS Code. |
| 8 | Usability acceptance and release | Full source and standalone reproduction, documentation, archives, checksums, and local `v0.2.0` tag. |

### 8.1 Release progression

```text
Preserve 0.1.0
    -> freeze console and packaging contracts
    -> persistent read-only console
    -> WMS inquiry, reports, exports, and trace
    -> protected sandbox lifecycle
    -> CSV templates, validation, and preview
    -> inventory-adjustment apply
    -> replenishment-control apply
    -> standalone Windows bundle
    -> clean reproduction and release 0.2.0
```

---

## 9. Cross-phase console contract

### 9.1 User modes

#### No database open

```text
WMS[NO DB]>
```

Allowed commands:

- `open`;
- `sample`;
- `clone` when a source path is provided;
- `help`;
- `version`;
- `history`;
- `clear`; and
- `exit`.

#### Read-only mode

```text
WMS[RO:warehouse]>
```

Allowed:

- inquiry;
- reports;
- exports;
- validation;
- description;
- transaction tracing;
- session configuration; and
- sandbox cloning.

Prohibited:

- CSV apply;
- inventory mutation;
- replenishment-control mutation; and
- arbitrary SQL.

#### Sandbox-write mode

```text
WMS[RW:training_sandbox]>
```

Allowed:

- all read-only behavior;
- CSV template generation;
- CSV validation and preview;
- approved CSV batch application;
- post-change validation;
- snapshot creation where required by the batch workflow; and
- trace of newly created commands and transactions.

### 9.2 Command grammar

Command verbs should be case-insensitive. Canonical identifiers should be normalized according to existing WMS rules rather than guessed by the formatter.

Recommended command surface:

```text
open <database> [--read-only]
open-sandbox <database>
sample
close
clone <source> <destination>
status
validate
describe
version
help [command]
history
clear
exit
quit

item <item-id>
location <location-id>
inventory location <location-id>
inventory item <item-id>
inventory empty
inventory needs

trip <trip-id>
pick <pick-event-id>
replenishment <task-id>
qa <qa-event-id>
adjustment <adjustment-id>
transactions item <item-id>
transactions location <location-id>
transactions group <transaction-group-id>
transactions command <command-id>
trace <command-id | transaction-group-id | source-record-id>

reports
report <report-name> [parameters]
export report <report-name> <path> [parameters]
export item-master <path>
export location-master <path>
export inventory-master <path>
export inventory-transactions <path> [filters]

csv template inventory-adjustments <path>
csv template replenishment-controls <path>
csv validate <path> --type <type>
csv preview <path> --type <type>
csv apply <preview-batch-id-or-manifest>

set limit <n>
set format table|vertical
set output-directory <path>
set timestamps utc|local|both
show settings
```

Equivalent one-shot commands should be exposed for automation and testing where practical.

### 9.3 Terminal presentation

- Detail records default to vertical key/value output.
- Multi-row output uses width-aware tables.
- The default result limit is `25` unless owner review chooses another value.
- Wide reports should show a useful subset of columns and explain how to export the full data.
- CSV export always includes the full canonical field set for the selected export.
- Output must remain understandable when ANSI styling is unavailable.
- Redirected output must not contain terminal-control characters.
- Fatal startup errors from a double-click launch must remain visible long enough to read rather than closing immediately.

### 9.4 Path behavior

- Paths with spaces must work.
- Relative paths entered inside the console resolve against the session working directory shown by `status`.
- The standalone application must not assume the current directory is the executable directory.
- Bundled resources are resolved from the application bundle location.
- User-created data and exports must not be written inside immutable packaged runtime directories unless the user explicitly selects a writable path.
- Existing files are never overwritten without an explicit approved overwrite workflow; default behavior is refusal.

---

## 10. Cross-phase CSV contract

### 10.1 Common requirements

All supported maintenance CSV files must have:

- a documented CSV contract version;
- stable headers;
- UTF-8 and UTF-8-with-BOM input support;
- deterministic normalization;
- explicit integer parsing;
- blank-value rules;
- unique stable row references;
- row-level validation results;
- safe handling of spreadsheet formula-like text;
- a canonical normalized representation for hashing; and
- clear separation between user-entered notes and operational identifiers.

### 10.2 Inventory-adjustment conceptual fields

Exact technical names must match the accepted WMS schema and existing adjustment service after the Phase 0 audit. The template must represent at least:

- row reference;
- location ID;
- item ID;
- signed quantity delta in cases;
- adjustment reason code;
- optional user note;
- expected current quantity;
- expected current item assignment; and
- expected last-change reference or equivalent state token.

The expected-state fields are used to detect stale spreadsheet edits and protect against applying a preview to changed inventory.

### 10.3 Replenishment-control conceptual fields

The template must represent at least:

- row reference;
- pick location ID;
- current item ID;
- proposed minimum cases;
- proposed reorder-trigger cases;
- proposed target cases;
- proposed maximum cases;
- expected current control values;
- expected current item assignment; and
- optional user note.

### 10.4 Batch identity

A batch ID should be derived from a canonical payload containing at least:

- workflow type;
- CSV contract version;
- normalized rows in stable order;
- source database run identity;
- source database schema version; and
- source state fingerprint relevant to the proposed changes.

Do not use Python `hash()` or nondeterministic filesystem metadata.

### 10.5 Preview artifacts

Each preview should produce a new directory such as:

```text
workspace/batches/<batch-id>/
    source_input.csv
    normalized_input.csv
    validation_results.csv
    proposed_changes.csv
    summary.json
    preview_manifest.json
```

A successful apply extends that directory or creates a linked result directory containing:

```text
    apply_results.csv
    command_map.csv
    post_apply_summary.json
    post_apply_manifest.json
```

### 10.6 Apply rule

The public apply workflow must consume an accepted preview manifest or batch ID. It must not silently create and apply an unseen preview in one noninteractive step.

For automation, a one-shot command may run validation and preview first, but it must stop unless an explicit confirmation token matching the generated preview is supplied.

---

## 11. Cross-phase standalone Windows contract

### 11.1 Distribution format

The required artifact is a versioned portable ZIP:

```text
Operational-Variance-Toolkit-0.2.0-Windows-x64.zip
```

Recommended extracted layout:

```text
Operational-Variance-Toolkit-0.2.0-Windows-x64/
    OperationalVarianceToolkit.exe
    runtime/
    sample-data/
        schema3_baseline.sqlite3
    templates/
    workspace/
        exports/
        sandboxes/
        batches/
    docs/
        QUICK_START.txt
        CONSOLE_COMMAND_REFERENCE.md
        CSV_WORKFLOW_GUIDE.md
    LICENSE
    CHANGELOG.md
    RELEASE_NOTES_0.2.0.md
    THIRD_PARTY_NOTICES.txt
    VERSION.txt
    RELEASE_MANIFEST.json
    SHA256SUMS.txt
```

The exact private runtime layout depends on the selected packager and may differ. The user-facing files and directories should remain obvious.

### 11.2 Packaging technology

Phase 0 must perform a bounded feasibility spike and select the packaging tool based on actual compatibility with:

- Python 3.14;
- the final terminal/input libraries;
- SQLite;
- Pandas, Statsmodels, Matplotlib, notebook/reporting dependencies already in the project;
- bundled data files; and
- Windows x64.

The roadmap does not preselect a packager without a successful proof. The selection and rationale must be recorded in the decision log.

### 11.3 Standalone acceptance meaning

“Standalone” means:

- no Python installation required;
- no `uv` installation required;
- no VS Code required;
- no repository checkout required;
- no environment-variable configuration required for normal launch;
- no internet required after extraction; and
- no dependency installation performed on first run.

### 11.4 Sample data

The portable bundle must include at least one safe schema-3 baseline database that opens read-only from the start menu.

The primary Windows bundle must not include restricted ground truth. An investigation example may be included only if it passes the same leakage review and materially improves the user experience; it is not required.

### 11.5 Windows-specific behavior

Test at minimum:

- double-click launch;
- PowerShell launch;
- Command Prompt launch;
- execution from a path containing spaces;
- extraction to a non-repository directory;
- read-only sample database;
- creation of sandbox and exports under the portable workspace;
- CSV workflow using a file edited and saved by Excel where practical;
- correct handling of Windows line endings;
- graceful shutdown;
- no orphan temporary files after normal exit;
- readable fatal error behavior; and
- Windows Defender/signing limitations documented honestly if the unsigned local executable produces a warning.

Code signing is not required for `0.2.0`.

---

# Detailed Phase Implementation Outlines

---

## Phase 0 — Preservation, audit, and release contracts

### 0.1 Purpose

Establish a safe development starting point, inspect the actual repository before designing around assumptions, and prove that a standalone Windows build is feasible before committing the release to a particular console or packaging library.

### 0.2 Prerequisites

- `v0.1.0` exists and points to the accepted release commit.
- Working tree is clean.
- Source and optional truth archives from `0.1.0` are preserved outside active development where practical.
- Current full test and quality gates are known.

### 0.3 Target state

At Phase 0 completion:

- `0.1.0` remains untouched and reproducible;
- a dedicated `0.2.0` development branch exists;
- the current CLI, WMS services, report registry, storage interfaces, command IDs, and release packaging code are mapped;
- the console dependency decision is documented;
- the Windows packaging tool is selected through a working spike;
- the standalone bundle format is frozen as a portable Windows x64 ZIP;
- sandbox and CSV contracts are frozen sufficiently for implementation; and
- Phase 1 can begin without unresolved architecture questions.

### 0.4 Required work

#### Preservation

1. Confirm:
   - current branch;
   - clean working tree;
   - final `0.1.0` commit;
   - tag `v0.1.0`;
   - local release archive hashes.
2. Create a branch such as:

```text
feature/release-0.2.0-console
```

3. Do not move, delete, or retag `v0.1.0`.
4. Record the starting full-suite test count and runtimes.

#### Repository audit

Inspect and document:

- CLI entry points and parser organization;
- current version lookup;
- schema-version routing;
- WMS service interfaces;
- unit-of-work and transaction boundaries;
- report registry and filter contracts;
- read-only database helpers;
- adjustment command and result records;
- replenishment-control fields and validators;
- command idempotency storage;
- available command/workflow history;
- snapshot service behavior;
- package-resource handling;
- release packaging and checksum code;
- current dependencies and license obligations; and
- existing tests that can be reused for the console.

The audit must identify where the roadmap’s conceptual fields differ from actual canonical names.

#### Console dependency spike

Evaluate whether the standard library is sufficient or whether a focused terminal dependency is justified.

The evaluation should cover:

- persistent prompt;
- command history;
- tab completion;
- Windows terminal behavior;
- width detection;
- readable tables;
- redirected output;
- testability; and
- standalone packaging.

Do not add both a formatting framework and an input framework unless each provides direct value.

#### Windows packaging feasibility spike

Create the smallest throwaway build that can:

- print the installed project version;
- open a schema-3 SQLite database read-only;
- run one standard report;
- write one CSV export to a temporary directory; and
- launch without Python or `uv` on the execution path.

This spike is not the release build. It proves compatibility and informs the packaging ADR.

#### Schema and audit decision

Determine whether existing schema-3 command/history structures can support:

- CSV batch metadata;
- row-to-command mapping; and
- replenishment-control maintenance history.

Preferred outcomes, in order:

1. reuse existing generic command/history structures without semantic abuse;
2. add narrowly scoped audit tables through a documented additive schema version for writable sandboxes; or
3. use a sidecar batch manifest only for console metadata while all WMS changes remain fully auditable in existing operational files.

If an additive schema version is required:

- accepted schema `3.0.0` source databases remain read-only;
- sandbox cloning performs an explicit transactional upgrade;
- compatibility remains version-routed;
- no completed source artifact is migrated in place; and
- the new version is documented before implementation.

#### Contract freeze

Finalize:

- console mode names;
- command grammar;
- default result limit;
- path resolution rules;
- protected database rules;
- sandbox manifest format;
- supported CSV headers;
- blank and expected-state semantics;
- batch identity algorithm inputs;
- preview artifact structure;
- apply confirmation rule;
- Windows bundle layout; and
- quick-start launch behavior.

### 0.5 Anticipated documentation changes

Update or create:

- this document;
- `PROJECT_STATUS.md`;
- decision log entries for console libraries, Windows packager, portable ZIP distribution, and sandbox metadata;
- a bounded current-interface audit for `0.2.0`; and
- requirement traceability additions.

### 0.6 Tests and verification

Run the complete existing gate before and after Phase 0 documentation/dependency changes:

```powershell
uv sync --frozen
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Verify the packaging spike outside the repository in a fresh temporary directory.

### 0.7 Acceptance criteria

Phase 0 passes when:

- `v0.1.0` is unchanged;
- full `0.1.0` regression remains green;
- no accepted artifact was modified;
- a Windows executable spike runs without Python or `uv` on the execution path;
- the selected console and packaging dependencies have acceptable licenses and bundle successfully;
- all binding contracts listed above are documented; and
- exact Phase 1 source/test changes are known.

### 0.8 Owner checkpoint

Review at this checkpoint is limited to the user-facing decisions:

- portable ZIP rather than installer;
- start-menu wording;
- prompt mode labels;
- high-level command vocabulary; and
- whether the sample baseline should open automatically or through menu selection.

Routine dependency and module choices remain engineering decisions unless they materially alter the user experience.

### 0.9 Progression prerequisites

Do not begin production console work if the packaging spike cannot produce a reliable Windows build. Resolve packaging feasibility first rather than building an interface that cannot be distributed.

---

## Phase 1 — Interactive console foundation

### 1.1 Purpose

Create the persistent console, standalone start menu, command parser, session state, and safe read-only database lifecycle.

### 1.2 Prerequisites

- Phase 0 accepted.
- Console and packaging dependencies selected.
- Session and path contracts frozen.
- Existing one-shot CLI behavior green.

### 1.3 Target state

A user can launch the console from source or the packaging-development executable, open a compatible schema-3 database read-only, inspect status, validate or describe it, close it, and exit cleanly.

### 1.4 Required capabilities

#### Public source command

```powershell
uv run operational-variance-toolkit console [--database <path>]
```

Recommended optional flags:

```text
--database <path>
--sample
--output-directory <path>
--no-style
```

Do not expose write mode through a general startup flag in Phase 1.

#### Start menu

When launched without a database:

- show application name and version;
- offer sample database, file selection/path entry, help, and exit;
- remain usable without a mouse;
- show clear errors for missing or invalid paths; and
- fall through into the same console session used by command-line launch.

A native graphical file picker is optional and should not be added unless it packages reliably and does not complicate testing. Typed or pasted paths are sufficient for initial acceptance.

#### Session state

The session model should track:

- active database path;
- active connection lifecycle;
- schema version;
- run ID;
- facility identity;
- mode;
- validation status and time checked;
- session working directory;
- output directory;
- result limit;
- display format;
- timestamp preference; and
- source or sandbox provenance when later available.

Session state must be explicit and testable, not module-level mutable globals.

#### Core commands

Implement:

```text
open <database>
sample
close
status
validate
describe
version
help [command]
history
clear
exit
quit
```

#### Read-only protections

- Open the active database using a read-only SQLite URI where supported.
- Enable query-only protection.
- Do not retain a writable connection accidentally through validators or report services.
- Close connections deterministically on `close`, `exit`, EOF, and fatal session errors.
- Verify the database hash is unchanged after representative sessions.

#### Parser behavior

- Use one parser/dispatch system for source and packaged execution.
- Support quoted paths with spaces.
- Keep command verbs case-insensitive.
- Preserve argument case where paths or free text require it.
- Return concise usage help for expected mistakes.
- Do not swallow unexpected programming errors during development tests.

#### Terminal behavior

- Ctrl+C cancels the current input or command and returns to the prompt without corrupting session state.
- EOF exits cleanly.
- `clear` uses a portable abstraction.
- History is local and contains commands only, never database secrets or restricted truth.
- History persistence should be bounded and stored in a user-writable application workspace, not the source repository.
- Styling degrades safely when ANSI is unavailable.

### 1.5 Suggested module boundaries

A likely structure is:

```text
src/operational_variance_toolkit/console/
    __init__.py
    application.py
    commands.py
    completion.py
    formatting.py
    parser.py
    session.py
    startup.py
```

Exact names may change after the audit. The boundaries matter more than matching this tree.

Rules:

- parsing does not open databases;
- formatting does not query storage;
- session state does not contain WMS business rules;
- command handlers call public application/read services;
- startup menu and persistent prompt share the same session application.

### 1.6 Testing

#### Unit tests

- parser happy paths;
- quoted paths;
- missing arguments;
- unknown commands;
- session transitions;
- prompt labels;
- settings defaults;
- Ctrl+C and EOF handling;
- output with and without styling.

#### Integration tests

- open valid schema-3 database;
- reject missing/corrupt/unsupported database;
- validate active database;
- describe active database;
- close and reopen;
- source checksum unchanged;
- repeated open closes prior connection safely;
- standalone-style resource resolution using a temporary bundle directory.

#### CLI regression

All existing one-shot commands remain green.

### 1.7 Acceptance criteria

Phase 1 passes when:

- source console launches successfully;
- packaging-development executable launches the same console;
- start menu works;
- valid schema-3 databases open read-only;
- protected source bytes remain unchanged;
- invalid databases produce useful errors;
- session commands behave predictably;
- no WMS mutation path exists;
- tests and quality gates pass; and
- `PROJECT_STATUS.md` records exact results.

### 1.8 Owner review

Items for usability review:

- double-click startup flow;
- startup banner;
- prompt labels;
- `status` output;
- help style;
- errors for invalid file paths; and
- exit behavior.

This is a usability review, not an architecture review.

### 1.9 Progression prerequisites

Do not add WMS inquiry by embedding SQL in console handlers. Phase 2 begins only after the console lifecycle is stable and read-only protection is proven.

---

## Phase 2 — WMS inquiry, reports, export, and transaction trace

### 2.1 Purpose

Turn the console into a useful WMS explorer by exposing ordinary operational records, the standard report registry, practical CSV exports, and coherent command/transaction tracing.

### 2.2 Prerequisites

- Stable read-only console from Phase 1.
- Existing report services and schema-3 read models audited.
- Canonical field names known.

### 2.3 Target state

A warehouse or WMS analyst can inspect the system without writing SQL and without repeatedly invoking long PowerShell commands.

### 2.4 Required work

#### Detail inquiry

Implement typed inquiry services and console commands for:

```text
item <item-id>
location <location-id>
inventory location <location-id>
inventory item <item-id>
trip <trip-id>
pick <pick-event-id>
replenishment <task-id>
qa <qa-event-id>
adjustment <adjustment-id>
```

Detail output should:

- use user-friendly labels;
- retain canonical technical field names in an optional technical view;
- show “not found” distinctly from database errors;
- show related identifiers that can be traced next; and
- avoid presenting hidden physical state or restricted truth.

#### Transaction inquiry

Implement:

```text
transactions item <item-id>
transactions location <location-id>
transactions group <transaction-group-id>
transactions command <command-id>
```

Support stable ordering and bounded result limits.

Filters should route through approved query services. Do not generate arbitrary SQL fragments from user input.

#### Standard reports

Implement:

```text
reports
report <report-name> [parameters]
```

All 12 accepted report names must remain available:

- `inventory-by-location`;
- `inventory-by-item`;
- `location-profile`;
- `empty-locations`;
- `code-date-inventory`;
- `replenishment-needs`;
- `open-replenishment-tasks`;
- `inventory-transaction-inquiry`;
- `adjustment-history`;
- `qa-activity`;
- `inventory-snapshot`; and
- `inventory-reconciliation`.

Console report results must match one-shot CLI results for equivalent parameters.

#### Presentation

Implement:

- vertical detail display;
- width-aware row tables;
- stable truncation and continuation guidance;
- row count and active limit;
- optional totals where the underlying report already defines them;
- `set limit`;
- `set format`;
- timestamp presentation setting; and
- full CSV export for wide results.

The console must not invent new report arithmetic merely for display.

#### CSV export

Implement:

```text
export report <report-name> <path> [parameters]
export item-master <path>
export location-master <path>
export inventory-master <path>
export inventory-transactions <path> [filters]
```

Exports must:

- use stable column order;
- use UTF-8 with a documented Excel-compatible choice;
- preserve canonical values;
- refuse accidental overwrite;
- write through a temporary file and atomic rename where practical;
- calculate and display SHA-256;
- report row count and destination; and
- encode hazardous strings in every spreadsheet-facing CSV column, including identifiers and references, as literal text; retain numeric values and stored canonical identifiers unchanged.

#### Trace

Implement the flagship command:

```text
trace <command-id | transaction-group-id | source-record-id>
```

Trace should resolve and display, where applicable:

- command ID;
- operation type;
- source workflow record;
- item;
- operator;
- operational event time;
- WMS recorded time;
- transaction group;
- all transaction lines;
- before and after balances;
- net quantity effect;
- final live location state;
- related snapshot or validation references; and
- balanced/conserved status for transfers.

It must distinguish:

- quantity-changing commands;
- workflow commands with no inventory delta;
- QA observations;
- replenishment lifecycle steps; and
- snapshot captures.

### 2.5 Example transfer trace

```text
Transaction Group: TXG-000475
Command: BASE-REPL-CONFIRM-000001
Workflow: REPL-000473
Operation: Replenishment Confirmation
Item: ITEM-0048
Operator: OP-0019

Source
  Location: LOC-05048
  Transaction: TXN-000475-01
  Balance: 15 -> 9
  Delta: -6

Destination
  Location: LOC-00048
  Transaction: TXN-000475-02
  Balance: 3 -> 9
  Delta: +6

Net Group Delta: 0
Status: BALANCED
```

### 2.6 Testing

#### Parity tests

- inquiry results versus direct repository fixtures;
- report console versus one-shot CLI;
- report console versus approved SQL expectations;
- export bytes reproducible for identical inputs;
- export row/column counts;
- trace arithmetic hand-checked for pick, transfer, and adjustment.

#### Safety tests

- no source database mutation;
- no ground-truth imports;
- filter injection attempts rejected;
- path traversal or unsafe output names rejected where applicable;
- overwrite refusal;
- formula-like free text safely exported.

#### Usability tests

Use scripted console sessions rather than brittle screenshots. Assert semantic output fields and relationships.

### 2.7 Acceptance criteria

Phase 2 passes when:

- ordinary WMS inquiry works without SQL;
- all 12 reports are available;
- wide reports are usable in the terminal and complete in CSV;
- trace works for each supported workflow class;
- exports open correctly in Excel during a manual spot check;
- source databases remain byte-identical;
- report and trace parity tests pass;
- all prior tests remain green; and
- documentation contains a preliminary command reference.

### 2.8 Owner checkpoint A — Console usefulness

Review is required for:

- Item detail;
- location detail;
- inventory by location;
- transaction inquiry;
- `replenishment-needs` report;
- one pick trace;
- one replenishment trace;
- one adjustment trace;
- table width and labels; and
- CSV export opened in Excel.

Acceptance focuses on whether the interface feels like a credible WMS console rather than a developer wrapper.

### 2.9 Progression prerequisites

Do not enable writes or add arbitrary SQL. Phase 3 begins only after the read-only console is genuinely useful.

---

## Phase 3 — Sandbox lifecycle and write protection

### 3.1 Purpose

Create a safe writable environment that preserves source databases and makes write capability explicit, visible, and auditable.

### 3.2 Prerequisites

- Phase 2 accepted.
- Read-only source protection proven.
- Sandbox metadata decision from Phase 0 finalized.

### 3.3 Target state

A user can clone a compatible WMS into a new sandbox, verify provenance, open it in visibly marked write mode, and perform all read-only operations without changing the original source.

### 3.4 Required work

#### Clone command

Support:

```text
clone <source-database> <destination-database>
```

From an active session, a shorter form may use the active database as the source:

```text
clone <destination-database>
```

Clone behavior:

1. validate source path and schema;
2. calculate source SHA-256;
3. refuse existing destination;
4. use a safe SQLite backup/copy method appropriate to finalized databases;
5. verify copied database integrity;
6. apply any approved sandbox-only additive schema upgrade transactionally;
7. write sandbox provenance metadata;
8. calculate initial sandbox SHA-256;
9. validate the sandbox;
10. open it in write mode only after success; and
11. remove incomplete outputs on failure.

#### Sandbox identity

The application must verify the sandbox each time it is opened for write.

A valid sandbox requires:

- expected manifest structure;
- destination database existence;
- matching run/schema identity;
- recognized creation version;
- no prohibited source path reuse;
- successful database integrity check; and
- any required schema upgrade present.

The manifest is a safety mechanism, not a cryptographic security boundary. Tampering should cause refusal or require deliberate re-cloning.

#### Write-mode entry

Support:

```text
open-sandbox <database>
```

or an equivalent explicit command selected in Phase 0.

On first write-capable action in a session, display:

```text
You are operating a writable sandbox copy.
Source databases and accepted release artifacts remain protected.
Changes will be recorded in this sandbox and cannot be automatically undone.
Type APPLY TO SANDBOX to continue:
```

The exact confirmation phrase may be shortened during usability review, but a plain accidental Enter must not authorize writes.

#### Source protection

The application must reject write mode for:

- accepted release database paths listed in protected release metadata;
- bundled sample databases;
- databases without valid sandbox provenance;
- schema versions unsupported for write workflows;
- databases currently open read-only through another session object; and
- source and destination resolving to the same file.

#### Sandbox status

`status` in sandbox mode should show:

- mode;
- sandbox path;
- source database identity;
- source checksum;
- sandbox creation version/time;
- current sandbox checksum or state revision;
- supported write workflow types; and
- latest applied batch, if any.

### 3.5 No operational writes yet

Phase 3 does not add adjustment or control update commands. It creates the safe lifecycle and mode boundary only.

### 3.6 Testing

- clone finalized database;
- source hash unchanged;
- sandbox canonical WMS content initially equivalent;
- protected sample cannot open write mode;
- renamed source file does not become a sandbox;
- invalid/tampered manifest rejected;
- failed copy leaves no partial destination;
- path with spaces works;
- sandbox can reopen after application restart;
- schema upgrade, if used, is atomic and version-routed;
- all read-only reports work on the sandbox;
- source and sandbox connections are not confused.

### 3.7 Acceptance criteria

Phase 3 passes when:

- a source can be cloned safely;
- source checksum remains unchanged;
- sandbox provenance is recorded and verified;
- write mode is impossible for an ordinary source database;
- the prompt visibly shows sandbox write mode;
- failed clones clean up safely;
- the sandbox remains a valid WMS; and
- all quality gates pass.

### 3.8 Owner review

Review is required for:

- clone command wording;
- write-mode warning;
- `status` provenance display; and
- distinction between bundled sample, source WMS, and sandbox.

### 3.9 Progression prerequisites

Do not add a generic “force write” override. If a database cannot be verified as a sandbox, the user must clone it through the approved workflow.

---

## Phase 4 — CSV templates, validation, and preview

### 4.1 Purpose

Build the reusable, non-mutating CSV workflow used by both supported maintenance types.

### 4.2 Prerequisites

- Verified sandbox lifecycle.
- Canonical CSV fields finalized from the actual schema and services.
- Batch identity and result-artifact formats frozen.

### 4.3 Target state

A user can generate an Excel-friendly template, edit it, validate every row, and inspect the exact proposed changes without modifying the sandbox.

### 4.4 Required work

#### CSV package boundaries

Suggested structure:

```text
src/operational_variance_toolkit/csv_workflows/
    __init__.py
    contracts.py
    export.py
    parsing.py
    normalization.py
    validation.py
    preview.py
    identity.py
    results.py
```

Responsibilities:

- serialization code knows CSV mechanics, not WMS rules;
- typed workflow validators call WMS read/domain services;
- preview uses the same domain semantics as apply;
- result writers do not mutate WMS state;
- console handlers only coordinate the workflow and render summaries.

#### Template generation

Support:

```text
csv template inventory-adjustments <path>
csv template replenishment-controls <path>
```

Also expose one-shot equivalents.

Template options may include:

- blank template;
- template populated from selected locations/items; and
- template populated from a report filter.

The blank template is required. Populated templates are recommended because they reduce typing and carry expected-state values.

#### Parsing and normalization

Handle:

- UTF-8;
- UTF-8 BOM;
- CRLF and LF;
- quoted commas;
- blank trailing lines;
- whitespace around values;
- strict required headers;
- clear unknown-header behavior;
- integer values only where required;
- stable reason-code normalization;
- duplicate row references;
- duplicate targeted records; and
- formula-like content in free-text fields.

The normalized file written by the application is authoritative for batch hashing.

#### Validation layers

**File-level validation**

- readable file;
- accepted encoding;
- correct contract type/version;
- required headers exactly once;
- no duplicate row references;
- at least one data row;
- bounded row count and file size.

**Row-level syntactic validation**

- required values present;
- identifiers parse;
- quantities parse as integers;
- reason codes allowed;
- notes within length limits;
- no unsupported formulas or control characters.

**WMS-state validation**

Inventory adjustments:

- location exists and is active for inventory;
- current item matches expected item;
- quantity delta is nonzero;
- resulting quantity is nonnegative;
- resulting quantity does not exceed dynamic physical maximum;
- reason is valid for adjustment service;
- expected quantity/state token matches current state.

Replenishment controls:

- location is an active pick location;
- assigned item matches expected item;
- all four control values are valid integers;
- `minimum <= trigger <= target <= maximum`;
- maximum does not exceed dynamic physical maximum;
- proposed values differ from current values;
- expected current controls/state token match.

#### Preview

Preview must:

- perform no database writes;
- create deterministic batch ID;
- display current and proposed values;
- show total proposed quantity change for adjustments;
- show affected locations/items;
- show validation counts;
- show warnings separately from failures;
- record source database fingerprint;
- record relevant per-row state tokens;
- write preview artifacts to a new batch directory; and
- end with a clear statement that no changes were applied.

Example adjustment preview summary:

```text
Batch: BATCH-...
Workflow: Inventory Adjustments
Rows read: 18
Valid rows: 18
Rejected rows: 0
Affected locations: 11
Net proposed quantity change: -42 cases
Negative balances: 0
Capacity violations: 0
Database modified: NO
```

### 4.5 Preview/apply separation

A successful preview manifest must include everything needed to prove what the user reviewed. Editing the source CSV after preview must not alter the accepted batch. The user must preview the edited file again.

### 4.6 Testing

#### Parser tests

- BOM and no BOM;
- CRLF and LF;
- quoted commas;
- missing/extra headers;
- duplicates;
- blank values;
- invalid integers;
- large/negative values;
- formula-like notes;
- deterministic normalization.

#### Validation tests

- valid adjustment;
- negative resulting inventory;
- item mismatch;
- missing location;
- stale expected quantity;
- valid replenishment controls;
- invalid ordering;
- maximum above dynamic capacity;
- reserve location targeted as pick;
- unchanged control row.

#### Preview tests

- zero database changes;
- deterministic batch ID;
- changed file changes batch ID;
- changed relevant database state invalidates preview identity;
- stable artifact bytes except documented execution metadata;
- useful row-level reasons;
- no ground-truth loading.

### 4.7 Acceptance criteria

Phase 4 passes when:

- both templates open and save correctly in Excel;
- both valid templates normalize reproducibly;
- invalid rows receive actionable reasons;
- preview arithmetic matches WMS domain services;
- no preview modifies the sandbox;
- batch identity is deterministic;
- preview artifacts are complete and traceable; and
- all tests and quality gates pass.

### 4.8 Owner checkpoint B — CSV usefulness

Review is required for:

- exact template headers;
- adjustment reason vocabulary;
- populated-template usefulness;
- row-level validation messages;
- preview summary;
- proposed-change CSV; and
- whether the workflow resembles real WMS implementation/maintenance practice.

### 4.9 Progression prerequisites

Apply implementation requires understandable preview results and prior product-owner approval of the templates. Preview is a user-control boundary, not a hidden internal step.

---

## Phase 5 — Inventory-adjustment CSV application

### 5.1 Purpose

Apply approved inventory-adjustment batches atomically through the existing WMS adjustment service while preserving full row, command, transaction, and final-state traceability.

### 5.2 Prerequisites

- Phase 4 preview accepted.
- Adjustment service and unit-of-work boundaries audited.
- Sandbox supports any required batch metadata/history structures.

### 5.3 Target state

A user can apply an accepted adjustment preview to a sandbox. Every row creates the same ordinary WMS records that a direct valid adjustment command would create, and no source database is touched.

### 5.4 Apply workflow

```text
csv apply <preview-batch-id-or-manifest>
```

Required sequence:

1. load preview manifest;
2. verify workflow type;
3. verify manifest and artifact checksums;
4. verify active database is the same verified sandbox;
5. verify batch has not already been applied;
6. reload all affected live records;
7. compare current state with preview state tokens;
8. rerun all validations;
9. display final apply summary;
10. require explicit sandbox confirmation;
11. begin one database transaction for the complete batch;
12. submit each deterministic adjustment command through the public WMS service;
13. write batch/row mapping metadata through the approved audit mechanism;
14. create a post-batch inventory snapshot if required to keep live-versus-latest-snapshot reporting coherent;
15. commit;
16. run post-apply validation;
17. produce result artifacts; and
18. display command IDs and follow-up trace instructions.

Any failure from step 11 through commit must roll back every row and any batch snapshot.

### 5.5 Adjustment semantics

Each accepted row must produce:

- one accepted adjustment workflow record;
- one immutable inventory transaction row with signed delta;
- updated `inventory_master` quantity;
- updated last-change references;
- deterministic command identity;
- link to source batch and row; and
- final balance matching preview.

The batch workflow must not invent a second adjustment implementation.

### 5.6 Snapshot and reconciliation behavior

Because a successful sandbox batch changes live inventory after the original generated closing snapshot, the application must preserve understandable reconciliation.

The preferred behavior is to create a clearly labeled post-maintenance snapshot after a successful adjustment batch. The snapshot should:

- capture all live locations;
- reference the batch or command group;
- occur after all adjustment transactions;
- remain factual WMS state;
- not rewrite prior snapshots; and
- become selectable by standard reconciliation and reconstruction workflows.

If the existing WMS snapshot contract provides a better equivalent, use it and document the choice.

### 5.7 Apply result artifacts

Produce at least:

- final normalized input checksum;
- apply result per row;
- row-to-command map;
- row-to-adjustment/transaction map;
- post-apply balances;
- post-batch snapshot ID where applicable;
- pre/post database checksum;
- validation summary;
- applied-by application version; and
- idempotency status.

### 5.8 Idempotency

Reapplying the same batch must either:

- return the original successful batch result without changing inventory; or
- fail with a clear duplicate-batch message and no changes.

Use the existing project-wide idempotency approach where possible.

### 5.9 Testing

#### Happy path

- one-row positive adjustment;
- one-row negative adjustment;
- mixed multi-row batch;
- multiple rows across different locations;
- post-batch snapshot/reconciliation;
- trace each new command.

#### Failure and rollback

- stale preview;
- invalid state after preview;
- duplicate command ID;
- injected failure on middle row;
- injected failure before snapshot;
- injected failure during result metadata write;
- negative inventory;
- capacity violation;
- read-only source accidentally active;
- database connection interruption where testable.

#### Idempotency

- same batch twice;
- semantically same file with harmless formatting differences;
- changed note or operational value according to frozen hashing rules;
- same batch against a different sandbox.

#### Reconciliation

- opening plus all transactions equals live inventory;
- live inventory equals selected post-batch snapshot;
- reconstruction includes new adjustment rows exactly once;
- source database checksum unchanged.

### 5.10 Acceptance criteria

Phase 5 passes when:

- a valid batch applies atomically;
- every row uses the existing adjustment service;
- every quantity change has immutable audit;
- failed batches leave no operational or metadata residue;
- duplicate apply cannot double-post;
- post-batch validation and reconstruction are coherent;
- new changes are visible through inquiry, reports, export, and trace;
- source databases remain unchanged; and
- full regression passes.

### 5.11 Owner review

Owner acceptance includes completion of one real spreadsheet workflow:

1. generate populated adjustment template;
2. edit quantities/reasons in Excel;
3. save;
4. validate;
5. preview;
6. inspect proposed changes;
7. apply to sandbox;
8. run inventory report; and
9. trace one adjustment.

### 5.12 Progression prerequisites

Do not support partial posting in `0.2.0`. A batch is accepted as a whole or not applied.

---

## Phase 6 — Replenishment-control CSV application

### 6.1 Purpose

Add safe bulk maintenance for pick-location replenishment parameters without moving inventory or abusing the inventory transaction audit.

### 6.2 Prerequisites

- Generic CSV framework accepted.
- Sandbox and batch audit mechanism working.
- Canonical replenishment-control fields and dynamic-capacity calculations confirmed.

### 6.3 Target state

A user can apply an accepted replenishment-control preview to a sandbox, with all settings validated, all changes auditable, and no inventory quantity changed.

### 6.4 Domain rules

Each row must target:

- an existing active `PICK` location;
- its current assigned item;
- a location with replenishment controls enabled by the WMS model; and
- a state matching the preview token.

Required ordering:

```text
minimum <= reorder trigger <= target <= maximum
```

Required capacity rule:

```text
maximum <= location pallet capacity * assigned item cases per pallet
```

Additional rules should reuse existing WMS validators rather than be hard-coded in CSV modules.

### 6.5 Apply workflow

Use the same preview-manifest apply discipline as Phase 5:

1. verify accepted preview;
2. verify sandbox and state tokens;
3. rerun validation;
4. begin whole-batch transaction;
5. submit typed replenishment-control maintenance commands;
6. record maintenance history and row mapping;
7. update approved live control fields;
8. commit;
9. run post-apply validation; and
10. create result artifacts.

### 6.6 Audit semantics

Replenishment-control changes do **not** create `inventory_transaction` rows because no quantity moved.

They must create an appropriate maintenance history record containing:

- command ID;
- batch ID;
- row reference;
- location;
- item;
- old control values;
- new control values;
- event/recorded time;
- application version;
- optional user note; and
- source preview reference.

If the repository already has a neutral command-history structure that represents this without ambiguity, reuse it. Otherwise use the additive sandbox schema decision approved in Phase 0.

### 6.7 Operational consequences

After apply:

- `inventory_master` quantities are unchanged;
- no inventory transaction delta is created;
- `replenishment-needs` immediately reflects the new settings;
- inventory-by-location and location detail display the new settings;
- trace resolves the maintenance command even though it has no quantity lines; and
- reconstruction quantity results remain unchanged.

### 6.8 Testing

#### Happy path

- one pick slot;
- multiple pick slots;
- increased target/max;
- decreased controls still above current logical constraints;
- report refresh;
- trace maintenance command.

#### Validation

- reserve location rejected;
- inactive location rejected;
- item mismatch rejected;
- invalid ordering rejected;
- maximum over dynamic physical capacity rejected;
- stale expected controls rejected;
- unchanged row handled consistently;
- blank semantics tested.

#### Atomicity and idempotency

- injected middle-row failure rolls back all controls;
- duplicate batch does not reapply;
- result metadata failure rolls back according to transaction design;
- source database unchanged.

#### Quantity invariance

- inventory master quantities identical before and after;
- inventory transaction row count unchanged;
- reconstruction quantities unchanged;
- replenishment-needs output changes only where expected.

### 6.9 Acceptance criteria

Phase 6 passes when:

- valid batches update all approved controls atomically;
- invalid batches change nothing;
- every accepted row is auditable;
- no quantity or inventory transaction changes occur;
- capacity and ordering rules are enforced;
- reports and trace reflect the change;
- duplicate apply is safe; and
- full regression passes.

### 6.10 Owner review

Review is required for:

- template terminology;
- relationship between min/trigger/target/max;
- dynamic capacity error wording;
- before/after preview;
- post-apply `replenishment-needs`; and
- maintenance trace.

### 6.11 Progression prerequisites

Do not expand this into re-slotting, item reassignment, replenishment task creation, or generic master-file maintenance.

---

## Phase 7 — Standalone Windows application and portable distribution

### 7.1 Purpose

Package the accepted console and CSV workflows as the primary user-facing Windows application so the toolkit can be operated without a development environment.

### 7.2 Prerequisites

- Phases 1–6 accepted from source execution.
- Packaging tool selected and proven in Phase 0.
- Runtime dependency licenses reviewed.
- Standalone directory contract frozen.

### 7.3 Target state

A user can download or copy one ZIP, extract it, double-click `OperationalVarianceToolkit.exe`, open the included sample WMS, clone a sandbox, export reports, and complete both CSV workflows without installing Python, `uv`, VS Code, or project dependencies.

### 7.4 Build entry point

Create a dedicated packaging entry point that calls the same console application used by:

```powershell
uv run operational-variance-toolkit console
```

The packaging entry point may handle bundle resource paths and double-click startup behavior. It must not duplicate command handlers or WMS logic.

### 7.5 Resource bundling

Bundle:

- executable and private runtime dependencies;
- safe baseline sample database;
- CSV templates or template metadata;
- quick-start guide;
- console command reference;
- CSV workflow guide;
- MIT license;
- changelog;
- release notes;
- third-party notices;
- version file;
- release manifest; and
- internal checksums.

Do not bundle:

- source repository Git metadata;
- `.venv`;
- caches;
- test artifacts;
- unrestricted ground truth;
- development secrets;
- machine-specific paths;
- accepted writable sandboxes;
- personal history files; or
- temporary packaging directories.

### 7.6 Portable workspace

On first launch, ensure writable directories exist or can be created:

```text
workspace/exports
workspace/sandboxes
workspace/batches
```

The app should use these as friendly defaults but allow user-selected paths.

It must not require administrator rights.

### 7.7 Double-click behavior

- Opening the executable displays the start menu.
- Startup errors remain visible.
- The console does not immediately exit after a recoverable error.
- The included sample database is treated as protected/read-only.
- The user can clone it into `workspace/sandboxes`.
- Documentation can be opened or its path displayed from the menu/help.

### 7.8 Command-line behavior

Support at least:

```powershell
OperationalVarianceToolkit.exe --help
OperationalVarianceToolkit.exe --version
OperationalVarianceToolkit.exe --database <path>
OperationalVarianceToolkit.exe --sample
```

The executable’s version must match package metadata and release manifest.

### 7.9 Build reproducibility

Create a scripted build command such as:

```powershell
uv run operational-variance-toolkit package-windows --output <new-directory>
```

or a documented build script owned by the repository.

The build must:

- run from a clean source tree;
- resolve resources explicitly;
- refuse existing release output;
- record tool and dependency versions;
- produce a machine-readable manifest;
- calculate internal member hashes;
- create the portable ZIP; and
- calculate external SHA-256.

Byte-for-byte reproducibility across Windows builds is desirable but not required if the packaging tool embeds unavoidable timestamps. Functional and member-level reproducibility must be documented.

### 7.10 Windows testing matrix

Test the extracted bundle in a clean directory outside the repository.

Required cases:

1. No Python command available on `PATH`.
2. No `uv` command available on `PATH`.
3. Launch by double-click.
4. Launch from PowerShell.
5. Launch from Command Prompt.
6. Launch from a directory containing spaces.
7. Open included sample.
8. Run Item and inventory inquiry.
9. Run one standard report.
10. Export CSV and open it in Excel where practical.
11. Clone sample to sandbox.
12. Generate adjustment template.
13. Validate and preview adjustment CSV.
14. Apply adjustment batch.
15. Trace resulting command.
16. Generate and apply replenishment-control batch.
17. Exit and reopen sandbox.
18. Verify source sample unchanged.
19. Verify no restricted truth present.
20. Verify checksums.

### 7.11 Antivirus and signing

The executable will be unsigned unless a signing certificate is later obtained. Documentation must not promise that Windows SmartScreen or third-party antivirus will never warn about a newly built local executable.

The release should minimize avoidable warning triggers by:

- using a reputable packaging tool;
- including version information;
- avoiding self-modifying behavior;
- avoiding download-on-first-run behavior;
- avoiding hidden network activity; and
- publishing checksums when the project is eventually shared.

No effort should be spent trying to bypass security software.

### 7.12 Acceptance criteria

Phase 7 passes when:

- portable Windows ZIP is created;
- executable launches without Python, `uv`, or VS Code;
- source and standalone consoles behave equivalently;
- included sample opens read-only;
- both CSV workflows operate in a standalone-created sandbox;
- paths with spaces work;
- no restricted truth or machine-specific paths are bundled;
- version and manifests agree;
- external checksum verifies; and
- all Windows smoke tests pass.

### 7.13 Owner checkpoint C — Standalone application

Owner acceptance includes completion of the workflow as an ordinary user:

1. extract ZIP;
2. double-click executable;
3. open included sample;
4. inspect inventory;
5. export report;
6. clone sandbox;
7. edit a CSV in Excel;
8. preview and apply;
9. trace the result; and
10. close and reopen the application.

The key acceptance question is:

> Does this feel like a standalone WMS utility rather than a Python project being driven through a terminal?

### 7.14 Progression prerequisites

Do not add an installer, auto-updater, GUI, or network service to solve packaging issues. The target is a reliable portable console application.

---

## Phase 8 — Usability acceptance, documentation, clean reproduction, and release

### 8.1 Purpose

Prove the full `0.2.0` product is safe, usable, documented, reproducible, and ready to freeze locally.

### 8.2 Prerequisites

- All functional phases accepted.
- Owner checkpoints A–C resolved.
- No unresolved safety or data-integrity defects.

### 8.3 Target state

Release `0.2.0` exists as:

- accepted source code;
- accepted portable Windows application;
- complete documentation;
- source and Windows release archives;
- checksums and manifests;
- clean reproduction evidence; and
- local Git tag `v0.2.0`.

### 8.4 Documentation deliverables

Create or update:

- root `README.md`;
- `PROJECT_STATUS.md`;
- `CHANGELOG.md`;
- `RELEASE_NOTES_0.2.0.md`;
- console user guide;
- command reference;
- CSV workflow guide;
- CSV template data dictionary;
- standalone Windows quick start;
- release and reproduction guide;
- architecture diagrams showing the console and packaging layers;
- decision log;
- traceability matrix;
- source release manifest;
- Windows release manifest; and
- third-party notices.

Documentation must clearly distinguish:

- source/developer use;
- standalone user use;
- read-only source databases;
- writable sandboxes;
- export versus update CSV files;
- inventory adjustments versus control maintenance;
- analyst-facing data versus restricted truth; and
- standalone packaging versus production deployment.

### 8.5 Full regression gate

Run the complete existing project suite plus all `0.2.0` tests:

```powershell
uv sync --frozen
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Also run:

- baseline and investigation validation;
- all 12 reports;
- both reconstructions;
- frozen Phase 5 analysis reproducibility where current release policy requires it;
- source leakage scan;
- Windows bundle leakage scan;
- sandbox mutation/source preservation checks;
- CSV atomicity and idempotency tests;
- package manifest verification; and
- archive checksum verification.

### 8.6 Clean source reproduction

From a fresh extraction outside the repository:

1. install with `uv sync --frozen`;
2. verify version/help;
3. generate or open schema-3 data;
4. launch console;
5. run inquiry/report/export;
6. clone sandbox;
7. validate/preview/apply both CSV workflows;
8. run trace;
9. run tests and quality gates;
10. build Windows package; and
11. verify archives and checksums.

### 8.7 Clean standalone reproduction

From a fresh extraction of the Windows ZIP:

1. remove Python and `uv` from the execution path;
2. launch by double-click;
3. launch by terminal;
4. open included sample;
5. run inquiry/report/export;
6. clone sandbox;
7. complete both CSV workflows;
8. exit and reopen;
9. verify sample checksum unchanged;
10. verify created sandbox validation;
11. scan bundle for restricted truth and unsafe paths; and
12. verify internal and external checksums.

### 8.8 Release artifacts

Produce locally:

```text
operational-variance-toolkit-0.2.0-source.zip
Operational-Variance-Toolkit-0.2.0-Windows-x64.zip
operational-variance-toolkit-0.2.0-ground-truth-optional.zip
SHA256SUMS.txt
```

The optional ground-truth archive remains separate under the established spoiler policy. It is not required for ordinary console operation and must not be copied into the Windows bundle.

### 8.9 Versioning

Bump the canonical project version to `0.2.0` only after all functional acceptance gates pass and before final package generation.

Synchronize:

- `pyproject.toml` version;
- executable version output;
- release notes;
- archive names;
- manifests;
- checksums; and
- Git tag.

### 8.10 Local Git release

After final acceptance:

1. confirm clean working tree;
2. create final release commit;
3. create annotated or existing-project-consistent local tag `v0.2.0`;
4. verify tag points to the final release commit; and
5. do not push.

### 8.11 Acceptance criteria

Release `0.2.0` is accepted when:

- all `0.1.0` capabilities remain valid;
- console usability checkpoints are approved;
- both CSV write workflows are atomic, idempotent, and auditable;
- accepted/source databases remain protected;
- portable Windows executable requires no development tools;
- clean source reproduction passes;
- clean standalone reproduction passes;
- all tests and quality checks pass;
- leakage scans pass;
- manifests and checksums verify;
- documentation matches actual behavior;
- local archives are produced; and
- local tag `v0.2.0` exists at the final accepted commit.

### 8.12 Decisions and blockers requiring review

A review decision is required before affected work continues only for:

- a material change to the approved user workflow;
- a need to edit accepted `0.1.0` artifacts;
- a proposed expansion beyond the two writable CSV types;
- a packaging conflict that would prevent a standalone Windows release;
- a license conflict;
- a hidden-truth leakage issue;
- a decision to add an installer or code signing; or
- a failed acceptance gate that cannot be resolved without changing release scope.

Routine implementation choices that remain within this plan may proceed without additional review.

---

## 12. Test strategy summary

### 12.1 Unit tests

- console parser and command dispatch;
- session state transitions;
- prompt and mode labels;
- formatter width and fallback behavior;
- path normalization;
- sandbox manifest validation;
- CSV parsing and normalization;
- contract-version handling;
- batch hashing;
- deterministic command IDs;
- preview arithmetic;
- result artifact serialization;
- packaging resource lookup; and
- version synchronization.

### 12.2 Integration tests

- console open/close/status;
- report parity;
- inquiry parity;
- transaction trace;
- source checksum preservation;
- sandbox clone and reopen;
- adjustment preview/apply;
- replenishment-control preview/apply;
- rollback at injected failure points;
- duplicate batch handling;
- post-batch snapshot and reconciliation;
- report refresh after control changes;
- no ground-truth access; and
- packaged executable smoke tests.

### 12.3 End-to-end tests

- source console read-only workflow;
- source console sandbox adjustment workflow;
- source console control-maintenance workflow;
- packaged standalone workflow;
- clean source build to Windows ZIP;
- clean Windows ZIP extraction and operation.

### 12.4 Safety tests

- read-only URI/query-only protection;
- accepted source hash unchanged;
- invalid sandbox provenance rejected;
- source/destination same-file rejection;
- partial clone cleanup;
- overwrite refusal;
- CSV formula-injection handling;
- stale preview rejection;
- atomic batch rollback;
- duplicate submission prevention;
- output path safety;
- no restricted truth in ordinary artifacts; and
- no machine-specific paths in release packages.

### 12.5 Compatibility tests

The following existing commands remain supported:

```text
config-check
init-wms
init-db
validate
describe
generate
report
scenario-check
reconstruct
analyze
build-reporting
package-release
```

Legacy schema behavior remains as documented. Write workflows clearly reject unsupported legacy schemas.

---

## 13. Release acceptance matrix

| Capability | Source console | Standalone Windows | Read-only source | Sandbox write | Acceptance evidence |
|---|---:|---:|---:|---:|---|
| Launch/help/version | Yes | Yes | N/A | N/A | CLI and executable tests |
| Open schema-3 WMS | Yes | Yes | Yes | Yes | session integration tests |
| Item/location inquiry | Yes | Yes | Yes | Yes | query parity tests |
| Standard reports | Yes | Yes | Yes | Yes | 12-report parity |
| CSV export | Yes | Yes | Yes | Yes | deterministic export tests |
| Transaction trace | Yes | Yes | Yes | Yes | hand-checked trace fixtures |
| Clone sandbox | Yes | Yes | From source | N/A | source hash and provenance tests |
| CSV validation | Yes | Yes | Allowed | Allowed | parser/state validation tests |
| CSV preview | Yes | Yes | Allowed but non-mutating | Allowed | zero-mutation tests |
| Adjustment apply | Yes | Yes | No | Yes | atomicity/idempotency/reconciliation |
| Replenishment-control apply | Yes | Yes | No | Yes | quantity-invariance/audit tests |
| No Python/uv required | No | Yes | N/A | N/A | clean standalone execution |
| Restricted truth absent | Yes | Yes | Yes | Yes | leakage scans |

---

## 14. Development operating policy

### 14.1 Phase execution

Implementation proceeds one phase at a time. A local completion commit requires
passing phase tests and completion of the applicable reviews and acceptance
checkpoints.

Within a phase, routine slices and internal checkpoints may proceed without
additional review. Owner checkpoints and genuine blockers defined in this plan
require review and resolution before affected work continues. Local completion
does not authorize a push, upload, hosted release, or publication; each requires
separate explicit approval.

### 14.2 Acceptance discipline

Before substantial implementation in each phase, acceptance preparation requires:

- inspection of the current repository in addition to this roadmap;
- confirmation of the exact canonical fields and services;
- new or updated targeted acceptance tests;
- preservation of unrelated work; and
- a direct phase need for any broad refactor.

Phase completion requires:

- passing targeted tests;
- a passing full applicable suite;
- passing Ruff and diff checks;
- a `PROJECT_STATUS.md` record of exact results;
- plan updates limited to approved changes;
- completion of required owner reviews and acceptance checkpoints; and
- a local completion commit without a push.

### 14.3 Development coordination

- Repository documents provide durable development context.
- Symbol-level inspection is appropriate when complete-file review is unnecessary.
- Independent read-only discovery may proceed in parallel; overlapping writes and shared-file changes require coordination and serialized edits.
- Findings remain concise, with exact command results retained for acceptance.
- Correctness and validation take precedence over development speed.

Architecture, WMS semantics, schema changes, batch atomicity, sandbox
protection, hidden-truth boundaries, release licensing, and final acceptance
remain owner-reviewed decisions.

---

## 15. Known risks and mitigations

### 15.1 Packaging dependency incompatibility

**Risk:** A selected terminal or packaging library may not support the project’s Python/runtime combination.

**Mitigation:** Mandatory Phase 0 packaging spike before console implementation; choose dependencies based on a working executable, not preference.

### 15.2 Standalone bundle size

**Risk:** Existing analysis/reporting dependencies may produce a large executable bundle.

**Mitigation:** Package the console entry point carefully; exclude development-only content; accept a reasonably sized one-folder bundle rather than forcing fragile single-file compression. Do not split into a second business-logic package merely to reduce size.

### 15.3 Antivirus warnings

**Risk:** Unsigned locally built executables can trigger warnings.

**Mitigation:** Honest documentation, version metadata, checksums, no network/download behavior, and no evasion attempts. Code signing remains optional future work.

### 15.4 CSV state drift

**Risk:** Inventory or controls change after preview but before apply.

**Mitigation:** Expected-state fields, preview fingerprints, immediate pre-apply revalidation, and complete-batch refusal on drift.

### 15.5 Duplicate application

**Risk:** User applies the same spreadsheet twice.

**Mitigation:** Deterministic batch/command IDs and existing idempotency controls.

### 15.6 Snapshot/reconciliation confusion after sandbox changes

**Risk:** Live inventory no longer matches the original closing snapshot after adjustment batches.

**Mitigation:** Create a clearly identified post-batch snapshot or use the existing equivalent accepted by the WMS contract; preserve older snapshots; make reconciliation selection explicit.

### 15.7 Maintenance audit gap

**Risk:** Replenishment-control changes are not inventory transactions and may lack an appropriate existing audit surface.

**Mitigation:** Resolve in Phase 0; reuse neutral command history if correct, otherwise introduce a narrow additive sandbox schema version with explicit compatibility.

### 15.8 Console scope creep

**Risk:** Interactive use encourages arbitrary SQL, direct commands, GUI work, or full master-data maintenance.

**Mitigation:** Maintain explicit exclusions. `0.2.0` supports inquiry, export, sandbox safety, and exactly two writable CSV types.

---

## 16. Definition of release success

Release `0.2.0` succeeds when a user can:

1. extract the Windows ZIP into an ordinary folder;
2. double-click `OperationalVarianceToolkit.exe`;
3. open the included sample WMS without installing anything;
4. inspect Items, locations, inventory, workflows, and transactions;
5. run and export standard reports without long PowerShell commands;
6. trace a replenishment or adjustment coherently;
7. clone the protected sample into a sandbox;
8. generate a CSV template;
9. edit it in Excel;
10. validate and preview the proposed changes;
11. apply the approved batch through ordinary WMS services;
12. audit every accepted row and resulting state change;
13. close and reopen the sandbox successfully; and
14. reproduce the release from source when operating as a developer.

The final product standard is:

> **The user should feel like they are operating a small WMS utility—not driving a Python repository from VS Code.**
