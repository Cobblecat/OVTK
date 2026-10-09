# Source Release Manifest

The canonical version is defined in `pyproject.toml`. The `package-release` workflow creates a
versioned local source ZIP with a machine-readable `RELEASE_MANIFEST.json` and internal
`SHA256SUMS.txt`.

The source archive includes:

- source code, tests, configuration, and dependency lockfile;
- documentation, reference materials, notebook source, license, changelog, and release notes;
- curated synthetic schema-3 SQLite examples and standard WMS report CSVs;
- accepted reconstruction and frozen statistical outputs with portable provenance paths;
- executed notebook, figures, exhibit tables, executive report, and technical appendix; and
- clean reproduction instructions.

It excludes Git internals, virtual environments, caches, IDE state, temporary files, scratch
outputs, SQLite WAL/SHM files, credentials, machine-specific paths, and restricted ground truth.

Restricted ground truth is packaged only in the separately named optional spoiler ZIP. That archive
contains its own warning, manifest, and checksums and is never an ordinary analyst input.
