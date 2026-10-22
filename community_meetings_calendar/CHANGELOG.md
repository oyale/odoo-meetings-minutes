# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings Calendar 18.0.1.0.5 (2026-10-22)
======================================================

## Release notes

### Misc

- 58-selector-migration, scheduling-preflight

## Internal changes

- **generated-description-refresh** — The generated marketplace description now matches the current addon README.
- **scheduling-preflight** — Calendar meeting scheduling now uses the shared access and state preflight before validating calendar-specific end times.
- **58-selector-migration** — Calendar browser selectors for translated UI messages now resolve those messages from the addon translation catalog.

## Community Meetings Calendar 18.0.1.0.4 (2026-10-21)
======================================================

## Release notes

### Improved Documentation

- Clarify in the English and Spanish guides that meeting changes update the linked Calendar event and cancellation removes it.

## Community Meetings Calendar 18.0.1.0.3 (2026-10-20)
======================================================

## Release notes

### Bugfixes

- Scheduling a meeting without a start date now shows the required date and time validation before checking the Calendar event interval.

## Internal changes

- **acceptance-coverage** — Added end-to-end acceptance scenarios for linked Calendar navigation, event cancellation, synchronization, and unlinked events.

## Community Meetings Calendar 18.0.1.0.2 (2026-10-19)
======================================================

## Internal changes

- **lint-migration** — Refresh lint and formatting conventions for the supported pre-commit toolchain.
- **ci-formatting** — Normalize audit remediation sources and tests for the repository formatting and lint checks.
- **addon-changelog** — Generate an addon-local changelog during release preparation.
