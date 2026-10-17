# FAQ and troubleshooting

Common situations, in the voice of the person hitting them.

## Access

**"I opened Odoo and I see no Meetings menu."**
The root menu requires the internal user group; if you still don't see your
expected meetings, you are not organizer/secretary/reader of them. Ask an editor
to add you on the meeting's **Access** tab, or a manager to grant you the Reader
role.

**"I am an attendee — why can't I open the meeting?"**
Attendees are contacts and do not grant access. Access is per user: organizer,
secretary, assigned readers/editors, or managers.

**"I can't propose points."**
Either the organization restricted proposals to specific groups
([catalogs](admin/catalogs.md#authorized-proposer-groups)) or the series you
picked is inactive/from another company.

## Preparing

**"Add Point is missing on my meeting."**
The series' *adding points* policy says this meeting no longer accepts points
(see [policies](admin/series.md#policies)). The server enforces it even if you
find another route.

**"The agenda exceeds the meeting duration."**
The sum of point estimates is larger than the planned duration. Extend the
duration, raise estimates' accuracy, or drop points. The warning is
informational.

**"Changing the series is blocked."**
Series can change only in draft/scheduled and before live execution starts, and
points shared with other meetings limit the target series.

## Live meeting

**"My notes disappeared."** They did not: with time tracking **on**, notes are
read-only when their point timer is paused and while the meeting is paused.
Resume the point (or the meeting) to continue typing. Everything auto-saves —
check the topbar status.

**"I pressed Finish Meeting by mistake."** An approver/editor can reopen
content while minutes are not approved: use *Undo result* per point or reopen
from the form; if already Held, the flow continues in minutes draft.

**"I can't complete a decision point."** Record the **agreement** first
(approved/rejected). Decisions need an agreement; the Done button stays disabled
until then.

**"I can't complete a TODO point."** Add an assigned follow-up — evidence of
responsibility is required before resolution.

**"Adding a point says it's not allowed anymore."** The series/company
*adding points* policy expired for this meeting's state. Options: propose it for
the next meeting or record it as a follow-up.

## Minutes

**"Approve Minutes is missing."** Only **approvers** see it, and only in
*Minutes draft* state.

**"The PDF is missing."** Approved revisions render their PDF on approval; if
the server lacks the PDF assets the snapshot is kept and the PDF can be
regenerated later from the revision.

**"Someone changed a point after approval."** Approved minutes are immutable
snapshots; changes after approval require **Start Amendment** (approver) and
produce a new revision.

## Follow-ups and tasks

**"The TODO point is closed but the work isn't done."** Expected: resolution
requires *evidence of responsibility* (assigned follow-up with activity/task),
not finished work.

**"Why can't I delete that task?"** A closed TODO still depends on it as
evidence. Cancel the task instead of deleting, or reopen the point.

**"The task owner can't see the meeting."** Add them as reader on the meeting's
**Access** tab — task links don't grant meeting access.

## Calendar

**"The calendar event is read-only."** It is managed by its meeting; edit the
meeting instead ([Calendar](integrations/calendar.md)).

## Still stuck?

Ask a **manager**; if the problem looks like a bug, describe the exact screen,
state of the meeting and the message shown — managers can inspect chatter
histories on meetings, points and follow-ups.
