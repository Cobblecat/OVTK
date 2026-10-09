# Remediation Change Summary

## What changed

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
