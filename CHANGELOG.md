# Changelog

All notable changes to this project are documented here.

## Unreleased

### Security remediation foundations - 2026-10-09

- Begin the separate, phase-gated security remediation on `remediation/phase1-foundations`, based on [`5931b15`](https://github.com/Cobblecat/OVTK/commit/5931b15c1838e83c37217e385e74a6db13afe6bf). Track the eight findings, three earlier patches, phase decisions, and remaining limits in the [security remediation status](docs/security/REMEDIATION_STATUS.md). Security phase numbers are separate from the product-development milestones.
- Add a read-only SQLite snapshot context with validated identity, explicit supplied limits, progress cancellation, and transaction-escape restrictions in [`a9d97fa`](https://github.com/Cobblecat/OVTK/commit/a9d97fae33678fab71d2295a66b47f78da571051). Database workflow adoption remains a later phase.
- Add strict manifest recognition and declared codec-v1 analytical readers in [`0ff0083`](https://github.com/Cobblecat/OVTK/commit/0ff00836914cbc1b7e3d5c2ff03f1dd77e0f094f). Recognized legacy inputs keep raw text semantics without prefix guessing. Analytical writer migration and real spreadsheet qualification remain pending; WMS presentation CSV bytes and canonical numeric values remain unchanged.
- Add private staging, ownership-aware cleanup, no-replace publication primitives, and sidecar-first/database-last readiness ordering in [`13078fe`](https://github.com/Cobblecat/OVTK/commit/13078fe33655c04c60d9b9d6c940b0522921f333). Producer migration remains pending. These primitives do not provide a multi-file atomic transaction, power-loss durability, or automatic recovery.
- Record routing contracts and G0/G1-W implementation evidence in [`1876a47`](https://github.com/Cobblecat/OVTK/commit/1876a476931871ec95b59615cea8ad4f7888d015). Independent review initially withheld Phase 1 acceptance and Phase 2 advancement because the publication qualifier did not fully enforce the approved CPython/native x64 restriction. A bounded Phase 1 correction was required within the existing publication finding.
- Complete that qualification correction in [`5596678`](https://github.com/Cobblecat/OVTK/commit/5596678448e54a20b1f3ec7fa2d9f3caaed9ec0c), retaining the four earlier commits. Require CPython 3.14 and a successful native-process/AMD64-host probe before staging; reject unsupported, failed, unavailable, or indeterminate results. Phase 1/G1-W was accepted for the recorded Windows configuration, and Phase 2 entry was approved after documentation integration. Dependent product decisions and later gates remain required.

### Remediation platform scope - 2026-10-09

- Record the owner's decision to remove Ubuntu/native POSIX qualification from the required remediation gates, including final acceptance. Windows qualification and all applicable security, compatibility, prior-patch, workflow, and performance gates remain required. Ubuntu support is unqualified; any future enablement requires separate approval and evidence. The decision changes the acceptance scope, with no application behavior or historical test evidence changed.

### Security remediation evidence and limitations - 2026-10-09

- The recorded Phase 1 candidate run passed 520 tests, with one Windows/ZMQ warning, on Windows 11 Home/Core 25H2 x64 build 26200.9457, local fixed NTFS, CPython 3.14.6, and SQLite 3.50.4. Recorded lint, formatting, and whitespace checks passed. Acceptance review inspected results and source identity without rerunning the test suite.
- The corrected candidate passed 266 component tests and 540 cumulative tests, with zero failures/errors/skips and the same warning. Native positive publication and 20 added qualification cases passed; substituted architecture results establish guard logic rather than native qualification of other machines. Acceptance review verified 119 indexed evidence entries, matching executed source bytes, and the immutable correction range. A supplemental commit-preparation parser false positive was retained and corrected without changing product/test inputs or waiving an assertion.
- Captured compatibility evidence retained 19 CSV files byte-for-byte and nine loaded reader tables, including numerical values, dtypes, ordering, and missingness. The three earlier security patch sinks remained unchanged and 11 original security-test contracts were preserved. These comparisons cover the captured fixtures, not every historical artifact or consumer.
- The eight findings remain open pending their implementation, grouped regression checks, cumulative qualification, and explicit acceptance. Product resource profiles and spreadsheet application/build/locale/import-mode qualification remain pending. No merged remediation, patched distributed release, affected release range, advisory, or CVE is established by this branch work.

### Repository documentation - 2026-10-09

- Add security, support, conduct, and accessibility guidance with structured issue and pull request templates.
- Expand contribution instructions, add a fresh-checkout quick start, and align the README console description with completed Phase 2 and Phase 3 source capabilities.
- Populate repository description, documentation link, topics, and social preview; enable private vulnerability reporting.

### Security fixes - 2026-10-09

- Escape supplied report text at PDF Paragraph boundaries while preserving application-owned markup and figure handling. Fixed in [f70d93e](https://github.com/Cobblecat/OVTK/commit/f70d93e08d893e994a850c0ea658f73bb8410074); [issue #1](https://github.com/Cobblecat/OVTK/issues/1) closed as completed.
- Encode hazardous strings in every spreadsheet-facing WMS CSV column, including identifiers, references, and leading whitespace/control prefixes. Preserve numeric objects, canonical stored data, and deterministic, non-overwriting exports. Fixed in [e5efb68](https://github.com/Cobblecat/OVTK/commit/e5efb68352f9205f6d01ffd73e4b03b84453c7a2); [issue #2](https://github.com/Cobblecat/OVTK/issues/2) closed as completed.
- Display C0, DEL, and C1 controls as visible text across console and CLI data output, prompts, and errors while preserving trusted output structure and printable Unicode. Include the argparse diagnostic gap identified by the independent audit. Fixed in [3d43460](https://github.com/Cobblecat/OVTK/commit/3d434602635dcd3ff528be2799b856b80b6c395a); [issue #3](https://github.com/Cobblecat/OVTK/issues/3) closed as completed.

### Verification - 2026-10-09

- Independently reviewed the fixes and completed guarded checks in disposable copies using existing locked dependencies: 451 full-suite tests and 145 focused output/CSV/CLI tests passed. The full suite reported one Windows/ZMQ warning. Original-code negative controls failed as expected; lint, formatting, and Git whitespace checks passed. Original scan and fix evidence was preserved.
- Verified ReportLab 5.0.0 literal parsing and inspected its local-file-first resource handling and rejection of URL fallback with `trustedHosts=None`. Tests intercepted or blocked resource operations; no real external retrieval or sensitive-file disclosure was tested. Spreadsheet application interoperability, arbitrary Unicode PDF glyph/layout behavior, and behavior across all terminals remain outside the verified scope.
- These are published source fixes. No patched distributed release or affected release range was established, and no release, tag, advisory, or CVE was created as part of this work. Issue closures record verified source remediation.

### Documentation cleanup for public release

Standardized planning language, clarified review checkpoints, and updated attribution. No application behavior changed.

## 0.1.0 - 2026-08-02

### Added

- Deterministic schema-3 miniature WMS with live inventory and immutable audit history.
- External physical simulation and scenario overlays for three controlled investigation patterns.
- Standard WMS reports, three-way reconstruction, and truth-blind statistical investigation.
- Frozen-output notebook, traceable exhibits, executive report, and technical appendix.
- Leakage-checked local source and optional restricted-ground-truth release archives.

### Release Policy

- Licensed under the MIT License.
- Requires Python 3.14 or newer; release acceptance was performed with Python 3.14.
- Restricted ground truth is available only in a separately named optional spoiler archive.
- No XLSX exhibit packet is included in the initial release.
