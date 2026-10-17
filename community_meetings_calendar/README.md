# Community Meetings - Calendar Integration

[![Odoo 18.0](https://img.shields.io/badge/Odoo-18.0-714B67.svg)](https://github.com/oyale/meeting-minutes/tree/18.0)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue.svg)](../../LICENSE)
[![Maturity: Beta](https://img.shields.io/badge/maturity-Beta-yellow.svg)](https://odoo-community.org/page/development-status)

This optional addon mirrors scheduled Community Meetings as private Odoo
Calendar events. It synchronizes event details and internal-user attendees,
and uses Odoo's native invitation and cancellation notifications. Meeting
minutes and private notes are not copied to Calendar.

## Usage

Install this addon with Odoo Calendar. Scheduled meetings with eligible
internal-user attendees create or update a linked Calendar event. Event links
open the meeting subject to the user's normal access rights. Calendar attendee
responses do not change meeting attendance.

See the [Calendar integration guide](https://oyale.github.io/meeting-minutes/html-en/integrations/calendar.html).
