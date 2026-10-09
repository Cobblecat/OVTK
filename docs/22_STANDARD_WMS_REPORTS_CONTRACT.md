# 22 — Standard WMS Reports Contract

## 1. Purpose

Standard reports provide an operational user’s first-line view of the WMS. They are not statistical analysis and do not reveal scenario intent.

Each report must be available through a registered read-only query and, where practical, direct SQL view.

## 2. Common report metadata

Every rendered/exported report includes or is accompanied by:

- report code and name;
- run ID;
- database path or source identity;
- schema version;
- as-of time;
- parameters;
- generated-at time;
- row count.

CSV content ordering must be deterministic.

Canonical project terminology is **Item**, not SKU. Technical source-column
names remain stable, while CLI and CSV presentation uses these owner-approved
labels where applicable:

- `Item ID`;
- `Recorded Occupied`;
- `Recorded Compatible Reserve Quantity`;
- `Operational Event Time`;
- `WMS Recorded Time`;
- `Source Reference`;
- `QA Observed Quantity`;
- `Recorded Inventory Snapshot`; and
- `Live-versus-Snapshot Reconciliation`.

## 3. `inventory-by-location`

### Purpose

Show the current recorded contents and profile of every warehouse location.

### Grain

One row per location.

### Required columns

- location ID;
- zone;
- location type;
- aisle, bay, level, position;
- pallet capacity;
- pickable and active flags;
- current item ID and description;
- quantity on hand;
- code date;
- cases per pallet;
- calculated physical maximum cases;
- available capacity for current item;
- occupancy percentage;
- trigger/minimum/target/maximum where applicable;
- last transaction ID;
- last updated UTC.

### Rules

- empty locations remain visible;
- case capacity is calculated only when an item is assigned;
- no hidden physical quantity.

## 4. `inventory-by-item`

### Grain

One row per item and optionally zone.

### Required columns

- item ID and description;
- required zone;
- velocity;
- total on-hand cases;
- pick cases;
- reserve cases;
- occupied location count;
- earliest code date;
- latest update;
- cases per pallet;
- pallet-equivalent quantity for interpretation.

## 5. `location-profile`

### Grain

One row per location.

### Required columns

Only stable location profile fields plus calculated current-occupancy summary. Clearly distinguish profile columns from current inventory columns.

## 6. `empty-locations`

### Grain

One row per zero-quantity location.

### Required columns

- location ID;
- zone/type/address;
- pallet capacity;
- assigned item if a zero-quantity pick slot;
- active/pickable status;
- last update.
- empty-location classification.

Do not treat a zero-quantity assigned pick slot as unassigned reserve space.
The classification value must be `Unassigned Empty Reserve` for an unassigned
zero-quantity reserve and `Assigned Zero-Quantity Pick Slot` for a retained
pick assignment at zero quantity.

## 7. `code-date-inventory`

### Grain

One row per occupied location with code date.

### Required columns

- item and location;
- quantity;
- code date;
- days until/past code date relative to explicit as-of date;
- zone;
- velocity/category.

## 8. `replenishment-needs`

### Grain

One row per pick location requiring or approaching replenishment.

### Required columns

- item/location;
- current quantity;
- trigger/minimum/target/maximum;
- recommended quantity to target;
- recorded compatible reserve quantity;
- velocity;
- open task ID/status if present;
- oldest open-task age.

### Rules

- recommended quantity cannot exceed target or dynamic physical maximum;
- report does not create tasks.

## 9. `open-replenishment-tasks`

### Grain

One row per `CREATED` or `STARTED` task.

### Required columns

- task ID;
- item;
- source/destination;
- status;
- operator;
- requested quantity;
- created/start times;
- age;
- current source/destination recorded quantities;
- delay reason.

## 10. `inventory-transaction-inquiry`

### Grain

One row per immutable audit line.

### Required columns

- transaction ID/group/command;
- event sequence/line;
- type;
- item;
- location and related location;
- signed delta;
- balance before/after;
- operator;
- operational event time and WMS recorded time;
- reason;
- source record type/ID.

Support filters by item, location, transaction group, source record, operator, and time range.

## 11. `adjustment-history`

### Grain

One row per adjustment.

### Required columns

- adjustment ID;
- item/location;
- signed quantity;
- reason;
- operator;
- effective/recorded times;
- balance before/after from audit;
- source reference.

## 12. `qa-activity`

### Grain

One row per QA event.

### Required columns

- QA event ID;
- item/location;
- event type;
- QA observed quantity;
- operator;
- occurred/recorded times;
- reason and disposition.

It must not claim a causal adjustment link.

## 13. `inventory-snapshot` - Recorded Inventory Snapshot

### Grain

One row per location for a selected snapshot batch.

### Required columns

- batch/type/as-of time;
- location;
- item;
- quantity;
- code date;
- last transaction.

## 14. `inventory-reconciliation` - Live-versus-Snapshot Reconciliation

### Purpose

Provide a factual comparison of live `inventory_master` with a selected WMS
snapshot.

The full transaction replay is produced by the external analysis workflow. It
must not be imported into, attached to, or written back into the WMS source
database, and it is not part of this standard WMS report.

Required fields:

- location;
- item;
- live master quantity;
- selected snapshot batch and as-of time;
- selected snapshot quantity;
- live-versus-snapshot difference;
- status.

## 15. CLI behavior

Recommended:

```text
report --database <db> --list
report --database <db> --name inventory-by-location
report --database <db> --name inventory-transaction-inquiry --item ITEM-0001
report --database <db> --name replenishment-needs --output <csv>
```

Expected errors:

- unknown report;
- unsupported schema;
- invalid parameter;
- unsafe output overwrite;
- source validation failure.

Implemented schema-3 report codes are the section names in this document:
`inventory-by-location`, `inventory-by-item`, `location-profile`,
`empty-locations`, `code-date-inventory`, `replenishment-needs`,
`open-replenishment-tasks`, `inventory-transaction-inquiry`,
`adjustment-history`, `qa-activity`, `inventory-snapshot`, and
`inventory-reconciliation`.

The reusable direct-SQL views are `wms_inventory_by_location`,
`wms_inventory_by_item`, `wms_location_profile`, `wms_empty_locations`,
`wms_adjustment_history`, and `wms_qa_activity`.

## 16. Report testing

Every report requires:

- hand fixture;
- direct SQL agreement;
- stable columns/order;
- parameter validation;
- no source mutation;
- no physical/truth access;
- deterministic CSV export;
- empty-result handling;
- schema-version support statement.
