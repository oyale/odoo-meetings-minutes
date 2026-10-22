# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings Project 18.0.3.1.7 (2026-10-22)
=====================================================

## Release notes

### Bugfixes

- Project task follow-up types now respect configured policies and are only offered to users with Project access. (project-follow-up-policy)
- The Project task wizard now displays its context and follow-up headings in Spanish when the Odoo interface is Spanish. (project-task-wizard-translations)

## Internal changes

- The generated marketplace description matches the current addon README.
- Project browser and acceptance checks resolve translated interface labels from the addon's translation catalog.

## Community Meetings Project 18.0.3.1.6 (2026-10-21)
=====================================================

## Internal changes

- **coverage-private-project-task-links** — Add regression coverage for privacy of inaccessible project task links.

## Community Meetings Project 18.0.3.1.5 (2026-10-21)
=====================================================

## Release notes

### Features

- Project destination and task policy changes on meeting series are now recorded in the series chatter.

## Internal changes

- **project-followup-browser-coverage** — Extend the Project follow-up wizard browser coverage to review context, link an existing task without creating a duplicate, and check the compact layout with Calendar installed.

## Community Meetings Project 18.0.3.1.4 (2026-10-20)
=====================================================

## Internal changes

- **alternate-project-selector-browser** — Corrected the alternate-project browser check to assert that the project input is hidden before enabling the option and visible afterwards.
- **acceptance-coverage** — Added end-to-end acceptance scenarios for creating and linking Project tasks from meeting follow-ups.

## Community Meetings Project 18.0.3.1.3 (2026-10-19)
=====================================================

## Internal changes

- **lint-migration** — Refresh lint and formatting conventions for the supported pre-commit toolchain.
- **ci-formatting** — Normalize audit remediation sources and tests for the repository formatting and lint checks.
- **addon-changelog** — Generate an addon-local changelog during release preparation.
