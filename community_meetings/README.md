# Community Meetings

`community_meetings` is the Odoo 18 Community core for operational meetings,
agendas, resolutions and follow-up actions. It depends only on `base` and
`mail`; Project and Calendar integrations are separate addons.

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
