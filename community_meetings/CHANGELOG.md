# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings 18.0.6.2.3 (2026-10-19)
=============================================

## Release notes

### Features

- Editors and approvers can preview the saved minutes draft from the meeting form or live screen before approval. The preview excludes private editorial notes and does not create the official PDF; approval still creates the immutable revision and PDF.
- Meeting series can define recurring agenda point templates. Selected templates create independent points in each meeting and link to the previous occurrence.

## Internal changes

- **lint-migration** — Refresh lint and formatting conventions for the supported pre-commit toolchain.
- **ci-formatting** — Normalize audit remediation sources and tests for the repository formatting and lint checks.
- **addon-changelog** — Generate an addon-local changelog during release preparation.
