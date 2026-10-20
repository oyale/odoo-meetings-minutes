# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings 18.0.6.2.4 (2026-10-20)
=============================================

## Release notes

### Features

- Continued agenda points can show earlier discussion as read-only context, with an option to start without it. Recurring agenda templates can choose whether new occurrences show previous discussion.

### Bugfixes

- Fixed agenda point type choices so arrow-key navigation works while rich choices are collapsed and assistive technologies announce the selected state.

### Improved Documentation

- Added an extraordinary-meeting example to the Spanish guide on moving an agenda point to another series.

## Internal changes

- **postponement-browser-synchronization** — Waited for point resumption and expanded collapsed controls before postponing an approved decision in the browser regression.
- **secretary-browser-identity** — Selected and verified the minutes secretary by user ID in browser checks, allowing display names to differ from login names.
- **focused-browser-test-selection** — Updated the full browser runner to accept qualified test selectors and fail when no tests match.
- **carryover-browser-controls** — Updated carryover browser checks to use the current Accept/Discard controls and carry-forward message, including persistence of the selected choice.
- **browser-series-fixture-names** — Used unique series names in structural-point and previous-minutes browser fixtures to avoid collisions on repeated runs.
- **draft-minutes-preview-browser** — Added a browser regression for opening saved draft minutes, returning to the meeting, and preserving the draft state.
- **approver-browser-session** — Verified the resulting approval state through the approver browser session in the approver-only regression.
- **acceptance-coverage** — Added end-to-end acceptance scenarios for meeting lifecycle, agenda preparation, proposals, carryovers, minutes preview, discussion history, and recurring points.

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
