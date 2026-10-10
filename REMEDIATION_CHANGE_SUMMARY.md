# Remediation Change Summary

This document summarizes the current security remediation and the earlier
operational architecture changes. Security phase numbers are separate from the
product-development milestones. See the [security remediation status](docs/security/REMEDIATION_STATUS.md)
for all eight findings, phase gates, source commits and qualification limits.

## Security remediation — 2026-10-09

### Accepted foundations

Phase 1/G1-W is accepted for the recorded Windows configuration at
[`5596678`](https://github.com/Cobblecat/OVTK/commit/5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c).
The shared foundations establish accepted read snapshots with explicit supplied
limits, declared analytical CSV readers, invocation-owned staging and qualified
no-replace publication. Workflow adoption and later qualification remain phase-gated.

The owner removed Ubuntu/native POSIX qualification from the required remediation
gates. Windows security, compatibility, earlier-patch, workflow and performance
requirements remain in effect. Ubuntu support is unqualified; future enablement
requires separate approval and evidence.

### Phase 2 identity component accepted at checkpoint 5

[`ba61169`](https://github.com/Cobblecat/OVTK/commit/ba61169f29b5d1209132c68514375ba79df62a4f)
requires exactly one WMS metadata row with a nonempty text run identity and checks
all 19 required run-bearing tables for that identity before dependent validation.
Legitimate empty child tables remain valid, and foreign-key checks remain required.
This component passed review against the approved plan; continued Phase 2 work is
approved. Checkpoint 5 is a work/review submission within Phase 2, not Phase 5 acceptance.

The completed candidate run reports **598 passing tests**, including **58 identity
cases**, with zero failures/errors/skips and one existing Windows/ZMQ warning.
The committed component files match the executed source bytes. Acceptance review
checked the immutable source and retained evidence without rerunning OVTK tests.
The test run preceded the commit; intervening changes were narrative documents.

Compatibility evidence preserves 19 CSV files byte-for-byte, nine reader-table
contracts, metadata, numerical/statistical results and summaries. The earlier PDF
text, WMS CSV and terminal escaping protections remain in place, with 11 original
security-test contracts preserved. Canonical values and numeric objects remain
unchanged. WMS presentation CSV apostrophe encoding remains non-reversible; it
must not be stripped or combined with the analytical codec.

### Current calibration hold

The temporary Windows measurement harness has not passed its process-containment
preflight. The latest safety-only diagnostic stopped after observing an additional
distinct process in its owned Windows Job. The effective process-limit behavior
and workload-admission contract remain unresolved. Cleanup passed for that attempt
only; no OVTK workload measurements ran, and the accepted repository bytes remained
unchanged.

Further execution and implementation are paused pending review of this qualification
issue; the recurring schedule is paused. The checkpoint 5 identity acceptance stands.
This observation establishes no new OVTK defect, resource profile or phase acceptance.
G2, full F3 qualification and Phase 3 entry remain held.

### Remaining Phase 2 work and later gates

- Integrate accepted snapshots into WMS describe/report readers and demonstrate
  that identity validation and result reads use the same accepted connection and
  snapshot; retain the complete affected-reader inventory.
- Complete the approved Phase 2 identity/snapshot, exact bounded QA/adjustment
  analysis and SQL identifier/object-policy group. Measured resource ceilings,
  headroom, compatibility and grouped performance evidence remain required for G2.
- Preserve the approved performance policy: no more than 10% ordinary-workload
  median runtime regression after accounting for measurement noise, with no
  unexplained peak-memory growth. Synthetic calibration sizes are not product
  ceilings or proof of the largest legitimate workload.
- Retain later gates for analytical CSV writer migration and spreadsheet
  qualification, captured/bound reporting evidence and truthful claims, output
  producer migration, confined release capture, earlier-patch regression and the
  complete Windows workflow.

All eight findings remain open. F3's identity component is accepted; same-snapshot
reader integration and complete F3/G2 qualification remain pending. Phase 3 entry
is pending. The remediation is on `remediation/phase1-foundations`; `main` remains
at `5931b15`. These source commits do not establish a patched distributed release
or an affected release range. Advisory posting was canceled at the owner's
request; no advisory has been created or published as part of this remediation.

## Earlier operational architecture changes

The project’s core business problem and investigation scenarios did not change.
The operational architecture did.

### Legacy model

```text
operations generator
    owns normal events
    owns scenario overlays
    owns recorded state in memory
    writes workflow tables and snapshots

analysis
    reconstructs from workflow tables
```

### Corrected model

```text
independent mini-WMS
    owns live recorded inventory
    owns transaction rules and audit
    owns standard reports

physical simulator
    owns physical truth

scenario drivers
    schedule physical actions
    submit ordinary WMS commands
    write restricted truth separately

analysis
    replays immutable WMS audit
    reconciles to live inventory and snapshots
```

## What remains valid

- deterministic identities and named random streams;
- configuration architecture;
- CLI and error foundation;
- SQLite and explicit SQL choice;
- facility, zone, operator, shift, trip, pick, replenishment, QA, adjustment, and system-event concepts;
- the three controlled patterns;
- restricted JSON ground truth;
- source-preserving reconstruction approach;
- context-table concepts;
- statistical guardrails;
- test and traceability discipline.

## What is superseded

- cube without retained dimensions;
- fixed case capacity in location profile;
- equipment area in location profile;
- handling units without full pallet lifecycle;
- snapshot-centered current inventory;
- in-memory recorded system state as the only live balance;
- scenario overlays inside WMS-like generation code;
- workflow-derived inventory audit as the only ledger;
- two-way closing snapshot reconciliation.

## New schema 3 anchors

- `item_master`
- `location_master`
- `inventory_master`
- `inventory_transaction`

## Why the remediation is necessary

An analyst should be able to query what the WMS currently records, trace why it
records that balance, run ordinary operational reports, and independently audit
the result. The investigation is credible only when the source system behaves
coherently regardless of which scenario operates it.
