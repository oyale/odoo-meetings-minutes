# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings 18.0.6.2.6 (2026-10-21)
=============================================

## Release notes

### Bugfixes

- Approved minutes now show the meeting time in the series timezone, falling back to the company timezone and then UTC. Draft previews show the viewer's timezone.
- Recording or moving a decision agreement that would duplicate another active agreement now raises a normal validation error instead of a database uniqueness error.

## Internal changes

- **coverage-resolution-guards** — Add regression coverage for resolution authorization, link consistency, duplicate agreements, and approved-minute locks.
- **coverage-approval-revision-guards** — Add regression coverage for minutes approval authorization, revision immutability, PDF access, and PDF failure rollback.

## Community Meetings 18.0.6.2.5 (2026-10-21)
=============================================

## Release notes

### Features

- A series can require earlier minutes to be approved from a later meeting. The assigned minutes secretary reviews and approves them from that meeting: during a live meeting, the secretary also needs the Editor role and edit access; for an offline meeting, the secretary can approve while preparing its minutes. Enabling the route adds its approval point to existing eligible meetings, and the point remains while approval is required. Approval history records the exact revision approved, including amendments.
- Meeting series now have a chatter. Changes to series settings are tracked, including coordinator, attendee, and allowed follow-up type membership changes. Existing series do not receive backfilled history for changes made before this feature was installed.
- Reviewing earlier minutes opens a read-only preview of the draft, available to anyone with read access to the meeting and rendered in that user’s language. Draft previews and approved minutes number agenda points consecutively for presentation, including structural points. The return action is translated, and returning takes the user back to the live meeting without pausing its running point timer.
- The persistent meeting form puts scheduling details beside meeting people and series on desktop, then stacks these sections on narrow screens.

### Bugfixes

- Clicking a series point estimate selects its current value; typing replaces it and saves the updated estimate.
- Live meeting notes no longer save empty editor markup, and edits from different points are serialized per meeting to avoid concurrent workflow lock retries.

### Improved Documentation

- Clarify draft preview access and return behavior, restoring earlier discussion, and the manager role required to start a minutes amendment in the English and Spanish guides.

## Internal changes

- **reader-preview-acceptance** — Align the reader preview acceptance scenario with the meeting read-access policy.
- **spanish-carryover-error-regression** — Add Odoo regression coverage for Spanish carryover error messages when es_ES is installed.
- **priority-acceptance-coverage** — Add native acceptance journeys for rejecting proposals and dismissing carryovers, and verify saved series wizard defaults through the browser.
- **preview-return-acceptance** — Check that returning from draft preview preserves saved meeting data and link acceptance scenarios to user guides and remaining coverage gaps.
- **meeting-visual-browser-evidence** — Extend browser evidence for the meeting preparation flows in English and Spanish, including mobile layouts, keyboard interaction, long attendee lists, and responsive form reflow.

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

- Users with read access to the meeting, including Readers, can preview the saved minutes draft from the meeting form or live screen before approval. The preview excludes private editorial notes and does not create the official PDF; approval still creates the immutable revision and PDF.
- Meeting series can define recurring agenda point templates. Selected templates create independent points in each meeting and link to the previous occurrence.

## Internal changes

- **lint-migration** — Refresh lint and formatting conventions for the supported pre-commit toolchain.
- **ci-formatting** — Normalize audit remediation sources and tests for the repository formatting and lint checks.
- **addon-changelog** — Generate an addon-local changelog during release preparation.
