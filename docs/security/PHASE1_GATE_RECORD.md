# Phase 1 compatibility foundations and gate evidence

Controlling specification: OVTK remediation plan R2, SHA-256
`fd5f22ce4a9bf9d439ba080598baf46a4efb1c2a8ad89035124b33fa24fd69aa`.
Baseline: `5931b15c1838e83c37217e385e74a6db13afe6bf`, tree
`d64f805d62b22b0610d889df063662d43674907a`. Genuine history was fetched from
Cobblecat/OVTK and all three earlier security patches were verified ancestors.

G0 is recorded passed for the affected Phase 1 contracts. G1-W implementation
checks pass on the configuration below. Independent phase acceptance remains
with review task `01a11f27-1b05-7ea2-b78a-33ceaaf90d49`.
Phase 2 has not started. G1-P remains deferred and unpassed.

## Changes and boundaries

- `storage.database.accepted_read_snapshot` builds on the existing URI
  `mode=ro`/`query_only` connection. A role validator and SQLiteReadLimits are
  mandatory. Limits apply before validation; one explicit transaction and
  initial read establish the view. The same connection and canonical
  ReadIdentity are yielded and always rolled back/closed. SQL cannot end the
  transaction, attach a database, or turn query_only off. Limits are supplied
  per invocation; no product-facing profile or default ceiling is introduced.
- `storage.csv_codec` recognizes approved manifests before CSV parsing.
  Raw legacy artifacts omit both serialization fields and retain parser
  semantics, including literal `OVTK1_` strings. Declared v1 requires both
  `artifact_format_version: 2.0.0` and `csv_codec: codec-v1`. Producer
  reconstruction/statistics versions continue to describe computation.
  Strict UTF-8 and canonical padded URL-safe Base64 decoding applies only to
  reserved-prefix tokens in declared v1 inputs. The new artifact format
  distinguishes encoded serialization from legacy raw artifacts.
- Phase 5 reconstruction loading and frozen statistics/reconciliation readers
  select that manifest contract. Existing workflow/schema support is retained.
  Unknown or contradictory versions and required missing manifests fail.
  Reporting fixtures now use the real approved producer versions instead of
  placeholder/empty manifests. Original security assertions are preserved.
- `storage.publication.publish_new` owns a private sibling container created
  with Windows mode 0700 ACLs. Native open-handle identity is compared before
  commit and cleanup. Completed payloads publish with MoveFileExW flags 0:
  no replacement, copy fallback, deferred move, or durability flag.
  Every existing destination, including an empty directory, is a collision.
  Cleanup only removes proven private staging and never a public destination.
  Uncertain ownership retains staging and raises a focused error.
- Readiness pairs publish sidecar first and database last; a failed second
  publication retains/reports the sidecar. Adopting readers must later reject
  incomplete or mismatched pairs. This is not a multi-file atomic transaction.
- `tests/security_routes.json` records direct raw database, CSV, publication,
  PDF, and terminal operations with explicit owners. AST checks detect new or
  changed operations and known import aliases. Existing deferred routes are
  inventoried, not declared safe. Snapshot callers migrate in Phase 2,
  analytical writers in Phase 3, reporting capture/claims in Phase 4,
  public producers in Phase 5, and release capture in Phase 6.

## Tested environment and results

Windows 11 Home/Core 25H2 x64 build 26200.9457; local fixed NTFS;
CPython 3.14.6; SQLite 3.50.4; locked uv environment, installed offline.
Exact dependency versions, SQLite compile options, receipt paths/digests,
baseline CSV hashes and F1-F8/prior-patch traceability are in
[phase1-gates.json](phase1-gates.json). Expanded argv and working directories
are retained in the hashed receipts.

| Check | Result |
| --- | --- |
| Unchanged baseline pytest | 451 passed, one Windows ZMQ warning |
| Corrected native sharing controls | 2 passed; verified handles and error 32 precondition |
| Interrupted component suite rerun | 242 passed, one warning |
| Final cumulative pytest | 520 passed, zero failed/skipped, one warning; 438.59 seconds |
| Ruff check and Ruff format --check | Passed |
| Git diff --check | Passed |
| Baseline numerical CSV comparison | 19/19 byte-identical |
| Loaded source tables, metadata, frozen statistics, reporting summary | Exact equality, including dtypes/order/missingness |
| Original security test functions | 11/11 identical UTF-8 ASTs, including assertions/decorators |

Reproduction of the in-repository test suite:

```powershell
uv sync --frozen
uv run pytest --maxfail=1
uv run ruff check .
uv run ruff format --check .
git diff --check
```

G0 evidence includes 1,118 conservatively inventoried candidate sites across
94 baseline source modules, 20 notebook cells, four schema versions, 19 CLI
help/diagnostic entries, manifests, legacy reader behavior, numerical fixtures,
deterministic hashes and prior-patch contracts. Each candidate has a retained,
migration or exclusion disposition. Full evidence is retained through Codex
Security supplemental storage for task
`01a120b5-ba07-70e3-8295-72dbedb1d4dc`; the gate JSON lists digests.
Generated databases, CSV goldens, reports, virtual environments and scratch
files remain outside commits.

## Failure accounting

The first component run stopped after 57 passes and 1 failure. The sharing
fixture used an unchecked FILE_READ_ATTRIBUTES handle, which did not establish
the assumed delete-sharing conflict. Work stopped and the reviewer authorized
a bounded correction (decision SHA-256
`0b1add96425a676072ee7937da41749a0d7574c532e1978b4e5fd36464dd8114`).
The corrected fixture verifies a GENERIC_READ handle, independently probes
DELETE access with OPEN_EXISTING, records native masks/errors, checks rejection
and intact private data, releases the lock and proves retry, and tests the
FILE_SHARE_DELETE positive control. No assertion was skipped or waived.
Metadata-only directory handles preserve identity evidence; they do not pin
directory namespaces. The adapter was not expanded into a broader attacker
model. See [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and the [MS-FSA sharing algorithm](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/8c0e3f4f-0729-49f4-a14d-7f7add593819).

A supplementary AST evidence collector initially used Windows default cp1252
for working files while decoding Git blobs as UTF-8. Its false differences were
explained by equal raw bytes and explicit UTF-8 AST comparison. Only that
collector changed; all 11 original security functions match. Both the failed
sharing attempt and collector correction remain in retained evidence.

## Limits and remaining decisions

The new publication API rejects POSIX and unqualified Windows/filesystems.
Only the exact Windows configuration above has runtime evidence; a supported
family is not proof that every later build passed. The unsupported ReFS branch
was tested with substituted filesystem metadata, not a qualified ReFS volume.
Staging is same-parent by construction; no external staging or cross-volume
copy fallback is exposed. No native POSIX test, durability/recovery guarantee,
artifact authenticity claim or namespace-pinning guarantee is asserted.

Spreadsheet applications/builds/locales/import modes and analytical writer
migration, product resource profiles/performance ceilings, the versioned
five-file release layout, stronger concurrent same-privilege release attacks
and POSIX enablement remain blocked for their dependent phases. The existing
WMS presentation CSV bytes/apostrophe ambiguity and numeric objects remain
unchanged. No XLSX dependency or automatic migration was added.

This phase supplies foundations. It does not close all eight findings or
authorize Phase 2, a merge, distributed artifact, release, issue/advisory
action, or external contact.
