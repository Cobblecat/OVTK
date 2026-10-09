# Security policy

OVTK is a local toolkit for deterministic synthetic warehouse operations and inventory-variance investigation. It is not designed as a production WMS or a hosted service.

## Reporting a vulnerability

Use **Report a vulnerability** on the [security advisories page](https://github.com/Cobblecat/OVTK/security/advisories) to send a private report to the repository maintainer, Cobblecat. Please keep potential vulnerabilities out of public issues until the report has been reviewed and a disclosure plan agreed.

Include:

- the affected commit or package version and your operating system;
- the command or workflow involved, with relevant Python and dependency versions;
- expected behavior, observed behavior, and the security boundary affected;
- a minimal reproduction using synthetic data in a disposable local copy; and
- the impact you observed, distinguished from possible impact that has not been demonstrated.

Do not include credentials, employer records, personal information, or confidential files. Do not test third-party systems or attempt to retrieve sensitive files or external resources to demonstrate impact.

If private reporting is unavailable, open an issue requesting a private contact method without disclosing vulnerability details.

## Current source and release status

Security fixes are recorded in the [changelog](CHANGELOG.md) with their source commits. Reports against current `main` are welcome; identify the exact revision so the behavior can be reproduced.

A source fix does not establish that an older ZIP or generated release artifact contains the fix. Historical version `0.1.0` archives and preparation snapshots must be checked against their recorded revision. No maintained backport schedule or response-time guarantee is established.

## Security boundaries and review priorities

Review changes against these project requirements:

- Accepted source databases and historical artifacts remain immutable. Ordinary inquiry and analysis use read-only connections.
- Sandbox identity and provenance must be verified before a sandbox workflow is accepted. Sandbox mode does not authorize arbitrary SQL or unrestricted writes.
- Outputs use new destinations and retain no-overwrite protections, deterministic serialization, and traceable checksums.
- Database and report text remain data at terminal, PDF, and spreadsheet-facing output boundaries. Application-owned formatting must remain distinct from supplied text.
- Analyst workflows do not load restricted ground truth. Optional truth artifacts remain separate and clearly identified.
- Configuration and named random streams preserve reproducibility. Findings retain the claim-strength limits of the statistical guardrails.
- Contributions contain synthetic data only and do not introduce credentials or confidential operational information.

See the [architecture](docs/03_ARCHITECTURE.md), [statistical guardrails](docs/14_STATISTICAL_GUARDRAILS.md), and [release guide](docs/28_RELEASE_AND_REPRODUCTION_GUIDE.md) for the governing technical contracts.

## Disclosure

The maintainer will review reports, agree on any necessary follow-up, and coordinate public documentation of confirmed fixes. Avoid publishing sensitive reproduction details before that coordination is complete. This project does not advertise a paid bounty program.
