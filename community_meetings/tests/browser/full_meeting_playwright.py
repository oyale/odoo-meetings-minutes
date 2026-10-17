#!/usr/bin/env python3
"""Full browser regression suite. See README.md for scope, credentials and cleanup."""

import json
import os
import re
from pathlib import Path
import sys
import time
import unittest
import uuid

from playwright.sync_api import expect
from live_meeting_playwright import BASE_URL, LiveMeetingBrowserChecks

# Each entry is an observable user action, not a line/branch coverage claim.
ACTIONS = {
    "test_scroll_and_meeting_wide_records_visibility": [
        "scroll live",
        "hide general records",
    ],
    "test_information_point_can_be_marked_done": ["finish information point"],
    "test_discussion_point_can_be_resolved": ["resolve discussion"],
    "test_postponing_a_point_enables_next_meeting_review": [
        "postpone point and enable next meeting review",
    ],
    "test_live_result_can_be_undone_and_manual_actual_time_is_hidden": [
        "hide manual actual point time",
        "undo a point result",
    ],
    "test_point_timer_navigation_collapses_and_resume_accumulates": [
        "start and pause point timing",
        "collapse inactive points when navigating",
        "accumulate time after resuming a point",
    ],
    "test_point_live_editing_requires_begin_and_pause_is_read_only": [
        "hide live editors until Begin point",
        "lock live editors after Pause point",
    ],
    "test_decision_can_be_undone_during_running_meeting": [
        "undo decision during live meeting",
    ],
    "test_todo_requires_a_followup_task_before_resolution": [
        "guard TODO closure",
        "assign TODO task",
        "resolve TODO",
    ],
    "test_decision_requires_and_uses_agreement_without_direct_edit": [
        "approve through agreement",
        "withdraw agreement",
        "reject through agreement",
    ],
    "test_postponing_an_approved_decision_withdraws_its_agreement": [
        "postpone approved decision"
    ],
    "test_dissent_author_reason_and_statement_are_usable": [
        "add dissent author",
        "choose dissent reason",
        "save dissent statement",
    ],
    "test_defer_works_for_each_point_type": ["postpone each point type"],
    "test_private_note_form_stays_collapsed_until_requested": [
        "expand private note form"
    ],
    "test_navigation_and_filter": [
        "collapse all",
        "expand one",
        "next point",
        "previous point",
        "filter pending",
    ],
    "test_notes_autosave_and_reload": [
        "edit discussion notes",
        "edit meeting notes",
        "persist after reload",
    ],
    "test_private_note_create_and_edit": ["save private note", "edit private note"],
    "test_task_editing": [
        "add follow-up task",
        "rename task",
        "assign task owner",
        "change task deadline",
        "start task",
        "complete task",
        "reopen task",
        "cancel task",
    ],
    "test_dissent_editing": [
        "edit dissent author",
        "edit dissent reason",
        "exclude dissent from minutes",
        "edit dissent body",
    ],
    "test_deferral_cancel": ["cancel postponement"],
    "test_attendees": [
        "search attendee",
        "add attendee",
        "remove attendee",
        "cancel attendee edits",
    ],
    "test_session_lifecycle": [
        "start meeting",
        "finish meeting",
        "prepare minutes",
        "return to meetings",
    ],
    "test_already_held": ["record already held meeting"],
    "test_point_type": ["change point type"],
    "test_mobile_layout": ["use live on mobile width"],
    "test_form_edit_and_schedule": ["edit meeting form", "schedule meeting"],
    "test_create_meeting_and_point": [
        "create meeting",
        "create agenda point",
        "review meeting summary",
    ],
    "test_series_creation": ["create series", "new meeting from series"],
    "test_carryover_request": [
        "request carryover",
        "accept carryover",
        "dismiss carryover",
    ],
    # Common actions still covered only outside this browser suite. Count as gaps.
    "test_guided_meeting_and_rich_point": [
        "guided meeting steps",
        "series attendee defaults",
        "series duration defaults",
        "wizard back preserves edits",
        "rich point body",
        "point priority",
        "optional deadline",
        "optional time estimate",
        "priority in live",
        "hide empty carryover list",
        "suggest series meeting name",
        "allow meeting name override",
    ],
    "test_followup_points_are_offered_in_new_meeting_wizard": [
        "carry completed follow-up point into next meeting",
    ],
    "test_selected_carryover_is_materialized_in_new_meeting": [
        "select carried point",
        "show carried point in created meeting",
    ],
    "test_add_point_from_live_and_cancel": [
        "add rich point from live",
        "cancel point wizard without side effects",
    ],
    "test_meetings_root_opens_list_and_preserves_submenus": [
        "open meeting list from root menu",
        "open new meeting wizard from its submenu",
    ],
    "test_followup_activity_uses_configured_activity_type": [
        "create follow-up with default activity type",
        "choose Odoo activity type",
        "create follow-up with native Odoo To-Do type",
        "keep activity completion out of live task editor",
    ],
    "test_automatic_continuation_reuses_identity_and_links": [
        "postponement schedules review",
        "automatic continuation keeps identity",
        "read carried HTML links",
    ],
    "test_review_continuations_from_live": [
        "review continuing points in live",
        "accept continuing point in live",
        "dismiss continuing point in live",
    ],
    "test_save_failure_keeps_text_and_retry_persists": ["recover after save failure"],
    "test_mobile_point_wizard_and_keyboard_cancel": [
        "point wizard on mobile",
        "cancel wizard by keyboard",
    ],
    "test_wizard_excludes_automatic_point_and_preserves_choice": [
        "exclude automatic continuation in wizard",
        "preserve continuation choice when going back",
    ],
    "test_approve_and_download_minutes": [
        "approve minutes",
        "download approved minutes",
    ],
}
ARTIFACTS = (
    Path(os.environ.get("PLAYWRIGHT_ARTIFACTS", "/tmp/meeting-playwright"))
    / uuid.uuid4().hex[:10]
)


