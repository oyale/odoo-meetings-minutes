# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings Project 18.0.3.1.10 (2026-11-20)
======================================================

## Release notes

### Bugfixes

- Linked Project task names now appear on live meeting agenda follow-ups, alongside the Project task details shown in meeting forms and minutes previews.
- Linked Project tasks in the live agenda now open from a compact, aligned action beside the follow-up type and status.

### Improved Documentation

- The English and Spanish browser documentation fixtures use representative project, task and meeting details instead of generic test labels.
- The English and Spanish follow-up guide now shows a linked Project task opened from a live meeting follow-up, with realistic meeting, task, project and owner details.

## Community Meetings Project 18.0.3.1.9 (2026-11-05)
=====================================================

## Release notes

### Bugfixes

- Minutes previews and newly approved minutes now show the name, optional due date, and task assignees for each readable linked Project task, separately from the follow-up's responsible people. Approved minutes retain the task details captured when they were approved.

## Community Meetings Project 18.0.3.1.8 (2026-10-23)
=====================================================

## Release notes

### Bugfixes

- Retrying series creation with a new Project no longer creates duplicate projects or changes the series' existing project link.

## Internal changes

- Generated marketplace description metadata is up to date.
- Regression coverage confirms a failed series and Project wizard finish rolls back the created series.

## Community Meetings Project 18.0.3.1.7 (2026-10-22)
=====================================================

## Release notes

### Bugfixes

- Project task follow-up types now respect configured policies and are only offered to users with Project access. (project-follow-up-policy)
- The Project task wizard now displays its context and follow-up headings in Spanish when the Odoo interface is Spanish. (project-task-wizard-translations)

## Internal changes

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
