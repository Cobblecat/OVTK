# Getting help

OVTK is a local, synthetic-data project maintained by [Cobblecat](https://github.com/Cobblecat). Start with the [README](README.md), [project status](PROJECT_STATUS.md), [WMS and SQL guide](docs/27_WMS_USER_AND_SQL_GUIDE.md), and [release and reproduction guide](docs/28_RELEASE_AND_REPRODUCTION_GUIDE.md).

## Setup and workflow questions

Use the **Help or usage question** issue template. Include your goal, the documentation you followed, the exact command, and the result you expected. Generated databases and release artifacts are not required to be checked into the repository; the source workflows create them at new paths.

The source requires Python 3.14 or newer and `uv`. From the repository root, install the locked environment with `uv sync --frozen`. The README quick start generates a synthetic baseline without relying on a pre-existing sample database.

## Bugs and feature requests

Search [existing issues](https://github.com/Cobblecat/OVTK/issues?q=is%3Aissue) before opening a report. Use the matching template and provide:

- a commit hash or package version;
- operating system, Python version, and `uv` version;
- a minimal command sequence using synthetic inputs;
- expected and actual behavior; and
- relevant error output with personal paths and confidential details removed.

For a feature request, explain the warehouse or investigation workflow, the problem it solves, and how success could be checked. Proposed behavior should preserve deterministic generation, source immutability, and the analyst/ground-truth boundary.

## Security reports

Follow [SECURITY.md](SECURITY.md) and use private vulnerability reporting. Do not post vulnerability payloads, credentials, or sensitive files in public issues.

## Project scope

This project does not provide production WMS operations, employer-data handling, or a commercial support service. Response times depend on maintainer availability. Historical acceptance results and unreleased source capabilities are described separately in the project status and changelog.
