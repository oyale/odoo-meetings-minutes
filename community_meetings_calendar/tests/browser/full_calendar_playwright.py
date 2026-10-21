"""Calendar extension browser checks on top of the core meeting workflow suite."""

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import expect

CORE_BROWSER = Path(__file__).resolve().parents[3] / "community_meetings" / "tests" / "browser"
sys.path.insert(0, str(CORE_BROWSER))
from full_meeting_playwright import BASE_URL, FullMeetingBrowserChecks  # noqa: E402


class CalendarMeetingBrowserChecks(FullMeetingBrowserChecks):
    def calendar_event_id(self):
        ids = self.record("community.meeting", self.meeting_id, ["calendar_event_ids"])[
            "calendar_event_ids"
        ]
        self.assertEqual(len(ids), 1)
        return ids[0]

    def open_calendar_event(self, event_id=None):
        event_id = event_id or self.calendar_event_id()
        self.page.goto(
            "%s/web#model=calendar.event&id=%s&view_type=form" % (BASE_URL, event_id)
        )
        expect(self.page.locator(".o_form_view")).to_be_visible(timeout=30000)
        return event_id

    def test_calendar_event_is_read_only_and_links_back_to_meeting(self):
        event_id = self.calendar_event_id()
        self.open_calendar_event(event_id)
        expect(
            self.page.get_by_text(
                self.ui_text(
                    "community_meetings_calendar",
                    "This event is managed by its community meeting. Open the meeting to view or edit meeting details.",
                )
            )
        ).to_be_visible()
        self.assertFalse(self.record("calendar.event", event_id, ["user_can_edit"])["user_can_edit"])
        subject = self.page.locator('.o_form_view .o_field_widget[name="name"]')
        expect(subject).to_contain_text(
            self.record("community.meeting", self.meeting_id, ["name"])["name"]
        )
        self.assertEqual(subject.locator("input, textarea, [contenteditable=true]").count(), 0)
        self.assertFalse(self.page.locator('div[name="send_buttons"]').is_visible())

        self.page.locator('button[name="action_open_community_meeting"]').click()
        meeting_name = self.record("community.meeting", self.meeting_id, ["name"])["name"]
        meeting_dialog = self.page.locator(".o_dialog .o_form_view")
        for _ in range(40):
            if "community.meeting" in self.page.url:
                break
            if meeting_dialog.count() and meeting_name in meeting_dialog.inner_text():
                break
            self.page.wait_for_timeout(250)
        opened_record = "community.meeting" in self.page.url or (
            meeting_dialog.count() and meeting_name in meeting_dialog.inner_text()
        )
        self.assertTrue(opened_record, "Calendar document link did not open its meeting")

        self.page.locator('button[name="action_open_calendar_event"]').click()
        event_name = self.record("calendar.event", event_id, ["name"])["name"]
        event_form = self.page.locator(".o_form_view")
        for _ in range(40):
            if "calendar.event" in self.page.url:
                break
            if event_form.count() and event_name in event_form.inner_text():
                break
            self.page.wait_for_timeout(250)
        opened_event = "calendar.event" in self.page.url or (
            event_form.count() and event_name in event_form.inner_text()
        )
        self.assertTrue(opened_event, "Meeting link did not open its Calendar event")

    def test_reschedule_and_attendee_change_are_mirrored_in_calendar(self):
        reviewer_login = os.environ["ODOO_REVIEWER_LOGIN"]
        reviewer_id = self.rpc("res.users", "search", [[("login", "=", reviewer_login)]])[0]
        reviewer_partner_id = self.record("res.users", reviewer_id, ["partner_id"])[
            "partner_id"
        ][0]
        new_start = (datetime.utcnow() + timedelta(days=4)).replace(microsecond=0)
        self.rpc("community.meeting", "write", [[self.meeting_id], {
            "name": "Calendar rescheduled in browser",
            "start_datetime": new_start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_datetime": (new_start + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "location": "Calendar browser room",
            "attendee_partner_ids": [(4, reviewer_partner_id)],
        }])
        event_id = self.calendar_event_id()
        event = self.record(
            "calendar.event", event_id,
            ["name", "start", "stop", "location", "partner_ids", "user_can_edit"],
        )
        self.assertEqual(event["name"], "Calendar rescheduled in browser")
        self.assertEqual(event["location"], "Calendar browser room")
        self.assertEqual(event["start"], new_start.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertIn(reviewer_partner_id, event["partner_ids"])
        self.assertFalse(event["user_can_edit"])

        self.open_calendar_event(event_id)
        expect(self.page.locator(".o_form_view")).to_contain_text(
            "Calendar rescheduled in browser"
        )
        expect(self.page.locator(".o_form_view")).to_contain_text("Calendar browser room")
        expect(self.page.locator(".o_form_view")).to_contain_text(
            self.record("res.partner", reviewer_partner_id, ["name"])["name"]
        )

    def test_cancel_from_meeting_form_removes_calendar_event(self):
        event_id = self.calendar_event_id()
        self.open_form()
        self.page.locator('button[name="action_cancel"]').click()
        expect(self.page.locator(".o_form_view")).to_be_visible()
        state = self.record("community.meeting", self.meeting_id, ["state"])["state"]
        self.assertEqual(state, "cancelled")
        self.assertFalse(self.rpc("calendar.event", "search", [[("id", "=", event_id)]]))


# unittest discovers every TestCase visible in the module; retain only the
# derived class so the inherited core suite runs once, with Calendar enabled.
del FullMeetingBrowserChecks


if __name__ == "__main__":
    unittest.main(verbosity=2)
