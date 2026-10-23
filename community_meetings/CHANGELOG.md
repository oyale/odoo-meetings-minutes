# Changelog

Addon release notes. For suite-wide summaries, see the [suite changelog](../CHANGELOG.md).

<!-- towncrier release notes start -->

## Community Meetings 18.0.6.2.10 (2026-10-23)
==============================================

## Release notes

### Bugfixes

- Focus mode fits the active point card in the available height by shrinking the discussion editor, and the Enlarge editor control still expands it when needed.
- Focus mode keeps the point card compact before the point starts, expands it to the available height when the editor appears, and keeps the card in view when the point starts.

## Internal changes

- Remove unsupported QWeb t-key attributes from the minutes report so the Odoo log checker sees a clean render.

## Community Meetings 18.0.6.2.9 (2026-10-23)
=============================================

## Release notes

### Features

- Agreements and dissents in meeting minutes render as cards, like follow-up
  actions, including their decision and agreement status.
- An expanded agenda point shows its responsible person, point type, estimate and
  priority aligned with the point title. In focus mode the discussion editor uses
  more of the available height and keeps the enlarge/reduce control.
- Approved minutes show a single revision sentence with the meeting code, the
  approval source (later agenda point, offline preparation, live meeting or
  manual approval), the localized approval date and the timezone. The point name
  is not repeated in the sentence.
- Automatically added recurring and structural agenda points use the meeting
  organizer as responsible when no explicit responsible is configured.
- Meeting minutes show the actual start and end, each point's proposer, status,
  related points and decision details, the destination of moved points, and
  follow-up actions with their origin, kind, activity type, responsible, due date
  and status. Same-day meetings show only the end time, a compact header omits
  empty fields and repeated time zones, and empty description or minutes sections
  are omitted.
- Meetings with approved minutes expose an "Approved Minutes" action from the
  meeting form, the meeting list and the live meeting. It opens the approved
  revision in the minutes preview and returns to the screen where it was opened.
- Mentions in discussion notes render as a themed chip in the active brand
  colour. The recorded text and the minutes PDF are unchanged.
- Minutes show each point's proposer, status and transfer destination in a
  consistent summary row with status chips. The follow-up origin label is
  translated.
- The meeting list can filter meetings by approved status.
- The minutes report lists the actas approved from a minutes-approval point,
  including each approved meeting's code, name, revision and date.

### Bugfixes

- Dissents and reservations in meeting minutes now appear inside the agenda point and agreement they belong to, rather than in a separate report section.
- Long presenter, status and transfer labels in the minutes preview now wrap inside the report instead of overflowing the page.
- Older approved revisions keep their recorded dissents inside the agenda point after the minutes report layout change.
- Postponed points use an hourglass icon, collapse after being marked done or
  postponed in the full agenda, and no longer count as unresolved when finishing
  the meeting. A collapsed point keeps its next-meeting review badge and an undo
  control visible.
- The back button in a live meeting returns to the meeting that opened it when
  you arrive from a related point or from reviewing approved minutes, instead of
  going to the meetings list.
- The minutes-approval point shows its approved previous minutes in held and
  read-only meetings, not only while the point is editable.
- Trying to save an agreement without a title now shows a warning explaining that
  a title is required.

### Improved Documentation

- The English and Spanish minutes preview documentation screenshots now show a realistic meeting with presenters, decisions, follow-ups and a dissent.
- The English and Spanish minutes preview documentation screenshots show a dissent inside its agenda point.

## Internal changes

- Add a browser capture fixture that builds a representative meeting for the minutes preview documentation screenshots.

## Community Meetings 18.0.6.2.8 (2026-10-23)
=============================================

## Release notes

### Features

- Type @ in an editable point's discussion to attribute an intervention to a contact. Mentions preserve the recorded name in notes and minutes without notifying the person or granting meeting access.

### Bugfixes

- Returning from live notes to a form no longer resubmits unchanged rich text after server sanitization. Edits made while a save is pending remain marked as unsaved until their own save completes.
- Ordinary agenda additions, including imports and accepted carryovers, obey the meeting’s configured addition deadline. Enabling previous-minutes approval can still insert its required structural point into existing draft, scheduled, held or minutes-draft meetings.
- Every proposal admission requires an authorized reviewer and records the reviewer and response date. After upgrading, earlier admissions without a completed recorded review keep their operational state and display an explicit historical status.
- Minutes previews and approved revisions now include the agreed next-meeting date and time, displayed in the minutes timezone and frozen with the approved PDF.
- Changing company or series time-tracking defaults during a live meeting no longer disables that session's timers; pausing and resuming also updates the live controls immediately.
- Earlier meetings whose minutes are still in Held state are marked as awaiting preparation and cannot be approved from a later meeting until their minutes enter draft.
- A meeting that has started can no longer be cancelled; finish it as Held to close its timers and preserve the actual session history.
- Earlier minutes that are still held can be prepared from the later meeting's live approval point before review and approval. The minutes preview scrolls, and refreshing it preserves the meeting and return point.

### Improved Documentation

- The English and Spanish live-meeting guides explain person attribution with @, contact visibility, and how recorded names are preserved without notifications.

## Internal changes

- Regression coverage checks that empty approval queues and readers without approval authority are handled correctly.
- Regression coverage includes empty agreed meeting dates, amendment snapshots, and read-only access to the previous-minutes approval queue.
- Browser diagnostics handle RPC responses evicted during navigation and capture rendered evidence when live-screen setup fails.
- Concurrency tests can synchronize independent database transactions.
- The invitee-priority regression test isolates candidate ranking from database collation differences.

## Community Meetings 18.0.6.2.7 (2026-10-22)
=============================================

## Release notes

### Features

- The live meeting view now supports scheduling and cancelling draft meetings, and exposes agenda reordering in every phase allowed by the meeting policy. Controls sit to the left of agenda cards on desktop and above them on mobile, where they provide larger touch targets.
- Meeting editors can move agenda points up or down in preparation and during a live meeting, within a company or series policy. The order is locked when the meeting is marked held; minutes-approval and next-meeting points retain their structural positions. (agenda-point-reordering)
- All recorded dissents are included in minute previews and approved revisions.
  The inclusion checkbox has been removed; private editorial notes remain
  separate from the minutes.

### Bugfixes

- Follow-up type policies now inherit from the most specific point through the series to the company, and an empty effective policy no longer crashes the defaults wizard. (follow-up-policy-inheritance)
- Repeated requests to add a recurring agenda point to a meeting now reuse the existing occurrence. (recurring-point-idempotency)
- Changing meeting details no longer raises an Odoo error while agenda rows are still being edited; move controls remain ordered by agenda sequence.
- The web client now declares the signed-in user's interface language and shows Spanish translations for JavaScript control names.
- Agenda review reasons for submitted proposals now follow the active user's interface language.

## Internal changes

- Carryover destinations are checked by one shared validator from both the wizard and model flows.
- Meeting scheduling uses a shared transition hook that also validates Calendar-specific end times.
- Browser checks cover agenda reordering across supported phases, verify desktop and mobile control placement, distinguish cancelling attendee edits from cancelling a meeting, and resolve localized labels from each addon's translation catalog.
- Browser checks report save errors when closing an unsaved meeting wizard.
- Named screenshot checkpoints share viewport and retention settings, and the capture policy has direct unit tests.
- The addon and shared browser support now pass the configured Python lint and formatting checks.

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
