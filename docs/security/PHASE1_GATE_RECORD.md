# Phase 1 compatibility foundations and gate evidence

Controlling specification: OVTK remediation plan R2, SHA-256
`fd5f22ce4a9bf9d439ba080598baf46a4efb1c2a8ad89035124b33fa24fd69aa`.
Baseline: `5931b15c1838e83c37217e385e74a6db13afe6bf`, tree
`d64f805d62b22b0610d889df063662d43674907a`. Genuine history was fetched from
Cobblecat/OVTK and all three earlier security patches were verified ancestors.

This record preserves the implementation submission before final acceptance.
The later decision is recorded in [remediation status](REMEDIATION_STATUS.md).

G0 is recorded passed for the affected Phase 1 contracts. Review denied
advancement at `1876a476931871ec95b59615cea8ad4f7888d015` because the
publication qualifier did not enforce R2's CPython/native x64 restriction.
The bounded correction below passes implementation checks. At submission,
independent Phase 1 acceptance was pending, and Phase 2 remained denied and
had not started. G1-P remains deferred and unpassed.

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

## Original candidate environment and results

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
| Pre-review cumulative pytest | 520 passed, zero failed/skipped, one warning; 438.59 seconds |
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
migration or exclusion disposition. Full evidence is retained in private
validation storage outside the source checkout; the gate JSON lists digests.
Generated databases, CSV goldens, reports, virtual environments and scratch
files remain outside commits.

## Native x64/CPython qualification correction

The independent review required a bounded correction within the existing
F6/G1-W contract; it did not approve Phase 2 or identify a ninth finding.
Formal review SHA-256:
`7ffdf9cd17a5a4e1832cfc4ca03d908928a5a6b00203d5bdf86c8c6923eab267`.
The four reviewed commits are retained and the correction is appended.

Before staging or public mutation, the qualifier now requires
`sys.implementation.name == "cpython"` and Python 3.14, then calls
`IsWow64Process2(GetCurrentProcess())`. Only a successful process-machine
`UNKNOWN` (0), meaning a non-WOW64 process, plus native-machine `AMD64`
(0x8664) is accepted. Other or indeterminate combinations reject. A failed,
unavailable or nominally successful probe with unset outputs also rejects.
Pointer width and architecture strings are not used as admission evidence.
See [Microsoft IsWow64Process2](https://learn.microsoft.com/en-us/windows/win32/api/wow64apiset/nf-wow64apiset-iswow64process2)
and [Python sys.implementation](https://docs.python.org/3.14/library/sys.html#sys.implementation).

The same recorded Windows/NTFS host returned process 0/native 34404 with
CPython 3.14.6. SQLite, compile options, the lock file and all 63 dependency
versions are unchanged. Twenty added cases cover actual native publication,
substituted acceptance, x86, ARM64/ARM64EC, x64 emulation on ARM64,
unknown/inconsistent codes, failed/unset/unavailable probes and non-CPython
rejection before the native probe. Rejection cases verify no staged/public
files remain and focused errors pass unchanged through `terminal_text`.
Substitutions establish decision coverage, not native qualification of those
other machines or interpreters.

| Correction check | Result |
| --- | --- |
| Publication/routing/snapshot/codec/workflow/prior-patch components | 266 passed; zero failures/errors/skips |
| Cumulative suite | 540 passed; zero failures/errors/skips; JUnit time 432.367 seconds |
| Ruff lint, format and Git whitespace checks | Passed |
| Regenerated baseline CSV comparison | 19/19 byte-identical |
| Reader tables and metadata/frozen statistics/report summary | 9 tables plus controls exactly equal |
| Original security-test contracts | 11/11 identical UTF-8 ASTs |
| Gate input stability | All 196 tracked files unchanged during and between both runs |

Both pytest runs retain the existing Windows ZMQ warning. Timings are
descriptive; no product performance threshold is accepted. Exact commands,
native probe/sharing-control JUnit properties, environment and before/after
file manifests are retained under `artifacts/phase1/qualifier-correction/`.
The `qualifier_correction` section of [phase1-gates.json](phase1-gates.json)
indexes their hashes. Later edits affect these gate documents only; executed
source/test hashes are checked again before committing.

A supplementary commit-preparation collector initially stripped the leading
space from Git porcelain status and falsely truncated the first expected path.
It stopped before staging. Only its newline handling was corrected, preserving
the failed helper/receipt and rerunning the exact four-path/index/source checks.
No product test or security assertion was waived and no executed source changed.

No no-replace, staging ownership, pair readiness, reader or prior-patch policy
was changed. All dependent owner decisions and G1-P remain pending or deferred
as recorded below. The decision recommendations are advisory, not an amendment
or approval of resource ceilings, spreadsheet targets or release behavior.

## Earlier failure accounting

The first component run stopped after 57 passes and 1 failure. The sharing
fixture used an unchecked FILE_READ_ATTRIBUTES handle, which did not establish
the assumed delete-sharing conflict. Work stopped, and review authorized
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
