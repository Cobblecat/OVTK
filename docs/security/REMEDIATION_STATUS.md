# Security remediation status

Last source acceptance: 2026-10-09, checkpoint 5, commit [`ba61169f29b5d1209132c68514375ba79df62a4f`](https://github.com/Cobblecat/OVTK/commit/ba61169f29b5d1209132c68514375ba79df62a4f). Current calibration review: 2026-10-09; execution and implementation paused pending preflight qualification.

This document tracks the security remediation separately from OVTK's feature-development and release milestones. It summarizes status and acceptance requirements without reproduction payloads or private evidence. The private assessment and approved plan remain the detailed specification; this summary does not replace them or authorize implementation, release, or disclosure.

If all goes well I should be done with this branch and have it implemented by the end of the weekend.

## Current decision

**Phase 1/G1-W is accepted for the recorded Windows configuration. Phase 2's committed WMS identity component passed checkpoint 5 review. Further execution and implementation are paused pending qualification of the temporary Windows calibration harness. G2 acceptance, full F3 qualification and Phase 3 entry remain held. All eight findings remain open.**

The foundations are committed on `remediation/phase1-foundations`, based on [`5931b15c1838e83c37217e385e74a6db13afe6bf`](https://github.com/Cobblecat/OVTK/commit/5931b15c1838e83c37217e385e74a6db13afe6bf). Advancement was initially withheld at `1876a476` because the publication qualifier did not fully enforce the approved CPython/native x64 configuration. The append-only correction [`5596678`](https://github.com/Cobblecat/OVTK/commit/5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c) enforces that restriction and adds its required decision/failure coverage. Acceptance followed review of the immutable range and evidence. The original denial and failed helper attempts remain recorded. This resolved an existing publication qualification gap; no ninth defect or failure on another architecture was confirmed.

The approved Phase 2 scope is the F3/F7/F8 database group; its current execution and implementation hold is described below. Product resource ceilings and legitimate-workload support remain unresolved, and G2 cannot pass or dependent work advance on invented defaults. The approved performance policy permits no more than 10% ordinary-workload median runtime regression after accounting for measurement noise, with no unexplained peak-memory growth; absolute limits and headroom remain subject to calibration and approval. Stop affected work and report failed gates, blocking decisions or new issues for review. The private acceptance record is retained with SHA-256 `03e3f5700fdd0515aa754999da3dbc8d2d1a970dd238e1635dc555f0f9e46288`.

Checkpoint 5 accepted [`ba61169`](https://github.com/Cobblecat/OVTK/commit/ba61169f29b5d1209132c68514375ba79df62a4f) as the bounded F3 identity component. WMS validation now requires exactly one metadata row with a nonempty text run identity and checks all 19 required run-bearing tables for that identity before dependent validation. Legitimate empty child tables remain valid, and foreign-key checks remain required. This component does not establish that validation and every subsequent reader use the same accepted snapshot.

After the current hold is cleared, the remaining objectives include accepted-snapshot integration for WMS describe/report readers, with focused caller evidence that identity validation and result reads use the same accepted connection and snapshot. Keep the affected-reader inventory explicit and produce measured resource profiles and headroom for approval before adopting product ceilings. F7's exact bounded algorithm, F8's identifier/object policy, remaining reader adoption and the grouped compatibility/resource/performance evidence are still required before G2 acceptance.

### Calibration preflight hold

The temporary Windows measurement harness has not passed its process-containment preflight. The latest separately authorized safety-only diagnostic stopped after observing an additional distinct process in the owned Windows Job. The effective process-limit behavior and workload-admission contract remain unresolved. No OVTK workload measurements ran; the accepted repository bytes remained unchanged. Cleanup passed for this attempt only, which does not qualify admission or every effective limit.

Further execution and implementation, product-profile adoption, dependent reader adoption and the recurring schedule remain paused pending review. Earlier failed attempts remain retained. The latest diagnostic's 19 indexed evidence files and all 18 declared file sizes were independently checked, along with the index and completion digests. This establishes evidence identity for the stop decision; it does not establish a new OVTK defect or invalidate the accepted checkpoint 5 identity component. No additional run or phase advancement is approved by this record.

On 2026-10-09, the owner removed Ubuntu support qualification from the required remediation gates. G1-P is removed from this remediation's acceptance dependencies, and no native Ubuntu/POSIX runner or qualification result is required for phase advancement or final Windows-candidate acceptance. G1-W and all applicable Windows security, compatibility, prior-patch, workflow, and performance gates remain required. Ubuntu support remains unqualified and outside the required scope; this decision establishes no new test result or phase acceptance.

## Finding coverage

F1-F8 identify the original assessment findings; they are **not GitHub issue numbers**. A foundation supporting a finding does not establish that its affected callers have migrated or that the finding is fixed.

| Finding | GitHub issue | Required control | Planned security phase | Current disposition |
| --- | --- | --- | --- | --- |
| F1 — Release symlink following | [#4](https://github.com/Cobblecat/OVTK/issues/4) | Confined regular-file capture into private staging; derive archive inventories from captured bytes. | 6, with the F1/F6 interaction | Open; release capture has not migrated. |
| F2 — Analytical CSV formula injection | [#5](https://github.com/Cobblecat/OVTK/issues/5) | Manifest-declared reversible analytical serialization, strict readers, compatible writer migration, and real spreadsheet qualification. | 3, with the F2/F4/F5 interaction | Open; codec readers and manifest recognition exist, writer migration is pending. The conditional Phase 6 frozen-matrix CSV route belongs to F2. |
| F3 — Mixed-run WMS identity | [#6](https://github.com/Cobblecat/OVTK/issues/6) | Exact-one-run validation and accepted identity on the same read snapshot used for queries. | 2 | Open; the identity component at `ba61169` passed checkpoint 5 review. Same-snapshot reader adoption and full F3/G2 qualification remain pending. |
| F4 — Unbound reconciliation reporting | [#7](https://github.com/Cobblecat/OVTK/issues/7) | Capture the accepted evidence set once, verify file/manifest/run/source/role binding, and use only captured inputs. | 4 | Open; reporting capture and binding are pending. |
| F5 — Unconditional empirical conclusions | [#8](https://github.com/Cobblecat/OVTK/issues/8) | Derive supported claims from one frozen evidence result and reuse it across reporting surfaces. | 4 | Open; claim derivation and reporting migration are pending. |
| F6 — Non-atomic output reservation | [#9](https://github.com/Cobblecat/OVTK/issues/9) | Invocation-owned private staging, qualified no-replace publication, ownership-safe cleanup, and fail-closed pair readiness. | 5, supporting 6 | Open; corrected foundation is accepted for the recorded Windows configuration, producer adoption is pending. |
| F7 — Unbounded QA/adjustment join | [#10](https://github.com/Cobblecat/OVTK/issues/10) | Exact bounded-processing replacement, cumulative work limits, and differential numerical/ordering checks. | 2 | Open; supplied limit contracts exist, algorithm replacement and approved product profiles are pending. |
| F8 — Schema-derived SQL identifier injection | [#11](https://github.com/Cobblecat/OVTK/issues/11) | Correct identifier handling and object policy within the accepted, bounded read boundary. | 2 | Open; snapshot infrastructure exists, identifier/object-policy adoption is pending. |

The eight issues are separate redacted public tracking records. Fuller technical disclosure is planned after implementation, required verification and review. Issue creation does not establish a verified fix, an affected release range or a patched distribution. Advisory posting was canceled at the owner's request; no GitHub advisory has been created or published as part of this remediation.

## Earlier source fixes and regression requirements

The following public GitHub issues were verified closed as completed on 2026-10-09. Their source-fix disposition remains separate from the eight findings above, later integration checks, and distributed-release status.

| Earlier fix | Source commit and issue | Integration requirement and limit |
| --- | --- | --- |
| PDF text escaping | [`f70d93e`](https://github.com/Cobblecat/OVTK/commit/f70d93e08d893e994a850c0ea658f73bb8410074), [issue #1](https://github.com/Cobblecat/OVTK/issues/1) | Escape supplied text once at ReportLab Paragraph insertion; preserve authored markup and canonical data. Resource operations were intercepted/blocked during earlier verification; actual retrieval or sensitive-file disclosure was not demonstrated. |
| WMS CSV protection | [`e5efb68`](https://github.com/Cobblecat/OVTK/commit/e5efb68352f9205f6d01ffd73e4b03b84453c7a2), [issue #2](https://github.com/Cobblecat/OVTK/issues/2) | Preserve existing presentation bytes and numeric objects. Apostrophe encoding is not reversible; do not strip apostrophes or stack the analytical codec. Earlier serialization tests did not qualify real spreadsheet applications. |
| Terminal escaping | [`3d43460`](https://github.com/Cobblecat/OVTK/commit/3d434602635dcd3ff528be2799b856b80b6c395a), [issue #3](https://github.com/Cobblecat/OVTK/issues/3) | Route new data and diagnostics through the shared terminal sink once; preserve trusted layout. Every terminal implementation and all Unicode display behavior have not been qualified. |

At the Phase 1 reviewed range and the checkpoint 5 identity component, the earlier production sinks are unchanged and 11 original security-test contracts are preserved. The completed Phase 2 candidate run includes the existing PDF, WMS CSV and terminal regression tests. Later phases must verify new callers and fields, not merely retain these tests.

## Commit and phase ledger

| Phase | Scope | Recorded status |
| --- | --- | --- |
| 0 / G0 | Evidence, affected compatibility contracts, ownership inventory and decisions. | Recorded passed for the contracts needed by Phase 1; dependent resource/spreadsheet decisions remain unresolved. |
| 1 / G1-W | Shared read, codec-reader, publication and routing foundations. | Five commits below; corrected foundations accepted for the recorded Windows configuration. |
| G1-P | Native POSIX foundation qualification. | Removed from required remediation gates by the owner's 2026-10-09 decision; unqualified and optional future work. |
| 2 / G2 | Database identity, snapshots, SQL identifiers and bounded analysis. | Identity component `ba61169` accepted at checkpoint 5. Further execution and implementation paused pending calibration preflight qualification; resource/workload decisions and G2 acceptance remain pending. |
| 3 / G3 | Versioned analytical writers and spreadsheet qualification. | Not started; consumer matrix approval and evidence required. |
| 4 / G4 | Captured reporting evidence and truthful claims. | Not started. |
| 5 / G5 | Output producer migration and no-replace publication. | Not started. |
| 6 / G6 | Confined release capture and release publication. | Not started; five-file layout compatibility decision remains pending. |
| 7 / G7 | Earlier-patch regression across the changed architecture. | Not started; prior-patch checks also apply during earlier phases. |
| 8 / G8 | Complete Windows workflow, platform and performance qualification. | Not started; Ubuntu qualification is outside the required scope. |
| 9 / G9 | Evidence accounting and owner acceptance. | Not started. |

Phase 1 commits:

- [`a9d97fa`](https://github.com/Cobblecat/OVTK/commit/a9d97fae33678fab71d2295a66b47f78da571051) — accepted read snapshot and supplied limit foundation.
- [`0ff0083`](https://github.com/Cobblecat/OVTK/commit/0ff00836914cbc1b7e3d5c2ff03f1dd77e0f094f) — recognized analytical manifests and codec-v1 readers.
- [`13078fe`](https://github.com/Cobblecat/OVTK/commit/13078fe33655c04c60d9b9d6c940b0522921f333) — Windows/NTFS publication lifecycle primitives.
- [`1876a47`](https://github.com/Cobblecat/OVTK/commit/1876a476931871ec95b59615cea8ad4f7888d015) — routing contracts and G0/G1-W evidence.
- [`5596678`](https://github.com/Cobblecat/OVTK/commit/5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c) — CPython/native AMD64 qualification correction and updated evidence; original four commits retained.

Phase 2 component commits:

- [`ba61169`](https://github.com/Cobblecat/OVTK/commit/ba61169f29b5d1209132c68514375ba79df62a4f) — singleton WMS metadata and consistent required-table run identity; three files changed, including 58 identity test cases. Accepted at checkpoint 5. F3 remains open pending reader integration and the complete G2 evidence.

Checkpoint numbers identify bounded work/review submissions within a phase; checkpoint 5 is not security Phase 5 or G5 acceptance.

Keep completed phases and corrections in separately scoped, traceable commits. Record the immutable commit, commands, environment, results, failures, compatibility checks and review decision before advancement. Explicit phase approval is required before the next phase begins. A failed gate or new issue stops the affected work; it is not waived by a later passing test count.

## Evidence at the reviewed commits

### Phase 1 foundations

See [Phase 1 gate record](PHASE1_GATE_RECORD.md) and [machine-readable gate evidence](phase1-gates.json).

Those records preserve the implementer's submission before the independent correction review. The later acceptance and owner platform-scope decisions above supersede their earlier advancement denial and POSIX gate dependency; the recorded commands, results and earlier failures remain unchanged.

- Recorded environment: Windows 11 Home/Core 25H2 x64 build 26200.9457, local fixed NTFS, CPython 3.14.6, SQLite 3.50.4 and locked dependencies.
- Pre-correction cumulative suite: 520 tests passed. Corrected candidate: 266 component and 540 cumulative tests passed, zero failures/errors/skips, one existing Windows/ZMQ warning. Lint, formatting and whitespace checks passed. Acceptance review inspected these receipts without rerunning OVTK tests.
- Recorded compatibility: 19 CSV files byte-identical and nine loaded reader tables equal, including dtypes, ordering and missingness.
- The initial review checked 75 indexed evidence digests and 16 changed candidate-file digests. The correction review checked 119 indexed entries (43 correction, 75 earlier, one collector receipt), matching hashes throughout, and verified the exact four-file correction range. All four execution manifests match; all 194 nongate files match executed bytes, with only the two gate records subsequently changed. This supports evidence identity, not comprehensive correctness.
- The initial sharing-fixture failure and its bounded correction were retained. The gate record explains the verified native precondition and positive control; no failed gate was erased or silently waived.
- The supplemental commit-preparation helper initially trimmed a meaningful leading space from Git status output. Its assertion stopped before staging. The corrected helper trims trailing newlines only, retaining the same source/index/path checks; both attempts are retained. No product test or security assertion was waived.

These are local recorded results for the candidate source represented by the reviewed commits. They are not signed remote CI evidence, qualification of every supported configuration, or closure of unimplemented controls.

### Phase 2 identity component — checkpoint 5

- Reviewed commit: `ba61169f29b5d1209132c68514375ba79df62a4f`; direct parent `69b08f4c10a46bc443d23b1e704ccb9c87e196a5`; tree `7d09d2a9c4cd69da1baa715dabb9cf08d1eb729f`. Exactly three paths changed: WMS validation, its repository adapter and the new identity tests. The immutable GitHub comparison and published branch identity were checked independently.
- The preserved cumulative candidate run passed **598 tests**, including **58 identity cases**, with zero failures/errors/skips and one existing Windows/ZMQ warning. Lint, formatting and relevant whitespace checks passed. The run used the recorded Windows/NTFS environment and locked dependencies; no new test run was performed during checkpoint 5 publication or acceptance review.
- All three committed component files match the executed source bytes. Other executable inputs are unchanged; five intervening narrative documents differ from the test-run checkout. Acceptance review independently verified all 33 indexed cumulative evidence files, 38 indexed publication files and eight controlling records. Evidence identity supports this component decision; it does not establish comprehensive security or complete Phase 2 qualification.
- Fresh compatibility comparisons preserve 19 CSV files byte-for-byte, nine loaded reader-table contracts, metadata, numerical/statistical results and summaries. Eleven earlier security-test contracts remain unchanged, and all three earlier patch commits remain ancestors.
- Identity coverage includes zero/one/multiple metadata rows, every required run-bearing table, missing/non-text/conflicting identities, explicit binary comparison despite differing collations, legitimate empty tables, foreign-key failures, recognized core schema routes and public describe/report rejection. The checked table set matches the independent WMS schema.
- The original interrupted cumulative attempt remains incomplete and retained separately. The later completed bounded retry is the test basis. A publication-evidence filename reuse was documented, with the actual preparation and verification records preserved separately; no product assertion or failed gate was waived.
- **Checkpoint 5 decision:** accept the identity component and continue the approved Phase 2 scope. The later calibration hold above pauses further execution and implementation without withdrawing this component acceptance. Same-snapshot adoption, F7/F8, measured resource profiles and individual, interaction, cumulative and performance qualification remain pending. G2, F3 closure and Phase 3 entry are not approved by this checkpoint.

## Compatibility, support and unresolved decisions

- Initial migrated-publication qualification targets Windows 11 25H2 Home/Core **x64**, local fixed **NTFS**, and **CPython 3.14.x**. Exact tested versions are recorded above. The corrected guard admits only a successful native-process/AMD64-host result. Substituted rejection cases do not qualify other native architectures or interpreters; approval of a configuration family is not evidence that every build passed.
- Ubuntu/native POSIX qualification is optional future work outside this remediation's required acceptance scope. A future support target requires separate approval and native component, interaction, prior-patch and complete-workflow evidence before enablement or a support claim. Migrated publication/release workflows reject unqualified platforms/filesystems; compatible unrelated read-only workflows retain their existing behavior.
- Approved legacy format/schema tuples retain their existing workflow support. Legacy text is not decoded by guessing a prefix. Unknown/contradictory declarations reject; no date cutoff or automatic removal is approved. Historical artifacts needing preservation have not been fully inventoried.
- Canonical database values, numerical results and deterministic artifacts remain compatibility requirements. PDF, terminal, WMS presentation CSV and analytical CSV encoding policies have distinct sinks and must not be stacked.
- Product resource ceilings, legitimate normal/largest workloads and spreadsheet application/build/locale/import-mode support remain unresolved for their dependent gates. The approved relative performance policy above requires measured calibration; absolute resource limits and support claims are not established by that approval.
- A new versioned five-file release directory is recommended but its user-visible output-path contract awaits approval. Preserve source/optional-ground-truth separation. Broader concurrent same-privilege release mutation guarantees have not been adopted.
- Every existing destination, including an empty directory, must reject under publish-new. Pair readiness is fail-closed; separate files are not a multi-file atomic transaction. Power-loss durability, automatic recovery, XLSX companions and automatic migration remain deferred.

## Closure and disclosure

Update each finding only when its implementation commit and required individual, interaction, earlier-patch and cumulative evidence support the stated disposition. Keep source-fix status, issue status, merged branch status, distributed release status and advisory status separate. The reviewed remediation remains on its separate branch; `main` remains at `5931b15`. No patched distributed release or affected release range is established by these branch commits.

Report potential vulnerabilities through [SECURITY.md](../../SECURITY.md). Private assessment materials and reproduction details should remain in the private reporting/review channel. This status document is not a disclosure authorization or a claim of comprehensive security.
