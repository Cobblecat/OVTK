# Changelog

All notable changes to this project are documented here.

## Unreleased

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
