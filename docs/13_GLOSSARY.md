# 13 — Glossary

## Analyst-facing WMS database

The SQLite database an ordinary user or analyst receives. It contains master files, live recorded inventory, workflow records, immutable inventory transactions, snapshots, and standard views. It does not contain physical truth or scenario labels.

## Audit file / inventory transaction file

The append-only `inventory_transaction` table. Each row records one signed location-level quantity effect, before/after balances, command and transaction identity, timestamps, user, and source workflow record.

## Code date

The single product date associated with the item currently recorded in a location under the initial one-item/one-code-date model. It represents a warehouse-readable expiration, best-by, or similar product date. The initial model does not separately implement lot control.

## Command

A typed request submitted to the mini-WMS application layer, such as record pick, confirm replenishment, adjust inventory, or capture snapshot. Commands carry stable command IDs for idempotency.

## Cube

Case volume in cubic feet, calculated from case length × width × height in cubic inches divided by 1,728. Dimensions are retained in `item_master`; cube is not a replacement for them.

## Dynamic physical maximum

The item-dependent case quantity a standard location can hold under the initial model:

```text
location pallet capacity × item cases per pallet
```

It is not an intrinsic fixed case capacity of the location.

## File

Operational/AS/400-style term for a structured source-system dataset. In the SQLite implementation, files are tables or views.

## Ground truth

Restricted scenario facts such as hidden mechanism, target entities, physical timing, and intended evidence. Ground truth is stored outside the WMS database and ordinary analysis.

## Inventory master

The live mutable WMS record keyed by location. It contains current recorded item assignment, quantity, code date, replenishment controls where applicable, last transaction, and last update.

## Item master

The stable warehouse-focused item profile, including dimensions, calculated cube, weight, pallet pattern, storage requirement, velocity, and handling attributes.

## Location master

The stable location profile, including address, zone, type, pallet capacity, pickable status, and active status. It does not contain current item or quantity.

## Mini-WMS

The independent operational application that maintains recorded inventory, audit history, workflow records, snapshots, and standard reports. It is narrower than a production WMS but must behave credibly within included domains.

## Physical state

The simulator’s hidden representation of where product actually exists. It may temporarily differ from WMS recorded state. The WMS cannot read it.

## Recorded state / system state

What the mini-WMS currently believes. In schema `3.0.0`, this is persisted in `inventory_master`.

## Scenario driver

An external protocol that schedules physical actions and submits ordinary WMS commands. It cannot write WMS tables and the WMS does not know its hidden intent.

## Snapshot

An immutable scheduled or verified capture of `inventory_master` at a defined time. It is a report/checkpoint, not live state.

## Standard WMS report

A tested read-only query or view over ordinary WMS files, such as inventory by location, replenishment needs, or transaction inquiry. It contains no scenario interpretation.

## Transaction group

The set of one or more inventory audit rows produced by one accepted command. A replenishment transfer uses one group with a source negative row and destination positive row.

## Three-way reconciliation

The requirement that opening snapshot plus immutable audit replay equals both finalized live inventory master and closing snapshot.

## WMS operational fidelity

The standard that every included WMS domain must use credible state, transaction, audit, validation, and report semantics even though the product does not implement a full enterprise WMS.
