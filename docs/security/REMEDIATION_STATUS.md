# Security remediation status

Last recorded review: 2026-10-09, commit `5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c`.

This document tracks the security remediation separately from OVTK's feature-development and release milestones. It summarizes status and acceptance requirements without reproduction payloads or private evidence. The private assessment and approved plan remain the detailed specification; this summary does not replace them or authorize implementation, release, or disclosure. 

If all goes well I should be done with this branch and have it implemented by the end of the weekend. 

## Current decision

**Phase 1/G1-W is accepted for the recorded Windows configuration. Phase 2 entry is approved, and its documentation prerequisite is satisfied. All eight findings remain open.**

The foundations are committed on `remediation/phase1-foundations`, based on [`5931b15c1838e83c37217e385e74a6db13afe6bf`](https://github.com/Cobblecat/OVTK/commit/5931b15c1838e83c37217e385e74a6db13afe6bf). Advancement was initially withheld at `1876a476` because the publication qualifier did not fully enforce the approved CPython/native x64 configuration. The append-only correction [`5596678`](https://github.com/Cobblecat/OVTK/commit/5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c) enforces that restriction and adds its required decision/failure coverage. Acceptance followed review of the immutable range and evidence. The original denial and failed helper attempts remain recorded. This resolved an existing publication qualification gap; no ninth defect or failure on another architecture was confirmed.

Phase 2 may implement and validate the approved F3/F7/F8 database group. Product resource ceilings and legitimate-workload support remain unresolved; independent identity, identifier and algorithm work and bounded synthetic calibration may proceed, but G2 cannot pass or dependent work advance on invented defaults. The approved performance policy permits no more than 10% ordinary-workload median runtime regression after accounting for measurement noise, with no unexplained peak-memory growth; absolute limits and headroom remain subject to calibration and approval. Stop affected work and report failed gates, blocking decisions or new issues for review. The private acceptance record is retained with SHA-256 `03e3f5700fdd0515aa754999da3dbc8d2d1a970dd238e1635dc555f0f9e46288`.

The Windows-first design remains feasible. Native POSIX publication qualification is deferred because an approved native runner has not been established. Deferred qualification is not a passing result.

## Finding coverage

F1-F8 identify the original assessment findings; they are **not GitHub issue numbers**. A foundation supporting a finding does not establish that its affected callers have migrated or that the finding is fixed.

| Finding | Required control | Planned security phase | Current disposition |
| --- | --- | --- | --- |
| F1 — Release symlink following | Confined regular-file capture into private staging; derive archive inventories from captured bytes. | 6, with the F1/F6 interaction | Open; release capture has not migrated. |
| F2 — Analytical CSV formula injection | Manifest-declared reversible analytical serialization, strict readers, compatible writer migration, and real spreadsheet qualification. | 3, with the F2/F4/F5 interaction | Open; codec readers and manifest recognition exist, writer migration is pending. The conditional Phase 6 frozen-matrix CSV route belongs to F2. |
| F3 — Mixed-run WMS identity | Exact-one-run validation and accepted identity on the same read snapshot used for queries. | 2 | Open; the shared snapshot foundation exists, production workflow adoption is pending. |
| F4 — Unbound reconciliation reporting | Capture the accepted evidence set once, verify file/manifest/run/source/role binding, and use only captured inputs. | 4 | Open; reporting capture and binding are pending. |
| F5 — Unconditional empirical conclusions | Derive supported claims from one frozen evidence result and reuse it across reporting surfaces. | 4 | Open; claim derivation and reporting migration are pending. |
| F6 — Non-atomic output reservation | Invocation-owned private staging, qualified no-replace publication, ownership-safe cleanup, and fail-closed pair readiness. | 5, supporting 6 | Open; corrected foundation is accepted for the recorded Windows configuration, producer adoption is pending. |
| F7 — Unbounded QA/adjustment join | Exact bounded-processing replacement, cumulative work limits, and differential numerical/ordering checks. | 2 | Open; supplied limit contracts exist, algorithm replacement and approved product profiles are pending. |
| F8 — Schema-derived SQL identifier injection | Correct identifier handling and object policy within the accepted, bounded read boundary. | 2 | Open; snapshot infrastructure exists, identifier/object-policy adoption is pending. |

## Earlier source fixes and regression requirements

The following public GitHub issues were verified closed as completed on 2026-10-09. Their source-fix disposition remains separate from the eight findings above, later integration checks, and distributed-release status.

| Earlier fix | Source commit and issue | Integration requirement and limit |
| --- | --- | --- |
| PDF text escaping | [`f70d93e`](https://github.com/Cobblecat/OVTK/commit/f70d93e08d893e994a850c0ea658f73bb8410074), [issue #1](https://github.com/Cobblecat/OVTK/issues/1) | Escape supplied text once at ReportLab Paragraph insertion; preserve authored markup and canonical data. Resource operations were intercepted/blocked during earlier verification; actual retrieval or sensitive-file disclosure was not demonstrated. |
| WMS CSV protection | [`e5efb68`](https://github.com/Cobblecat/OVTK/commit/e5efb68352f9205f6d01ffd73e4b03b84453c7a2), [issue #2](https://github.com/Cobblecat/OVTK/issues/2) | Preserve existing presentation bytes and numeric objects. Apostrophe encoding is not reversible; do not strip apostrophes or stack the analytical codec. Earlier serialization tests did not qualify real spreadsheet applications. |
| Terminal escaping | [`3d43460`](https://github.com/Cobblecat/OVTK/commit/3d434602635dcd3ff528be2799b856b80b6c395a), [issue #3](https://github.com/Cobblecat/OVTK/issues/3) | Route new data and diagnostics through the shared terminal sink once; preserve trusted layout. Every terminal implementation and all Unicode display behavior have not been qualified. |

At the Phase 1 reviewed range, the earlier production sinks are unchanged and 11 original security-test contracts are preserved. Later phases must verify new callers and fields, not merely retain these tests.

## Commit and phase ledger

| Phase | Scope | Recorded status |
| --- | --- | --- |
| 0 / G0 | Evidence, affected compatibility contracts, ownership inventory and decisions. | Recorded passed for the contracts needed by Phase 1; dependent resource/spreadsheet decisions remain unresolved. |
| 1 / G1-W | Shared read, codec-reader, publication and routing foundations. | Five commits below; corrected foundations accepted for the recorded Windows configuration. |
| G1-P | Native POSIX foundation qualification. | Deferred and unpassed; no approved native runner established. |
| 2 / G2 | Database identity, snapshots, SQL identifiers and bounded analysis. | Entry approved; documentation prerequisite satisfied. Implementation and G2 acceptance remain pending, including dependent resource/workload decisions. |
| 3 / G3 | Versioned analytical writers and spreadsheet qualification. | Not started; consumer matrix approval and evidence required. |
| 4 / G4 | Captured reporting evidence and truthful claims. | Not started. |
| 5 / G5 | Output producer migration and no-replace publication. | Not started. |
| 6 / G6 | Confined release capture and release publication. | Not started; five-file layout compatibility decision remains pending. |
| 7 / G7 | Earlier-patch regression across the changed architecture. | Not started; prior-patch checks also apply during earlier phases. |
| 8 / G8 | Complete workflow, platform and performance qualification. | Not started. |
| 9 / G9 | Evidence accounting and owner acceptance. | Not started. |

Phase 1 commits:

- [`a9d97fa`](https://github.com/Cobblecat/OVTK/commit/a9d97fae33678fab71d2295a66b47f78da571051) — accepted read snapshot and supplied limit foundation.
- [`0ff0083`](https://github.com/Cobblecat/OVTK/commit/0ff00836914cbc1b7e3d5c2ff03f1dd77e0f094f) — recognized analytical manifests and codec-v1 readers.
- [`13078fe`](https://github.com/Cobblecat/OVTK/commit/13078fe33655c04c60d9b9d6c940b0522921f333) — Windows/NTFS publication lifecycle primitives.
- [`1876a47`](https://github.com/Cobblecat/OVTK/commit/1876a476931871ec95b59615cea8ad4f7888d015) — routing contracts and G0/G1-W evidence.
- [`5596678`](https://github.com/Cobblecat/OVTK/commit/5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c) — CPython/native AMD64 qualification correction and updated evidence; original four commits retained.

Keep completed phases and corrections in separately scoped, traceable commits. Record the immutable commit, commands, environment, results, failures, compatibility checks and review decision before advancement. Explicit phase approval is required before the next phase begins. A failed gate or new issue stops the affected work; it is not waived by a later passing test count.

## Evidence at the reviewed commit

See [Phase 1 gate record](PHASE1_GATE_RECORD.md) and [machine-readable gate evidence](phase1-gates.json).

Those records preserve the implementer's submission before the independent correction review. The later acceptance decision above supersedes their advancement denial; the recorded commands, results and earlier failures remain unchanged.

- Recorded environment: Windows 11 Home/Core 25H2 x64 build 26200.9457, local fixed NTFS, CPython 3.14.6, SQLite 3.50.4 and locked dependencies.
- Pre-correction cumulative suite: 520 tests passed. Corrected candidate: 266 component and 540 cumulative tests passed, zero failures/errors/skips, one existing Windows/ZMQ warning. Lint, formatting and whitespace checks passed. Acceptance review inspected these receipts without rerunning OVTK tests.
- Recorded compatibility: 19 CSV files byte-identical and nine loaded reader tables equal, including dtypes, ordering and missingness.
- The initial review checked 75 indexed evidence digests and 16 changed candidate-file digests. The correction review checked 119 indexed entries (43 correction, 75 earlier, one collector receipt), matching hashes throughout, and verified the exact four-file correction range. All four execution manifests match; all 194 nongate files match executed bytes, with only the two gate records subsequently changed. This supports evidence identity, not comprehensive correctness.
- The initial sharing-fixture failure and its bounded correction were retained. The gate record explains the verified native precondition and positive control; no failed gate was erased or silently waived.
- The supplemental commit-preparation helper initially trimmed a meaningful leading space from Git status output. Its assertion stopped before staging. The corrected helper trims trailing newlines only, retaining the same source/index/path checks; both attempts are retained. No product test or security assertion was waived.

These are local recorded results for the candidate source represented by the reviewed commits. They are not signed remote CI evidence, qualification of every supported configuration, or closure of unimplemented controls.

## Compatibility, support and unresolved decisions

- Initial migrated-publication qualification targets Windows 11 25H2 Home/Core **x64**, local fixed **NTFS**, and **CPython 3.14.x**. Exact tested versions are recorded above. The corrected guard admits only a successful native-process/AMD64-host result. Substituted rejection cases do not qualify other native architectures or interpreters; approval of a configuration family is not evidence that every build passed.
- Native Ubuntu Server 26.04.1 LTS amd64/ext4/CPython 3.14.x is the intended future POSIX target. Migrated publication/release workflows must remain disabled there until native and applicable later gates pass. Mocks, WSL and containers do not satisfy the approved native qualification requirement. This does not disable unrelated compatible read-only workflows.
- Approved legacy format/schema tuples retain their existing workflow support. Legacy text is not decoded by guessing a prefix. Unknown/contradictory declarations reject; no date cutoff or automatic removal is approved. Historical artifacts needing preservation have not been fully inventoried.
- Canonical database values, numerical results and deterministic artifacts remain compatibility requirements. PDF, terminal, WMS presentation CSV and analytical CSV encoding policies have distinct sinks and must not be stacked.
- Product resource ceilings, legitimate normal/largest workloads and spreadsheet application/build/locale/import-mode support remain unresolved for their dependent gates. The approved relative performance policy above requires measured calibration; absolute resource limits and support claims are not established by that approval.
- A new versioned five-file release directory is recommended but its user-visible output-path contract awaits approval. Preserve source/optional-ground-truth separation. Broader concurrent same-privilege release mutation guarantees have not been adopted.
- Every existing destination, including an empty directory, must reject under publish-new. Pair readiness is fail-closed; separate files are not a multi-file atomic transaction. Power-loss durability, automatic recovery, XLSX companions and automatic migration remain deferred.

## Closure and disclosure

Update each finding only when its implementation commit and required individual, interaction, earlier-patch and cumulative evidence support the stated disposition. Keep source-fix status, issue status, merged branch status, distributed release status and advisory status separate. No patched distributed release or affected release range is established by the Phase 1 branch work.

Report potential vulnerabilities through [SECURITY.md](../../SECURITY.md). Private assessment materials and reproduction details should remain in the private reporting/review channel. This status document is not a disclosure authorization or a claim of comprehensive security.
