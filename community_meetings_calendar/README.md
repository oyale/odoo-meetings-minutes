# Community Meetings - Calendar Integration

This optional addon creates one private Odoo Calendar event when a community
meeting is scheduled. Install it alongside `community_meetings` and Odoo's
`calendar` addon; the core meeting addon remains independent of Calendar.

The meeting remains the source of truth for event title, time, location,
organizer, secretary and internal-user attendees. Changes update the same event
while the meeting remains scheduled. Holding the meeting freezes the event
mirror, preserving the invitation history. Cancelling the meeting removes the
event and queues iCalendar cancellation notices; removing an attendee queues a
cancellation for that attendee. Odoo's native invitation and date-change
notifications are used for additions and rescheduling.

Calendar invitees see the event metadata in their calendar. The event does not
copy the meeting description, agenda, minutes or private notes. Its document
link uses normal meeting access rules: an invitee must separately have read
access to open the meeting. Calendar attendee responses remain in Calendar and
do not change meeting attendance. Event alarms are not enabled by this
integration.

Only active internal users in the meeting company can be invitees. A missing
email address does not prevent the user from appearing as a Calendar
participant, but Odoo cannot send that participant an invitation email. The
standard `calendar.block_mail` setting and outbound-mail configuration still
control delivery.

## Browser checks

The Calendar browser runner reuses the full core Playwright suite and adds
Calendar-specific checks. Run it against a dedicated test database with the
addon installed; it sets `calendar.block_mail` in that database before creating
fixtures so no invitation or cancellation mail leaves the test run:

```sh
python3 addons/community_meetings_calendar/tests/browser/run_development_suite.py \
  --development --database community_meetings_calendar_test
```
