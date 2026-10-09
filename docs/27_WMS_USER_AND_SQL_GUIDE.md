# WMS User and SQL Guide

This guide is for inspecting a schema `3.0.0` WMS database. The database is
synthetic, local, and read-only for the workflows below. Use a fresh output
path when creating or regenerating artifacts; do not migrate a generated
database in place.

## WMS command-line workflow

Create a schema-3 WMS database with the canonical initializer:

```powershell
uv run operational-variance-toolkit init-wms `
  --config configs/baseline.toml `
  --output artifacts/data/schema3_baseline.sqlite3
```

Validate and describe an existing database:

```powershell
uv run operational-variance-toolkit validate `
  --database artifacts/data/schema3_baseline.sqlite3

uv run operational-variance-toolkit describe `
  --database artifacts/data/schema3_baseline.sqlite3
```

`init-db` is the legacy schema-1/2 path. It is not the schema-3 WMS
initializer.

## Standard reports

List the registered reports:

```powershell
uv run operational-variance-toolkit report `
  --database artifacts/data/schema3_baseline.sqlite3 `
  --list
```

Run a report to the terminal or to a new CSV path:

```powershell
uv run operational-variance-toolkit report `
  --database artifacts/data/schema3_baseline.sqlite3 `
  --name inventory-by-location

uv run operational-variance-toolkit report `
  --database artifacts/data/schema3_baseline.sqlite3 `
  --name inventory-by-item `
  --output artifacts/reports/inventory_by_item.csv
```

The available report names are:

`inventory-by-location`, `inventory-by-item`, `location-profile`,
`empty-locations`, `code-date-inventory`, `replenishment-needs`,
`open-replenishment-tasks`, `inventory-transaction-inquiry`,
`adjustment-history`, `qa-activity`, `inventory-snapshot`, and
`inventory-reconciliation`.

Examples with read-only filters:

```powershell
uv run operational-variance-toolkit report `
  --database artifacts/data/schema3_baseline.sqlite3 `
  --name inventory-transaction-inquiry `
  --item ITEM-0001

uv run operational-variance-toolkit report `
  --database artifacts/data/schema3_baseline.sqlite3 `
  --name inventory-reconciliation `
  --snapshot-batch SNAPSHOT-BATCH-ID
```

`inventory-reconciliation` compares live `inventory_master` with the selected
WMS snapshot. It is not the independent transaction-replay reconstruction.

WMS CSV exports prefix hazardous string cells with an apostrophe for spreadsheet
review, including identifiers and references beginning with formula markers or
leading tab/line-break characters. This presentation encoding leaves database
values and numeric cells unchanged. Analytical CSV inputs retain their raw
machine-readable format. Terminal output displays control characters as visible
escapes; application-owned help lines and report column separators remain intact.

## Safe read-only SQL

The reusable report views are ordinary WMS read models. Open SQLite in read-only
mode and query only. The `immutable=1` URI is appropriate for a finalized
database that will not change during inspection.

Using the SQLite CLI:

```powershell
sqlite3 "file:artifacts/data/schema3_baseline.sqlite3?mode=ro&immutable=1" `
  "SELECT location_id, item_id, qty_on_hand_cases FROM wms_inventory_by_location ORDER BY location_id LIMIT 20;"
```

Using Python's standard-library `sqlite3` adapter:

```python
import sqlite3

database = "file:artifacts/data/schema3_baseline.sqlite3?mode=ro&immutable=1"
with sqlite3.connect(database, uri=True) as connection:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT item_id, SUM(qty_on_hand_cases) AS recorded_cases
        FROM inventory_master
        WHERE item_id IS NOT NULL
        GROUP BY item_id
        ORDER BY item_id
        """
    ).fetchall()
    for row in rows:
        print(dict(row))
```

Useful read-only checks include:

```sql
SELECT name FROM sqlite_master
WHERE type IN ('table', 'view')
ORDER BY name;

SELECT item_id, location_id, qty_on_hand_cases, code_date
FROM inventory_master
WHERE qty_on_hand_cases > 0
ORDER BY item_id, location_id;

SELECT transaction_id, transaction_type, item_id, location_id,
       qty_delta_cases, balance_before_cases, balance_after_cases,
       event_utc, recorded_utc
FROM inventory_transaction
ORDER BY event_sequence, line_number;
```

The schema-3 operational tables include `item_master`, `location_master`,
`inventory_master`, and immutable `inventory_transaction`, along with the
workflow and snapshot tables. `inventory_master` has one row per location and
at most one Item and one code date per location. Empty reserve locations may
have no Item; an assigned pick location can retain its Item at zero quantity.

## WMS state versus independent reconstruction

The WMS is the source of recorded operational state. Its application services
validate commands, update `inventory_master`, and write immutable
`inventory_transaction` audit lines atomically. QA observations alone do not
change recorded inventory.

Independent reconstruction is a read-only analysis workflow:

```powershell
uv run operational-variance-toolkit reconstruct `
  --database artifacts/data/schema3_baseline.sqlite3 `
  --output artifacts/analysis/schema3_baseline
```

It replays the opening recorded snapshot and immutable audit history into
derived files, then compares the reconstructed closing quantity with live
`inventory_master` and the selected closing snapshot. These derived outputs
are outside the WMS database and must not be written back into it. Physical
warehouse state and restricted ground truth are also outside ordinary WMS
reports and analyst-facing reconstruction.

All records and examples in this repository are synthetic. Item identifiers,
operators, quantities, timings, and events are generated for testing and
training; they are not evidence about real people, facilities, or operations.
