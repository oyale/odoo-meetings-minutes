# Community Meetings - Project Tasks

This optional addon links existing Odoo Project tasks to meeting agenda items, resolutions, and follow-up actions. It depends on `community_meetings` and Odoo's `project` addon; installing the core addon does not install either dependency automatically.

Task links require Project task read and write access and enforce company compatibility. The carryover wizard only carries tasks an editor explicitly selects. Task details are not included in approved minute snapshots, so later task changes cannot rewrite historical minutes. A task's “Meeting Agenda Links” action searches only meeting records the current user can access.

Creating a task is optional and available from a meeting follow-up action when the user has Project task creation access.
