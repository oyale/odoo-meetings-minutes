# Community Meetings

`community_meetings` is the Odoo 18 Community core for operational meetings,
agendas, resolutions and follow-up actions. It depends on `base`, `mail`, `web` and
`web_editor`; Project and Calendar integrations are separate addons.

## Install

Add this directory to Odoo's `addons_path`, refresh the Apps list, and install
**Community Meetings**. The project container already mounts `addons/` at
`/opt/meeting_addons`.

The core provides meeting workflows, agenda items, resolutions and actions,
recurring series, restricted editorial notes and dissent, agenda proposals,
carryover, approval, immutable revisions and snapshot-rendered PDF reports.
Optional integrations live in separate addons, including
`community_meetings_project` and the synthetic extension contract demo.

## Access

The addon defines proposer, reader, editor, approver and manager groups. Internal
users receive only the proposal capability by default. A meeting is visible to
its organizer, secretary, explicitly assigned readers/editors, or a manager in
an allowed company. Attendee contacts do not grant access. Editorial notes and
dissent are separate restricted records and are not exposed by the reader ACL.

## Development

Use the existing `meeting_minutes` development environment at
`http://meeting-minutes.local:8069`. Keep development data synthetic. Do not
create another database or bind a second HTTP port for this project.

Core tests are under `tests/`; optional addon tests are beside their addons.
`docs/VALIDATION.md` records the installed state and checks actually run. Use
the existing database and service for development; do not create another
database or bind another HTTP port.

## License

Original addon code is licensed AGPL-3.0-or-later.

## Prepare and run a meeting

**New** opens a guided flow: series, date and duration, attendees, continuing
points and new agenda points. Series defaults are copied, so later series edits
do not alter existing meetings. Use **Add Point** for a title and rich body;
priority is normal by default, and deadline/minutes are under **More options**.

A point keeps its identity across meetings. Each participation preserves its
own discussion and outcome. **Postpone** marks it for the next meeting;
**Review at next meeting** also schedules follow-up of an already resolved
point. Review proposals appear above the meeting form and live agenda. Series
can include continuing points automatically or require editorial review.

Live cards show outcomes read-only and offer explicit actions. Decisions are
approved/rejected through agreements. TODO points require an assigned follow-up
before resolution. Completing that work is separate from resolving the agenda
point. Follow-ups create Odoo activities for their owners; completing the
activity updates the durable follow-up rather than deleting the evidence.
Task owners need access to the originating meeting.

**Point options** offers point details and reopening with a reason. Approved
minutes keep their snapshot and original PDF when a shared point changes.
Attachments in point bodies are reserved for a later delivery; rich text and
links are supported now.