class FullMeetingBrowserChecks(LiveMeetingBrowserChecks):
    retained = []

    def setUp(self):
        self.errors_before = len(self.console_errors)
        super().setUp()
        self.page.set_default_timeout(10000)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self.addCleanup(self.save_trace)

    def save_trace(self):
        ARTIFACTS.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.context.tracing.stop(path=str(ARTIFACTS / (self._testMethodName + ".zip")))

    def tearDown(self):
        self.assertFalse(
            self.console_errors[self.errors_before :],
            "Browser errors: " + repr(self.console_errors[self.errors_before :]),
        )

    def consume_injected_write_error(self, marker):
        errors = self.console_errors[self.errors_before :]
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("Live meeting write failed", errors[0])
        self.assertIn(marker, errors[0])
        del self.console_errors[self.errors_before :]

    def cleanup_meeting(self):
        if not self.meeting_id or not self.rpc(
            "community.meeting", "search_count", [[("id", "=", self.meeting_id)]]
        ):
            return
        if getattr(self, "retain_carryover", False):
            self.retained.append(
                {
                    "model": "community.meeting",
                    "id": self.meeting_id,
                    "reason": "carryover history",
                }
            )
            return
        state = self.record("community.meeting", self.meeting_id, ["state"])["state"]
        if state not in ("draft", "scheduled", "cancelled"):
            # Published/held records cannot be deleted through ordinary editorial APIs.
            # The development runner removes only its own disposable-user fixtures.
            self.retained.append(
                {"model": "community.meeting", "id": self.meeting_id, "state": state}
            )
            return
        if state == "cancelled":
            self.rpc("community.meeting", "unlink", [[self.meeting_id]])
        else:
            super().cleanup_meeting()

    def wait_field(self, model, record_id, field, expected):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = self.record(model, record_id, [field])[field]
            if value == expected or (
                isinstance(value, str)
                and isinstance(expected, str)
                and expected in value
            ):
                return value
            self.page.wait_for_timeout(100)
        self.fail("%s.%s: expected %r, got %r" % (model, field, expected, value))

    def related(self, model, kind):
        rows = self.rpc(
            model,
            "search_read",
            [[("agenda_item_id", "=", self.item_ids[kind])]],
            {"fields": ["id"]},
        )
        self.assertEqual(len(rows), 1)
        return rows[0]["id"]

    def wait_action_record(self, name):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            rows = self.rpc(
                "community.meeting.action",
                "search_read",
                [[("meeting_id", "=", self.meeting_id), ("name", "=", name)]],
                {"fields": ["name", "agenda_item_id", "followup_kind", "followup_activity_id"], "limit": 1},
            )
            if rows:
                return rows[0]
            self.page.wait_for_timeout(100)
        self.fail("Follow-up %r was not saved" % name)

    def edit_rich(self, locator, text):
        expect(locator).to_be_visible()
        locator.click()
        locator.press("ControlOrMeta+a")
        locator.fill(text)
        self.page.locator(".o_live_header h1").click()

    def open_form(self):
        self.page.goto(
            "%s/web#model=community.meeting&id=%s&view_type=form"
            % (BASE_URL, self.meeting_id)
        )
        self.page.locator(".o_form_view").wait_for()

    def test_review_next_meeting_failure_restores_checkbox(self):
        target = "**/web/dataset/call_kw/community.meeting.agenda.item/write"

        def reject(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "error": {
                            "code": 200,
                            "message": "Injected failure",
                            "data": {
                                "name": "odoo.exceptions.ValidationError",
                                "message": "Injected failure",
                                "arguments": ["Injected failure"],
                                "debug": "",
                            },
                        },
                    }
                ),
            )

        self.page.route(target, reject, times=1)
        checkbox = self.card("information").get_by_role(
            "checkbox", name="Review at next meeting"
        )
        checkbox.click()
        expect(self.page.get_by_role("alert").filter(has_text="Some changes could not be saved.")).to_be_visible()
        expect(checkbox).to_be_enabled()
        expect(checkbox).not_to_be_checked()
        self.assertFalse(
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["information"],
                ["review_next_meeting"],
            )["review_next_meeting"]
        )
        checkbox.check()
        expect(checkbox).to_be_enabled()
        expect(checkbox).to_be_checked()
        self.assertTrue(
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["information"],
                ["review_next_meeting"],
            )["review_next_meeting"]
        )
        self.consume_injected_write_error("Injected failure")

    def test_review_next_meeting_toggle_persists(self):
        checkbox = self.card("information").get_by_role(
            "checkbox", name="Review at next meeting"
        )
        checkbox.check()
        expect(checkbox).to_be_checked()
        expect(checkbox).to_be_enabled()
        expect(checkbox).to_be_checked()
        self.assertTrue(
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["information"],
                ["review_next_meeting"],
            )["review_next_meeting"]
        )
        self.open_live(self.meeting_id)
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        expect(checkbox).to_be_checked()
        checkbox.uncheck()
        expect(checkbox).to_be_enabled()
        expect(checkbox).not_to_be_checked()
        self.assertFalse(
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["information"],
                ["review_next_meeting"],
            )["review_next_meeting"]
        )

    def test_empty_html_live_in_debug_mode(self):
        self.rpc(
            "community.meeting", "write", [[self.meeting_id], {"minutes_notes": False}]
        )
        self.rpc(
            "community.meeting.agenda.item",
            "write",
            [list(self.item_ids.values()), {"discussion_notes": False}],
        )
        self.page.goto(
            "%s/web?debug=1#model=community.meeting&id=%s&view_type=form"
            % (BASE_URL, self.meeting_id)
        )
        self.page.locator('button[name="action_open_live_meeting"]').click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        expect(
            self.card("information").locator('[contenteditable="true"]').first
        ).to_be_visible()

    def test_navigation_and_filter(self):
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        expect(self.card("information", begin=False).locator(".o_live_expand")).to_have_attribute(
            "aria-expanded", "false"
        )
        self.card("information", begin=False).locator(".o_live_expand").click()
        expect(self.card("information", begin=False).locator(".o_live_expand")).to_have_attribute(
            "aria-expanded", "true"
        )
        self.page.get_by_role("button", name="Next agenda point").click()
        expect(self.card("discussion", begin=False)).to_have_class(re.compile("o_live_current"))
        self.page.get_by_role("button", name="Previous agenda point").click()
        expect(self.card("information", begin=False)).to_have_class(re.compile("o_live_current"))
        self.page.get_by_role("button", name="Start Meeting").click()
        expect(self.page.get_by_role("button", name="Finish Meeting")).to_be_visible()
        information = self.card("information", begin=False)
        information.get_by_role("button", name="Begin point").click()
        information.get_by_role("button", name="Done").click()
        expect(self.outcome("information")).to_have_text("Done")
        self.page.get_by_role("button", name="Pending only").click()
        expect(
            self.page.locator(".o_live_agenda_card").filter(has_text="Browser Information case")
        ).to_have_count(0)
        expect(self.page.locator(".o_live_agenda_card")).to_have_count(3)
        self.page.get_by_role("button", name="Pending only").click()
        expect(self.card("information")).to_be_visible()

    def test_notes_autosave_and_reload(self):
        self.edit_rich(
            self.card("discussion").locator(
                '[contenteditable="true"][aria-label="Discussion notes"]'
            ),
            "Discussion persisted in browser",
        )
        self.wait_field(
            "community.meeting.agenda.item",
            self.item_ids["discussion"],
            "discussion_notes",
            "Discussion persisted",
        )
        self.edit_rich(
            self.page.locator('[contenteditable="true"][aria-label="Meeting minutes"]'),
            "Session notes persisted",
        )
        self.wait_field(
            "community.meeting",
            self.meeting_id,
            "minutes_notes",
            "Session notes persisted",
        )
        self.open_form()
        self.page.get_by_role("button", name="Open Live Meeting").click()
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        expect(
            self.card("discussion").locator(
                '[contenteditable="true"][aria-label="Discussion notes"]'
            )
        ).to_contain_text("Discussion persisted")
        expect(
            self.page.locator('[contenteditable="true"][aria-label="Meeting minutes"]')
        ).to_contain_text("Session notes persisted")

    def test_private_note_create_and_edit(self):
        details = (
            self.card("discussion")
            .locator("details")
            .filter(has_text="Private editorial notes")
        )
        details.locator("summary").click()
        details.get_by_role("button", name="Add private note", exact=True).click()
        details.get_by_label("Private editorial note", exact=True).fill("Private draft")
        details.get_by_role("button", name="Add private note", exact=True).click()
        expect(details.locator(".o_live_rich_readonly")).to_contain_text(
            "Private draft"
        )
        note = self.related("community.meeting.editor.note", "discussion")
        details.get_by_role("button", name="Edit private note", exact=True).click()
        self.edit_rich(
            details.locator('[contenteditable="true"]'), "Revised private draft"
        )
        self.wait_field(
            "community.meeting.editor.note", note, "content", "Revised private draft"
        )

    def test_task_editing(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label("Task name", exact=True).fill("Browser follow-up")
        owners = (
            form.get_by_label("Task owner")
            .locator("option")
            .evaluate_all("(els) => els.map(e => e.value).filter(Boolean)")
        )
        self.assertTrue(owners)
        editor_id = self.rpc(
            "res.users", "search", [[("login", "=", os.environ["ODOO_LOGIN"])]]
        )[0]
        form.get_by_label("Task owner").select_option(str(editor_id))
        form.get_by_label("Deadline", exact=True).fill("2027-02-01")
        form.get_by_role("button", name="Add follow-up").click()
        row = card.locator('li:has(select[aria-label="Task status"])')
        expect(row).to_be_visible()
        task = self.related("community.meeting.action", "discussion")
        self.assertEqual(
            self.record("community.meeting.action", task, ["responsible_user_id"])[
                "responsible_user_id"
            ][0],
            editor_id,
        )
        row.get_by_label("Task name").fill("Renamed follow-up")
        row.get_by_label("Task name").press("Tab")
        self.wait_field("community.meeting.action", task, "name", "Renamed follow-up")
        row.get_by_label("Task deadline").fill("2027-02-02")
        row.get_by_label("Task deadline").press("Tab")
        self.wait_field("community.meeting.action", task, "deadline", "2027-02-02")
        for state in ("in_progress", "done", "open", "cancelled"):
            row.get_by_label("Task status").select_option(state)
            self.wait_field("community.meeting.action", task, "state", state)

    def test_followup_can_be_deleted_while_point_is_open(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label("Task name").fill("Remove this follow-up")
        form.get_by_role("button", name="Add follow-up", exact=True).click()
        row = card.locator('li:has(select[aria-label="Task status"])').last
        expect(row.get_by_role("button", name="Delete follow-up")).to_be_visible()
        action_id = self.related("community.meeting.action", "discussion")
        row.get_by_role("button", name="Delete follow-up").click()
        expect(row).not_to_be_visible()
        self.assertFalse(self.rpc("community.meeting.action", "search", [[("id", "=", action_id)]]))

    def test_dissent_editing(self):
        self.test_dissent_author_reason_and_statement_are_usable()
        row = self.card("discussion").locator(".o_live_record_list li").first
        row.get_by_label("Author", exact=True).fill("Grace Hopper")
        row.get_by_label("Author", exact=True).press("Tab")
        record_id = self.related("community.meeting.dissent", "discussion")
        self.wait_field(
            "community.meeting.dissent",
            record_id,
            "author_display_name",
            "Grace Hopper",
        )
        row.get_by_label("Statement type").select_option(label="Dissent")
        dissent_reason = self.rpc(
            "community.meeting.dissent.reason", "search", [[("name", "=", "Dissent")]], {"limit": 1}
        )[0]
        deadline = time.time() + 10
        saved = self.record("community.meeting.dissent", record_id, ["reason_id"])["reason_id"]
        while time.time() < deadline and (not saved or saved[0] != dissent_reason):
            self.page.wait_for_timeout(100)
            saved = self.record("community.meeting.dissent", record_id, ["reason_id"])["reason_id"]
        self.assertEqual(saved[1], "Dissent")
        row.get_by_label("Include in minutes").click()
        expect(row.get_by_label("Include in minutes")).not_to_be_checked()
        self.wait_field(
            "community.meeting.dissent", record_id, "include_in_minutes", False
        )
        row.get_by_role("button", name="Edit statement").click()
        self.edit_rich(
            row.locator('[contenteditable="true"]'), "Alternative proposal in detail"
        )
        self.wait_field(
            "community.meeting.dissent", record_id, "body", "Alternative proposal"
        )

    def test_deferral_cancel(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Postpone agenda point").click()
        card.get_by_label("Reason for postponing").fill("Unconfirmed reason")
        card.locator(".o_live_deferral").get_by_role(
            "button", name="Cancel", exact=True
        ).click()
        expect(card.get_by_label("Reason for postponing")).to_have_count(0)
        self.assertEqual(
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["discussion"],
                ["disposition"],
            )["disposition"],
            "open",
        )

    def test_attendees(self):
        # Use the authenticated user's existing partner; do not create contacts.
        user = self.rpc(
            "res.users",
            "search_read",
            [[("login", "=", os.environ["ODOO_LOGIN"])]],
            {"fields": ["partner_id"], "limit": 1},
        )[0]
        partner_id, partner_name = user["partner_id"]
        self.page.get_by_role("button", name="Edit attendees").click()
        self.page.get_by_label("Find contacts").fill(partner_name)
        option = self.page.locator(".o_live_attendee_options").get_by_label(
            partner_name, exact=True
        )
        option.check()
        self.page.get_by_role("button", name="Save attendees").click()
        self.wait_field(
            "community.meeting", self.meeting_id, "attendee_partner_ids", [partner_id]
        )
        self.page.get_by_role("button", name="Edit attendees").click()
        self.page.locator(".o_live_selected_attendees").get_by_label(
            partner_name, exact=True
        ).uncheck()
        self.page.locator(".o_live_attendee_editor").get_by_role(
            "button", name="Cancel", exact=True
        ).click()
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["attendee_partner_ids"])[
                "attendee_partner_ids"
            ],
            [partner_id],
        )
        self.page.get_by_role("button", name="Edit attendees").click()
        self.page.locator(".o_live_selected_attendees").get_by_label(
            partner_name, exact=True
        ).uncheck()
        self.page.get_by_role("button", name="Save attendees").click()
        self.wait_field(
            "community.meeting", self.meeting_id, "attendee_partner_ids", []
        )

    def test_session_lifecycle(self):
        self.page.get_by_role("button", name="Start Meeting", exact=True).click()
        expect(
            self.page.get_by_role("button", name="Finish Meeting", exact=True)
        ).to_be_visible()
        self.assertTrue(
            self.record(
                "community.meeting", self.meeting_id, ["actual_start_datetime"]
            )["actual_start_datetime"]
        )
        self.page.get_by_role("button", name="Finish Meeting", exact=True).click()
        expect(
            self.page.get_by_role("button", name="Prepare Minutes", exact=True)
        ).to_be_visible()
        self.page.get_by_role("button", name="Prepare Minutes", exact=True).click()
        self.wait_field("community.meeting", self.meeting_id, "state", "minutes_draft")
        self.page.get_by_role("button", name="Back to Meetings").click()
        expect(self.page.locator(".o_list_view")).to_be_visible()

    def test_already_held(self):
        self.page.get_by_role(
            "button", name="Record as Already Held", exact=True
        ).click()
        expect(
            self.page.get_by_role("button", name="Prepare Minutes", exact=True)
        ).to_be_visible()
        record = self.record(
            "community.meeting", self.meeting_id, ["state", "actual_end_datetime"]
        )
        self.assertEqual(record["state"], "held")
        self.assertTrue(record["actual_end_datetime"])

    def test_point_type(self):
        card = self.card("information")
        card.get_by_role("button", name="Change point type").click()
        type_id = self.record(
            "community.meeting.agenda.item",
            self.item_ids["discussion"],
            ["agenda_type_id"],
        )["agenda_type_id"][0]
        card.get_by_label("Point type", exact=True).select_option(str(type_id))
        expect(card.get_by_role("button", name="Done")).to_be_visible()
        self.wait_field(
            "community.meeting.agenda.item",
            self.item_ids["information"],
            "kind",
            "discussion",
        )

    def test_mobile_layout(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        try:
            main = self.page.locator("main.o_community_live_meeting")
            overflow = main.evaluate("el => ({width: el.clientWidth, scrollWidth: el.scrollWidth, offenders: [...el.querySelectorAll('*')].filter(x => x.scrollWidth > x.clientWidth + 2).map(x => ({tag: x.tagName, className: x.className, text: (x.innerText || '').slice(0, 80), width: x.clientWidth, scrollWidth: x.scrollWidth})).slice(0, 12)})")
            self.assertLessEqual(overflow["scrollWidth"] - overflow["width"], 1, overflow)
            self.card("information").get_by_role("button", name="Done").click()
            expect(self.outcome("information")).to_have_text("Done")
        finally:
            self.page.set_viewport_size({"width": 1440, "height": 1000})

    def test_form_edit_and_schedule(self):
        # Separate draft fixture: the standard case is already scheduled.
        draft = self.rpc(
            "community.meeting",
            "create",
            [{"name": "Browser draft", "start_datetime": "2027-03-01 09:00:00"}],
        )
        self.addCleanup(self.delete_draft, draft)
        self.page.goto(
            "%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, draft)
        )
        self.page.locator('.o_field_widget[name="location"] input').fill("Browser room")
        self.page.get_by_role("button", name="Schedule", exact=True).click()
        expect(
            self.page.get_by_role("button", name="Open Live Meeting")
        ).to_be_visible()
        record = self.record("community.meeting", draft, ["location", "state"])
        self.assertEqual(
            (record["location"], record["state"]), ("Browser room", "scheduled")
        )

    def delete_draft(self, record_id):
        self.rpc("community.meeting", "action_cancel", [[record_id]])
        self.rpc("community.meeting", "unlink", [[record_id]])

    def test_create_meeting_and_point(self):
        name = "Browser created " + uuid.uuid4().hex[:8]
        self.page.goto(
            BASE_URL + "/odoo/action-community_meetings.action_community_meetings"
        )
        self.page.locator(".o_list_button_add").click()
        wizard = self.page.get_by_role("dialog").last
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('.o_field_widget[name="name"] input').fill(name)
        for _ in range(3):
            wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_add_point"]').click()
        point = self.page.get_by_role("dialog").last
        point.locator('.o_field_widget[name="name"] input').fill("Created agenda title")
        point.locator('button[name="action_save"]').click()
        wizard = self.page.get_by_role("dialog").last
        expect(wizard.locator('.o_field_widget[name="line_ids"]')).to_contain_text(
            "Created agenda title"
        )
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.locator('.o_field_widget[name="review_summary"]')
        ).to_contain_text("Created agenda title")
        wizard.locator('button[name="action_finish"]').click()
        expect(
            self.page.locator('.o_form_view .o_field_widget[name="name"] input').first
        ).to_have_value(name)
        rows = self.rpc("community.meeting", "search", [[("name", "=", name)]])
        self.assertEqual(len(rows), 1)
        self.addCleanup(self.delete_draft, rows[0])
        items = self.rpc(
            "community.meeting.agenda.item",
            "search_read",
            [[("meeting_id", "=", rows[0])]],
            {"fields": ["name"]},
        )
        self.assertEqual([i["name"] for i in items], ["Created agenda title"])

    def test_series_creation(self):
        name = "Browser series " + uuid.uuid4().hex[:8]
        self.page.goto(
            BASE_URL + "/odoo/action-community_meetings.action_community_meeting_series"
        )
        self.page.locator(".o_list_button_add").click()
        series_wizard = self.page.get_by_role("dialog").last
        series_wizard.locator('.o_field_widget[name="name"] input').fill(name)
        for _ in range(3):
            series_wizard.locator('button[name="action_next"]').click()
        series_wizard.locator('button[name="action_finish"]').click()
        expect(series_wizard).not_to_be_visible()
        rows = self.rpc("community.meeting.series", "search", [[("name", "=", name)]])
        self.assertEqual(len(rows), 1)
        self.addCleanup(self.rpc, "community.meeting.series", "unlink", [rows])
        self.page.locator('button[name="action_new_meeting"]').click()
        expect(
            self.page.locator('.o_field_widget[name="series_id"] input')
        ).to_have_value(name)
        # Leave the unsaved meeting without persisting it.

    def test_carryover_request(self):
        series = self.rpc(
            "community.meeting.series",
            "create",
            [
                {
                    "name": "Browser carryover " + uuid.uuid4().hex[:8],
                    "carryover_policy": "review",
                }
            ],
        )
        self.rpc(
            "community.meeting", "write", [[self.meeting_id], {"series_id": series}]
        )
        # Series cleanup must run after meeting cleanup.
        self.retain_carryover = True
        self.retained.append({"model": "community.meeting.series", "id": series})
        # Defer an unstarted point before the meeting runs: live edits are
        # server-guarded once a point or the meeting is under way.
        self.rpc(
            "community.meeting.carryover",
            "create",
            [
                {
                    "origin_model": "agenda_item",
                    "origin_record_id": self.item_ids["information"],
                    "reason": "Second review",
                }
            ],
        )
        self.open_form()
        self.page.get_by_role("button", name="Open Live Meeting").click()
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        card = self.card("discussion")
        card.get_by_role("button", name="Postpone agenda point").click()
        card.get_by_label("Reason for postponing").fill("Review next week")
        card.get_by_role("button", name="Move to another meeting series").click()
        dialog = self.page.get_by_role("dialog")
        dialog.get_by_role("button", name="Request Follow-up", exact=True).click()
        expect(dialog).not_to_be_visible()
        transfers = self.rpc(
            "community.meeting.carryover",
            "search_read",
            [[("origin_agenda_item_id", "=", self.item_ids["discussion"])]],
            {"fields": ["status"]},
        )
        self.assertEqual(len(transfers), 1)
        expect(self.outcome("discussion")).to_have_text("Postponed")
        destination = self.rpc(
            "community.meeting",
            "create",
            [
                {
                    "name": "Browser next meeting",
                    "series_id": series,
                    "start_datetime": "2030-01-01 10:00:00",
                }
            ],
        )
        self.retained.append(
            {
                "model": "community.meeting",
                "id": destination,
                "reason": "carryover history",
            }
        )
        self.page.goto(
            "%s/web#model=community.meeting&id=%s&view_type=form"
            % (BASE_URL, destination)
        )
        self.page.get_by_role("tab", name="Incoming Carryovers").click()
        incoming = self.page.locator('.o_field_widget[name="incoming_carryover_ids"]')
        row = incoming.locator("tr.o_data_row").filter(
            has_text="Browser Discussion case"
        )
        row.locator('button[name="action_accept"]').click()
        expect(row).to_contain_text("Accepted")
        other = incoming.locator("tr.o_data_row").filter(
            has_text="Browser Information case"
        )
        other.locator('button[name="action_dismiss"]').click()
        expect(other).to_contain_text("Dismissed")
        items = self.rpc(
            "community.meeting.agenda.item",
            "search_count",
            [[("meeting_id", "=", destination)]],
        )
        self.assertEqual(items, 1)

    def current_user(self):
        return self.rpc(
            "res.users", "search", [[("login", "=", os.environ["ODOO_LOGIN"])]]
        )[0]

    def open_live(self, meeting_id):
        self.page.goto(
            "%s/web#model=community.meeting&id=%s&view_type=form"
            % (BASE_URL, meeting_id)
        )
        self.page.locator('button[name="action_open_live_meeting"]').click()
        self.page.locator("main.o_community_live_meeting").wait_for()

    def test_guided_meeting_and_rich_point(self):
        user = self.rpc("res.users", "read", [[self.current_user()], ["partner_id"]])[0]
        series = self.rpc(
            "community.meeting.series",
            "create",
            [
                {
                    "name": "Guided series " + uuid.uuid4().hex[:8],
                    "duration_hours": 1.5,
                    "attendee_partner_ids": [(6, 0, [user["partner_id"][0]])],
                }
            ],
        )
        self.retained.append({"model": "community.meeting.series", "id": series})
        self.page.goto(
            "%s/web#model=community.meeting.series&id=%s&view_type=form"
            % (BASE_URL, series)
        )
        self.page.locator('button[name="action_new_meeting"]').click()
        wizard = self.page.get_by_role("dialog").last
        expect(wizard.locator('.o_field_widget[name="series_id"] input')).to_have_value(
            re.compile("Guided series")
        )
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.get_by_text("Estimated Start Datetime", exact=True)
        ).to_be_visible()
        duration = wizard.locator('.o_field_widget[name="duration_hours"] input')
        expect(duration).to_have_value("01:30")
        suggested = wizard.locator('.o_field_widget[name="name"] input')
        expect(suggested).to_have_value(re.compile(r"\d{4}-\d{2}-\d{2} Guided series"))
        name = "Guided meeting " + uuid.uuid4().hex[:8]
        suggested.fill(name)
        wizard.locator('button[name="action_back"]').click()
        wizard.locator('button[name="action_next"]').click()
        expect(wizard.locator('.o_field_widget[name="name"] input')).to_have_value(name)
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.locator('.o_field_widget[name="attendee_partner_ids"]')
        ).to_contain_text(user["partner_id"][1])
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.get_by_text(
                "There are no points to carry over into this meeting.", exact=True
            )
        ).to_be_visible()
        expect(wizard.locator('.o_field_widget[name="carry_line_ids"]')).not_to_be_visible()
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_add_point"]').click()
        point = self.page.get_by_role("dialog").last
        point.locator('.o_field_widget[name="name"] input').fill("Rich guided point")
        point.locator(
            '.o_field_widget[name="description"] [contenteditable="true"]'
        ).fill("Background, proposed action and supporting links.")
        point.locator('.o_field_widget[name="priority"] select').select_option(
            label="Critical"
        )
        expect(
            point.locator('.o_field_widget[name="estimated_minutes"] input')
        ).to_be_visible()
        point.locator('.o_field_widget[name="estimated_minutes"] input').fill("20")
        point.locator('.o_field_widget[name="deadline"] input').fill("12/20/2026")
        point.locator('button[name="action_save"]').click()
        wizard = self.page.get_by_role("dialog").last
        expect(wizard.locator('.o_field_widget[name="line_ids"]')).to_contain_text(
            "Rich guided point"
        )
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.locator('.o_field_widget[name="review_summary"]')
        ).to_contain_text("Rich guided point")
        wizard.locator('button[name="action_finish"]').click()
        expect(
            self.page.locator('.o_form_view .o_field_widget[name="name"] input').first
        ).to_have_value(name)
        meeting_id = self.rpc("community.meeting", "search", [[("name", "=", name)]])[0]
        self.retained.append({"model": "community.meeting", "id": meeting_id})
        values = self.record(
            "community.meeting",
            meeting_id,
            ["duration_minutes", "attendee_partner_ids"],
        )
        self.assertEqual(values["duration_minutes"], 90)
        self.assertEqual(values["attendee_partner_ids"], [user["partner_id"][0]])
        items = self.rpc(
            "community.meeting.agenda.item",
            "search_read",
            [[("meeting_id", "=", meeting_id)]],
            {
                "fields": [
                    "name",
                    "description",
                    "priority",
                    "estimated_minutes",
                    "deadline",
                    "topic_id",
                ]
            },
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(
            (items[0]["priority"], items[0]["estimated_minutes"], items[0]["deadline"]),
            ("3", 20, "2026-12-20"),
        )
        self.assertIn("Background", items[0]["description"])
        self.rpc("community.meeting", "action_schedule", [[meeting_id]])
        self.open_live(meeting_id)
        expect(self.page.locator(".o_live_priority_3")).to_have_attribute(
            "aria-label", "Critical"
        )
        expect(self.page.locator(".o_live_point_meta")).to_contain_text("20 min")
        expect(self.page.locator(".o_live_planned")).to_contain_text("Background")

    def test_followup_points_are_offered_in_new_meeting_wizard(self):
        name = "Follow-up carryover " + uuid.uuid4().hex[:8]
        series = self.rpc("community.meeting.series", "create", [{
            "name": name, "carryover_policy": "review",
        }])
        self.retained.append({"model": "community.meeting.series", "id": series})
        source = self.rpc("community.meeting", "create", [{
            "name": name + " previous",
            "series_id": series,
            "start_datetime": "2026-10-01 10:00:00",
        }])
        point = self.rpc("community.meeting.agenda.item", "create", [{
            "meeting_id": source, "name": "Completed follow-up to review",
        }])
        self.rpc("community.meeting.action", "create", [{
            "meeting_id": source, "agenda_item_id": point,
            "name": "Completed action", "state": "done",
        }])
        self.page.goto(
            "%s/web#model=community.meeting.series&id=%s&view_type=form"
            % (BASE_URL, series)
        )
        self.page.locator('button[name="action_new_meeting"]').click()
        wizard = self.page.get_by_role("dialog").last
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('.o_field_widget[name="start_datetime"] input').fill(
            "10/08/2026 10:00:00"
        )
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        expect(wizard.locator('.o_field_widget[name="carry_line_ids"]')).to_contain_text(
            "Completed follow-up to review"
        )
        self.retained.append({"model": "community.meeting", "id": source})

    def test_selected_carryover_is_materialized_in_new_meeting(self):
        series_name = "Selected carryover " + uuid.uuid4().hex[:8]
        series = self.rpc("community.meeting.series", "create", [{
            "name": series_name, "carryover_policy": "review",
        }])
        self.retained.append({"model": "community.meeting.series", "id": series})
        origin_id = self.rpc("community.meeting", "create", [{
            "name": series_name + " previous", "series_id": series,
            "start_datetime": "2026-10-01 10:00:00",
        }])
        self.retained.append({"model": "community.meeting", "id": origin_id})
        source_name = "Selected point " + uuid.uuid4().hex[:8]
        self.rpc("community.meeting.agenda.item", "create", [{
            "meeting_id": origin_id, "name": source_name,
            "review_next_meeting": True,
        }])
        self.page.goto(
            "%s/web#model=community.meeting.series&id=%s&view_type=form"
            % (BASE_URL, series)
        )
        self.page.locator('button[name="action_new_meeting"]').click()
        wizard = self.page.get_by_role("dialog").last
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('.o_field_widget[name="start_datetime"] input').fill(
            "10/08/2026 10:00:00"
        )
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        row = wizard.locator(
            '.o_field_widget[name="carry_line_ids"] tr.o_data_row'
        ).filter(has_text=source_name)
        expect(row).to_be_visible()
        expect(row.locator('input[data-value="include"]')).to_be_checked()
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.locator('.o_field_widget[name="review_summary"]')
        ).to_contain_text(source_name)
        wizard.locator('button[name="action_finish"]').click()
        expect(wizard).not_to_be_visible(timeout=30000)
        created_meetings = self.rpc(
            "community.meeting", "search_read",
            [[("series_id", "=", series), ("id", "!=", origin_id)]],
            {"fields": ["name", "state", "start_datetime"]},
        )
        self.assertTrue(
            created_meetings,
            "Wizard did not create a meeting. URL=%s; dialog=%r; notifications=%r"
            % (
                self.page.url,
                self.page.get_by_role("dialog").all_text_contents(),
                self.page.locator('[role="alert"]').all_text_contents(),
            ),
        )
        meeting_id = created_meetings[0]["id"]
        self.retained.append({"model": "community.meeting", "id": meeting_id})
        items = self.rpc(
            "community.meeting.agenda.item", "search_read",
            [[("meeting_id", "=", meeting_id)]],
            {"fields": ["name", "carryover_id", "topic_id"]},
        )
        self.assertEqual(len(items), 1)
        self.assertIn(source_name, items[0]["name"])
        self.assertTrue(items[0]["carryover_id"])
        expect(self.page.locator(".o_form_view")).to_contain_text(source_name)

    def test_add_point_from_live_and_cancel(self):
        before = self.rpc(
            "community.meeting.agenda.item",
            "search_count",
            [[("meeting_id", "=", self.meeting_id)]],
        )
        self.page.get_by_role("button", name="Add Point", exact=True).click()
        dialog = self.page.get_by_role("dialog").last
        dialog.locator('.o_field_widget[name="name"] input').fill(
            "Cancelled point draft"
        )
        dialog.get_by_role("button", name="Cancel", exact=True).click()
        expect(dialog).not_to_be_visible()
        self.assertEqual(
            self.rpc(
                "community.meeting.agenda.item",
                "search_count",
                [[("meeting_id", "=", self.meeting_id)]],
            ),
            before,
        )
        self.page.get_by_role("button", name="Add Point", exact=True).click()
        dialog = self.page.get_by_role("dialog").last
        dialog.locator('.o_field_widget[name="name"] input').fill("Live-created point")
        dialog.locator(
            '.o_field_widget[name="description"] [contenteditable="true"]'
        ).fill("Detailed topic from live.")
        dialog.locator('button[name="action_save"]').click()
        card = self.page.locator(".o_live_agenda_card").filter(
            has_text="Live-created point"
        )
        expect(card).to_be_visible()
        self.assertEqual(
            self.rpc(
                "community.meeting.agenda.item",
                "search_count",
                [[("meeting_id", "=", self.meeting_id)]],
            ),
            before + 1,
        )
        card.locator(".o_live_expand").click()
        expect(card.locator(".o_live_planned")).to_contain_text("Detailed topic")

    def test_meetings_root_opens_list_and_preserves_submenus(self):
        self.page.goto(BASE_URL + "/web")
        self.page.locator(".o_navbar_apps_menu").click()
        root = self.page.locator(
            'a[data-menu-xmlid="community_meetings.menu_community_meetings_root"]'
        )
        expect(root).to_be_visible()
        root.click()
        expect(self.page.locator(".o_list_view")).to_be_visible()
        for menu_xmlid in (
            "menu_prepare_meeting",
            "menu_community_meeting_series",
        ):
            expect(
                self.page.locator(
                    'a[data-menu-xmlid="community_meetings.%s"]' % menu_xmlid
                )
            ).to_be_visible()

        self.page.locator(
            'a[data-menu-xmlid="community_meetings.menu_community_meetings_root"]'
        ).click()
        expect(self.page.locator(".o_list_view")).to_be_visible()
        self.page.locator(
            'a[data-menu-xmlid="community_meetings.menu_prepare_meeting"]'
        ).click()
        dialog = self.page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text("New Meeting")
        dialog.get_by_role("button", name="Cancel").click()
        expect(dialog).not_to_be_visible()

    def test_followup_activity_uses_configured_activity_type(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label("Task name").fill("Native meeting follow-up")
        form.get_by_role("button", name="Add follow-up").click()
        row = card.locator('li:has(select[aria-label="Task status"])').last
        expect(row).to_be_visible()
        expect(row.locator(".o_live_followup_task_title")).to_be_visible()
        expect(
            card.get_by_role("button", name="Complete activity", exact=True)
        ).to_have_count(0)
        task_id = self.related("community.meeting.action", "discussion")
        self.assertTrue(
            self.record("community.meeting.action", task_id, ["followup_activity_id"])[
                "followup_activity_id"
            ]
        )
        self.assertEqual(
            self.record("community.meeting.action", task_id, ["followup_kind"])[
                "followup_kind"
            ],
            "activity",
        )

        form.get_by_label("Task name").fill("Odoo call activity")
        activity_type = next(
            (
                row["id"]
                for row in self.rpc(
                    "mail.activity.type",
                    "search_read",
                    [[("active", "=", True)]],
                    {"fields": ["name", "category"], "limit": 50},
                )
                if row.get("category") == "phonecall"
            ),
            None,
        )
        self.assertTrue(activity_type, "Odoo Call activity type must be available")
        form.get_by_label("Activity type").select_option(str(activity_type))
        form.get_by_role("button", name="Add follow-up").click()
        record = self.wait_action_record("Odoo call activity")
        activity_row = card.locator("li").filter(has_text="Odoo call activity")
        expect(activity_row.get_by_role("button", name="Create Project task")).to_have_count(0)
        self.assertEqual(record["agenda_item_id"][0], self.item_ids["discussion"])
        self.assertEqual(record["followup_kind"], "activity")
        self.assertTrue(record["followup_activity_id"])
        self.assertEqual(
            self.record(
                "mail.activity", record["followup_activity_id"][0], ["activity_type_id"]
            )["activity_type_id"][0],
            activity_type,
        )

        form.get_by_label("Task name").fill("Native Odoo to-do")
        native_todo = self.rpc(
            "mail.activity.type",
            "search_read",
            [[("name", "=", "To-Do")]],
            {"fields": ["id"], "limit": 1},
        )
        self.assertTrue(native_todo, "The native Odoo To-Do type must be installed")
        form.get_by_label("Activity type").select_option(str(native_todo[0]["id"]))
        form.get_by_role("button", name="Add follow-up").click()
        todo_record = self.wait_action_record("Native Odoo to-do")
        self.assertEqual(todo_record["agenda_item_id"][0], self.item_ids["discussion"])
        self.assertEqual(todo_record["followup_kind"], "activity")
        self.assertTrue(todo_record["followup_activity_id"])
        todo_activity = self.record(
            "mail.activity",
            todo_record["followup_activity_id"][0],
            ["activity_type_id"],
        )
        self.assertEqual(todo_activity["activity_type_id"][0], native_todo[0]["id"])

    def test_automatic_continuation_reuses_identity_and_links(self):
        series = self.rpc(
            "community.meeting.series",
            "create",
            [
                {
                    "name": "Automatic " + uuid.uuid4().hex[:8],
                    "carryover_policy": "automatic",
                }
            ],
        )
        self.rpc(
            "community.meeting", "write", [[self.meeting_id], {"series_id": series}]
        )
        self.rpc(
            "community.meeting.agenda.item",
            "write",
            [
                [self.item_ids["discussion"]],
                {
                    "description": '<p>Read <a href="https://example.org/reference">the reference</a></p>',
                    "priority": "2",
                },
            ],
        )
        self.open_live(self.meeting_id)
        card = self.card("discussion")
        card.get_by_role("button", name="Postpone agenda point").click()
        card.get_by_label("Reason for postponing").fill("Continue this point next time")
        card.get_by_role("button", name="Leave postponed", exact=True).click()
        expect(self.outcome("discussion")).to_have_text("Postponed")
        self.wait_field("community.meeting.agenda.item", self.item_ids["discussion"], "review_next_meeting", True)
        self.assertTrue(
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["discussion"],
                ["review_next_meeting"],
            )["review_next_meeting"]
        )
        destination = self.rpc(
            "community.meeting",
            "create",
            [
                {
                    "name": "Automatic next",
                    "series_id": series,
                    "start_datetime": "2030-01-01 10:00:00",
                }
            ],
        )
        self.retain_carryover = True
        self.retained.extend(
            [
                {"model": "community.meeting", "id": destination},
                {"model": "community.meeting.series", "id": series},
            ]
        )
        self.rpc("community.meeting", "action_refresh_carryovers", [[destination]])
        items = self.rpc(
            "community.meeting.agenda.item",
            "search_read",
            [[("meeting_id", "=", destination)]],
            {"fields": ["topic_id", "name"]},
        )
        self.assertEqual(len(items), 1)
        original = self.record(
            "community.meeting.agenda.item", self.item_ids["discussion"], ["topic_id"]
        )
        self.assertEqual(original["topic_id"][0], items[0]["topic_id"][0])
        self.rpc("community.meeting", "action_schedule", [[destination]])
        self.open_live(destination)
        expect(self.page.get_by_role("link", name="the reference")).to_have_attribute(
            "href", "https://example.org/reference"
        )
        expect(self.page.locator(".o_live_priority_2")).to_have_attribute(
            "aria-label", "High"
        )

    def test_review_continuations_from_live(self):
        series = self.rpc(
            "community.meeting.series",
            "create",
            [{"name": "Live review " + uuid.uuid4().hex[:8]}],
        )
        self.rpc(
            "community.meeting", "write", [[self.meeting_id], {"series_id": series}]
        )
        self.rpc(
            "community.meeting.agenda.item",
            "write",
            [
                [self.item_ids["discussion"], self.item_ids["information"]],
                {"review_next_meeting": True},
            ],
        )
        destination = self.rpc(
            "community.meeting",
            "create",
            [
                {
                    "name": "Review next",
                    "series_id": series,
                    "start_datetime": "2030-01-01 10:00:00",
                }
            ],
        )
        self.retain_carryover = True
        self.retained.extend(
            [
                {"model": "community.meeting", "id": destination},
                {"model": "community.meeting.series", "id": series},
            ]
        )
        self.rpc("community.meeting", "action_schedule", [[destination]])
        self.open_live(destination)
        inbox = self.page.get_by_role("region", name="Points to continue")
        expect(inbox).to_be_visible()
        discussion = inbox.locator("div.mb-2").filter(
            has_text="Browser Discussion case"
        )
        discussion.get_by_role("button", name="Accept", exact=True).click()
        expect(self.card("discussion")).to_be_visible()
        information = inbox.locator("div.mb-2").filter(
            has_text="Browser Information case"
        )
        information.get_by_role("button", name="Dismiss", exact=True).click()
        expect(inbox).not_to_be_visible()
        self.assertEqual(
            self.rpc(
                "community.meeting.agenda.item",
                "search_count",
                [[("meeting_id", "=", destination)]],
            ),
            1,
        )

    def test_approve_and_download_minutes(self):
        card = self.card("decision")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        card.get_by_placeholder("Agreement title").fill(
            "Approval for published minutes"
        )
        card.get_by_placeholder("What was agreed?").fill(
            "Approve this proposal with its recorded context."
        )
        card.get_by_role("button", name="Add agreement", exact=True).click()
        expect(self.outcome("decision")).to_have_text("Approved")
        private = (
            self.card("discussion")
            .locator("details")
            .filter(has_text="Private editorial notes")
        )
        private.locator("summary").click()
        private.get_by_role("button", name="Add private note", exact=True).click()
        private.get_by_label("Private editorial note", exact=True).fill(
            "PRIVATE_NOT_FOR_PUBLICATION"
        )
        private.get_by_role("button", name="Add private note", exact=True).click()
        expect(private.locator(".o_live_rich_readonly")).to_contain_text(
            "PRIVATE_NOT_FOR_PUBLICATION"
        )
        self.page.get_by_role("button", name="Finish Meeting", exact=True).click()
        expect(self.page.get_by_role("button", name="Prepare Minutes", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="Prepare Minutes", exact=True).click()
        self.wait_field("community.meeting", self.meeting_id, "state", "minutes_draft")
        self.open_form()
        self.page.locator('button[name="action_approve_minutes"]').click()
        self.wait_field("community.meeting", self.meeting_id, "state", "approved")
        revision_id = self.record(
            "community.meeting", self.meeting_id, ["approved_revision_id"]
        )["approved_revision_id"][0]
        snapshot = self.record(
            "community.meeting.revision", revision_id, ["snapshot_json", "pdf_sha256"]
        )
        self.assertNotIn("PRIVATE_NOT_FOR_PUBLICATION", snapshot["snapshot_json"])
        self.assertIn("Approval for published minutes", snapshot["snapshot_json"])
        self.page.get_by_role("tab", name="Approved Revisions").click()
        with self.page.expect_download(timeout=30000) as downloaded:
            self.page.locator('.o_field_widget[name="revision_ids"] button').filter(
                has_text="PDF"
            ).click()
        download = downloaded.value
        pdf = Path(download.path()).read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(
            __import__("hashlib").sha256(pdf).hexdigest(), snapshot["pdf_sha256"]
        )
        # Current point content can evolve while the approved snapshot stays fixed.
        topic = self.record(
            "community.meeting.agenda.item", self.item_ids["discussion"], ["topic_id"]
        )["topic_id"][0]
        self.rpc(
            "community.meeting.topic",
            "write",
            [[topic], {"name": "Updated after approval"}],
        )
        self.assertEqual(
            self.record("community.meeting.revision", revision_id, ["snapshot_json"])[
                "snapshot_json"
            ],
            snapshot["snapshot_json"],
        )

    def test_save_failure_keeps_text_and_retry_persists(self):
        target = "**/web/dataset/call_kw/community.meeting.agenda.item/write"

        def fail_once(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "error": {
                            "code": 200,
                            "message": "Injected save failure",
                            "data": {
                                "name": "odoo.exceptions.ValidationError",
                                "message": "Injected save failure",
                                "arguments": ["Injected save failure"],
                                "debug": "",
                            },
                        },
                    }
                ),
            )

        self.page.route(target, fail_once, times=1)
        editor = self.card("discussion").locator(
            '[contenteditable="true"][aria-label="Discussion notes"]'
        )
        self.edit_rich(editor, "Unsaved text must survive an error")
        expect(self.page.get_by_role("alert").filter(has_text="Some changes could not be saved.")).to_be_visible()
        expect(editor).to_contain_text("Unsaved text must survive")
        self.assertNotIn(
            "Unsaved text",
            self.record(
                "community.meeting.agenda.item",
                self.item_ids["discussion"],
                ["discussion_notes"],
            )["discussion_notes"]
            or "",
        )
        self.edit_rich(editor, "Recovered notes after retry")
        self.wait_field(
            "community.meeting.agenda.item",
            self.item_ids["discussion"],
            "discussion_notes",
            "Recovered notes after retry",
        )
        self.consume_injected_write_error("Injected save failure")

    def test_mobile_point_wizard_and_keyboard_cancel(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        try:
            self.page.get_by_role("button", name="Add Point", exact=True).click()
            dialog = self.page.get_by_role("dialog").last
            title = dialog.locator('.o_field_widget[name="name"] input')
            title.click()
            title.press_sequentially("Keyboard-only draft")
            title.press("Tab")
            self.assertLessEqual(
                dialog.evaluate("el => el.scrollWidth - el.clientWidth"), 1
            )
            cancel = dialog.get_by_role("button", name="Cancel", exact=True)
            cancel.focus()
            cancel.press("Enter")
            expect(dialog).not_to_be_visible()
            self.assertEqual(
                self.rpc(
                    "community.meeting.agenda.item",
                    "search_count",
                    [
                        [
                            ("meeting_id", "=", self.meeting_id),
                            ("name", "=", "Keyboard-only draft"),
                        ]
                    ],
                ),
                0,
            )
        finally:
            self.page.set_viewport_size({"width": 1440, "height": 1000})

    def test_wizard_excludes_automatic_point_and_preserves_choice(self):
        name = "Automatic exclusion " + uuid.uuid4().hex[:8]
        series = self.rpc(
            "community.meeting.series",
            "create",
            [{"name": name, "carryover_policy": "automatic"}],
        )
        self.rpc(
            "community.meeting", "write", [[self.meeting_id], {"series_id": series}]
        )
        self.rpc(
            "community.meeting.agenda.item",
            "write",
            [[self.item_ids["discussion"]], {"review_next_meeting": True}],
        )
        self.retain_carryover = True
        self.page.goto(
            "%s/web#model=community.meeting.series&id=%s&view_type=form"
            % (BASE_URL, series)
        )
        self.page.locator('button[name="action_new_meeting"]').click()
        wizard = self.page.get_by_role("dialog").last
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('.o_field_widget[name="start_datetime"] input').fill(
            "01/01/2030 10:00:00"
        )
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        row = wizard.locator(
            '.o_field_widget[name="carry_line_ids"] tr.o_data_row'
        ).filter(has_text="Browser Discussion case")
        expect(row).to_be_visible()
        rows = wizard.locator('.o_field_widget[name="carry_line_ids"] tr.o_data_row')
        expect(rows).to_have_count(1)
        row = rows.first
        row.locator('td[name="decision"]').click()
        row.locator('input[data-value="discard"]').check()
        wizard.locator('button[name="action_back"]').click()
        wizard.locator('button[name="action_next"]').click()
        expect(row.locator('input[data-value="discard"]')).to_be_checked()
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_finish"]').click()
        expect(self.page.get_by_role("dialog")).to_have_count(0)
        expect(self.page.locator(".o_form_view")).to_be_visible()
        meetings = self.rpc(
            "community.meeting",
            "search",
            [[("series_id", "=", series), ("id", "!=", self.meeting_id)]],
        )
        self.assertEqual(len(meetings), 1)
        self.retain_carryover = True
        self.retained.extend(
            [
                {"model": "community.meeting", "id": meetings[0]},
                {"model": "community.meeting.series", "id": series},
            ]
        )
        self.assertEqual(
            self.rpc(
                "community.meeting.agenda.item",
                "search_count",
                [[("meeting_id", "=", meetings[0])]],
            ),
            0,
        )

    def test_concurrent_confirmation_is_idempotent(self):
        import concurrent.futures
        from urllib.request import Request, urlopen

        wizard = self.rpc(
            "community.meeting.create.wizard",
            "create",
            [
                {
                    "name": "Concurrent guided meeting",
                    "start_datetime": "2030-01-01 10:00:00",
                }
            ],
        )
        cookies = "; ".join(
            "%s=%s" % (c["name"], c["value"])
            for c in self.context.cookies()
            if c["name"] == "session_id"
        )
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": {
                    "model": "community.meeting.create.wizard",
                    "method": "action_finish",
                    "args": [[wizard]],
                    "kwargs": {},
                },
            }
        ).encode()

        def confirm():
            request = Request(
                BASE_URL
                + "/web/dataset/call_kw/community.meeting.create.wizard/action_finish",
                data=payload,
                headers={"Content-Type": "application/json", "Cookie": cookies},
            )
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: confirm(), range(2)))
        for reply in replies:
            self.assertNotIn("error", reply)
        self.assertEqual(replies[0]["result"]["res_id"], replies[1]["result"]["res_id"])
        self.retained.append(
            {"model": "community.meeting", "id": replies[0]["result"]["res_id"]}
        )

    def test_concurrent_task_cancellation_keeps_a_valid_followup(self):
        import concurrent.futures
        from urllib.request import Request, urlopen

        action_ids = [
            self.rpc(
                "community.meeting.action",
                "create",
                [
                    {
                        "meeting_id": self.meeting_id,
                        "agenda_item_id": self.item_ids["todo"],
                        "name": "Concurrent task %s" % n,
                    }
                ],
            )
            for n in range(2)
        ]
        self.rpc(
            "community.meeting.agenda.item",
            "write",
            [[self.item_ids["todo"]], {"disposition": "closed"}],
        )
        cookies = "; ".join(
            "%s=%s" % (c["name"], c["value"])
            for c in self.context.cookies()
            if c["name"] == "session_id"
        )

        def cancel(action_id):
            payload = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "call",
                    "params": {
                        "model": "community.meeting.action",
                        "method": "write",
                        "args": [[action_id], {"state": "cancelled"}],
                        "kwargs": {},
                    },
                }
            ).encode()
            request = Request(
                BASE_URL + "/web/dataset/call_kw/community.meeting.action/write",
                data=payload,
                headers={"Content-Type": "application/json", "Cookie": cookies},
            )
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(cancel, action_ids))
        self.assertEqual(sum("result" in reply for reply in replies), 1)
        self.assertEqual(sum("error" in reply for reply in replies), 1)
        self.assertEqual(
            self.rpc(
                "community.meeting.action",
                "search_count",
                [[("id", "in", action_ids), ("state", "!=", "cancelled")]],
            ),
            1,
        )
        self.assertEqual(
            self.record(
                "community.meeting.agenda.item", self.item_ids["todo"], ["disposition"]
            )["disposition"],
            "closed",
        )


