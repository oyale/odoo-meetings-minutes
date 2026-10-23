# Changelog

User-facing changes to the Odoo Meetings Minutes suite. Each release records
the exact Odoo addon version included in the published suite packages.
History below starts at `18.0.20261018.2`; earlier suite releases are not backfilled.
Each addon changelog starts with its first release prepared after this change;
the combined history below retains the existing suite release notes.

<!-- towncrier release notes start -->
## Odoo Meetings Minutes 18.0.20261023.1 (2026-10-23)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.9` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.6` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.8` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

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
## Calendar Integration

No significant changes.
## Project Integration

No significant changes.
## Extension Demo

No significant changes.
## Odoo Meetings Minutes 18.0.20261023.0 (2026-10-23)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.8` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.6` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.8` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

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

## Calendar Integration

No user-facing changes.

## Project Integration

### Bugfixes

- Retrying series creation with a new Project no longer creates duplicate projects or changes the series' existing project link.
## Extension Demo

No significant changes.
## Odoo Meetings Minutes 18.0.20261022.0 (2026-10-22)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.7` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.5` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.7` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

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

## Project Integration

### Bugfixes

- Project task follow-up types now respect configured policies and are only offered to users with Project access. (project-follow-up-policy)
- The Project task wizard now displays its context and follow-up headings in Spanish when the Odoo interface is Spanish. (project-task-wizard-translations)

## Extension Demo

No significant changes.
## Odoo Meetings Minutes 18.0.20261021.1 (2026-10-21)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.6` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.4` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.6` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

### Bugfixes

- Approved minutes now show the meeting time in the series timezone, falling back to the company timezone and then UTC. Draft previews show the viewer's timezone.
- Recording or moving a decision agreement that would duplicate another active agreement now raises a normal validation error instead of a database uniqueness error.
## Calendar Integration

No significant changes.
## Extension Demo

No significant changes.
## Odoo Meetings Minutes 18.0.20261021.0 (2026-10-21)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.5` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.4` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.5` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

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
## Calendar Integration

### Improved Documentation

- Clarify in the English and Spanish guides that meeting changes update the linked Calendar event and cancellation removes it.
## Project Integration

### Features

- Project destination and task policy changes on meeting series are now recorded in the series chatter.
## Extension Demo

No significant changes.
## Odoo Meetings Minutes 18.0.20261020.0 (2026-10-20)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.4` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.3` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.4` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

### Features

- Continued agenda points can show earlier discussion as read-only context, with an option to start without it. Recurring agenda templates can choose whether new occurrences show previous discussion.

### Bugfixes

- Fixed agenda point type choices so arrow-key navigation works while rich choices are collapsed and assistive technologies announce the selected state.

### Improved Documentation

- Added an extraordinary-meeting example to the Spanish guide on moving an agenda point to another series.
## Calendar Integration

### Bugfixes

- Scheduling a meeting without a start date now shows the required date and time validation before checking the Calendar event interval.
## Extension Demo

No significant changes.
## Odoo Meetings Minutes 18.0.20261019.3 (2026-10-19)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| [Community Meetings](community_meetings/CHANGELOG.md) | `18.0.6.2.3` |
| [Calendar Integration](community_meetings_calendar/CHANGELOG.md) | `18.0.1.0.2` |
| [Project Integration](community_meetings_project/CHANGELOG.md) | `18.0.3.1.3` |
| [Extension Demo](community_meetings_extension_demo/CHANGELOG.md) | `18.0.1.0.1` |

=====================================================

## Community Meetings

### Features

- Editors and approvers can preview the saved minutes draft from the meeting form or live screen before approval. The preview excludes private editorial notes and does not create the official PDF; approval still creates the immutable revision and PDF.
- Meeting series can define recurring agenda point templates. Selected templates create independent points in each meeting and link to the previous occurrence.
## Odoo Meetings Minutes 18.0.20261019.2 (2026-10-19)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| Community Meetings | `18.0.6.2.2` |
| Calendar Integration | `18.0.1.0.1` |
| Project Integration | `18.0.3.1.2` |
| Extension Demo | `18.0.1.0.0` |

### Community Meetings

#### Bugfixes

- Preserve execution-evidence checks supplied by addons when validating resolved TODOs.

### Calendar Integration

No user-facing changes.

### Project Integration

#### Bugfixes

- Serialize task deletion with TODO closure so a resolved TODO keeps its required Project task.

### Extension Demo

No significant changes.

## Odoo Meetings Minutes 18.0.20261019.1 (2026-10-19)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| Community Meetings | `18.0.6.2.1` |
| Calendar Integration | `18.0.1.0.0` |
| Project Integration | `18.0.3.1.1` |
| Extension Demo | `18.0.1.0.0` |

### Community Meetings

#### Features

- The Add Point wizard offers visual agenda type cards with behavior guidance. The New Meeting and New Series wizards group choices with contextual help, clear field labels, and scannable reviews.
- The meeting creation review warns when the selected agenda, including automatic points, exceeds the estimated meeting duration.

### Calendar Integration

No significant changes.

### Project Integration

#### Features

- The Project task wizard now shows the linked follow-up's title, owners and deadline as read-only context, and separates existing task selection from creating a new task.

### Extension Demo

No significant changes.

## Odoo Meetings Minutes 18.0.20261018.2 (2026-10-18)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| Community Meetings | `18.0.6.2.0` |
| Calendar Integration | `18.0.1.0.0` |
| Project Integration | `18.0.3.1.0` |
| Extension Demo | `18.0.1.0.0` |

### Community Meetings

#### Features

- Added a dedicated Community Meetings icon to the Odoo app launcher.
- The point preparation form keeps priority, estimated duration and deadline together, makes related points available in the main flow, and reserves advanced options for reusing a point and configuring follow-ups. The description editor is highlighted so its purpose is clear while drafting.

### Calendar Integration

No significant changes.

### Project Integration

No significant changes.

### Extension Demo

No significant changes.
