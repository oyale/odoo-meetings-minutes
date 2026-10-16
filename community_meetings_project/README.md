# Community Meetings - Project Tasks

This optional addon links existing Odoo Project tasks to meeting agenda items, resolutions, and follow-up actions. It depends on `community_meetings` and Odoo's `project` addon; installing the core addon does not install either dependency automatically.

Task links require Project task read and write access and enforce company compatibility. The carryover wizard only carries tasks an editor explicitly selects. Task details are not included in approved minute snapshots, so later task changes cannot rewrite historical minutes. A task's “Meeting Agenda Links” action searches only meeting records the current user can access.

Creating a task is optional and available from a meeting follow-up action when the user has Project task creation access.

## Task policies

Installing this addon keeps assigned core follow-ups sufficient for TODOs by
default. Company settings and the series **Task Policy** tab configure three
independent choices:

- No default project, one company project, or one project per series.
- Core follow-up or a linked Project task required to resolve a TODO.
- Any accessible project or only the configured project for task selection.

A series project is created on first task creation, with standard Project
creation permissions; otherwise select an existing project. Project tasks must
be assigned, active, non-cancelled and company-compatible to satisfy a required
TODO. Existing tasks can be linked through **Create Project task** without
creating a duplicate. Project and core follow-up execution states remain
separate; the core follow-up is completed through its activity or status.

Closure captures the applicable requirement and project scope. Later policy
changes apply to subsequent resolutions. Removing the last valid task or moving
it outside that historical scope is rejected while the TODO remains resolved.