class CoverageResult(unittest.TextTestResult):
    passed = set()

    def addSuccess(self, test):
        self.passed.add(test._testMethodName)
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.capture(test)
        super().addFailure(test, err)

    def addError(self, test, err):
        self.capture(test)
        super().addError(test, err)

    def capture(self, test):
        ARTIFACTS.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            test.page.screenshot(
                path=str(ARTIFACTS / (test._testMethodName + ".png")), full_page=True
            )
        except Exception:
            pass  # Preserve the original failure if the browser itself has died.


def run_suite(test_case=FullMeetingBrowserChecks, actions=ACTIONS):
    if "--list-actions" in sys.argv:
        print(json.dumps(actions, indent=2))
        raise SystemExit(0)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_case)
    if len(sys.argv) > 1:
        suite = unittest.TestSuite(
            t for t in suite if any(part in t._testMethodName for part in sys.argv[1:])
        )
    result = unittest.TextTestRunner(verbosity=2, resultclass=CoverageResult).run(suite)
    covered = [
        a
        for method, method_actions in actions.items()
        if method in result.passed
        for a in method_actions
    ]
    total = sum(map(len, actions.values()))
    report = {
        "suite": test_case.__name__,
        "tests_run": result.testsRun,
        "tests_passed": len(result.passed),
        "tests_failed": len(result.failures),
        "tests_errored": len(result.errors),
        "tests_skipped": [{"test": str(test), "reason": reason} for test, reason in result.skipped],
        "total_actions": total,
        "passed_actions": len(covered),
        "percent": round(100 * len(covered) / total, 1),
        "covered": covered,
        "uncovered": [
            a
            for m, method_actions in actions.items()
            if m not in result.passed
            for a in method_actions
        ],
        "retained_records": test_case.retained,
        "scope": "Explicit inventory of frequent current editor actions; not code coverage or measured user telemetry.",
    }
    ARTIFACTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    (ARTIFACTS / "coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        "Action coverage: %s/%s (%s%%). Report: %s"
        % (len(covered), total, report["percent"], ARTIFACTS / "coverage.json")
    )
    raise SystemExit(
        0
        if result.wasSuccessful() and not result.skipped and (len(sys.argv) > 1 or report["percent"] >= 90)
        else 1
    )


if __name__ == "__main__":
    run_suite()
