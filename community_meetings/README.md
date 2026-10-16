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

### Test coverage

`tests/coverage.sh` measures line coverage by running the module's Odoo test
suite under `coverage` (install once with
`/home/odoo/pyenv/versions/odoo/bin/pip install coverage`). It runs inside the
Odoo container, rewrites the `.coverage` data to `/tmp`, and prints a per-file
report excluding tests and migrations:

```sh
bash tests/coverage.sh
```

The revision/PDF tests are excluded by default (they need live HTTP assets), so
`revision.py`/`report_revision.py` show low coverage in the default run; pass a
different `--test-tags` value as the first argument to focus elsewhere.

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

### Changing the meeting series

The meeting form allows assigning, changing or removing its series while it is
in draft or scheduled and live execution has not started. A series change is
blocked after execution starts or when an approved revision exists. The target
series must be active and match the meeting company and kind. Points used only
by this meeting follow the new series; points shared with another meeting cannot
be moved to a different series.

### Core coverage runner

Inside the development container, run `bash /opt/meeting_addons/community_meetings/tests/coverage.sh`
for core line coverage. The runner records whether the Odoo service was active,
stops it before accessing the existing database, and restores that initial state
on success, test/report failure or a handled signal. It fails if Odoo cannot be
stopped or restarted. `ODOO_TEST_TIMEOUT` controls the test-process limit (120s
by default); the default test selection excludes PDF revision tests that need
HTTP assets. Run `bash tests/test_coverage_runner.sh` from this addon checkout
to check the service recovery paths without touching the real service. SIGKILL
and host loss cannot run shell cleanup.
