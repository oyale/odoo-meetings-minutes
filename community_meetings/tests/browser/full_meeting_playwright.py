#!/usr/bin/env python3
"""Full browser regression suite. See README.md for scope, credentials and cleanup."""

import json
import os
import re
import sys
import time
import unittest
import uuid
from datetime import datetime
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[3] / "tests"
sys.path.insert(0, str(TESTS_ROOT))

from browser_support.screenshot_capture import capture_checkpoint, capture_failure
from live_meeting_playwright import BASE_URL, LiveMeetingBrowserChecks
from playwright.sync_api import expect

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
    "test_focus_mode_presents_one_point_at_a_time": [
        "switch to one-point focus mode",
        "navigate between focused points",
        "keep the focused point editor and enlarge control in focus mode",
        "check mobile focus layout for overflow",
        "return to full agenda",
    ],
    "test_next_meeting_datetime_is_primary_in_agenda": [
        "see next meeting date without expanding its point",
        "keep next meeting date prominent in focus mode",
    ],
    "test_discussion_notes_can_expand_and_description_stays_visible": [
        "read point description without another disclosure",
        "see estimated point duration in collapsed header",
        "enlarge discussion notes editor",
        "restore compact notes editor",
    ],
    "test_notes_autosave_and_reload": [
        "edit discussion notes",
        "edit meeting notes",
        "persist after reload",
    ],
    "test_private_note_create_and_edit": ["save private note", "edit private note"],
    "test_point_presenter_badge_and_related_points": [
        "see the point responsible badge",
        "see and follow related points",
        "inspect linked Odoo activity details",
        "open a linked Odoo activity",
    ],
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
    "test_minutes_preview_returns_to_draft_meeting": [
        "preview saved draft minutes and return to meeting",
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
    "test_recurring_agenda_template_selection_and_lineage": [
        "create a recurring agenda template",
        "set whether its occurrence can be reordered",
        "include and skip template per meeting",
        "keep the occurrence fixed in the meeting agenda",
        "link occurrence to previous occurrence",
    ],
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
        "choose a behavior-specific agenda type card",
        "navigate agenda type cards with the keyboard",
        "point priority",
        "optional deadline",
        "optional time estimate",
        "priority in live",
        "hide empty carryover list",
        "suggest series meeting name",
        "allow meeting name override",
    ],
    "test_guided_meeting_uses_agreed_date_when_selecting_series": [
        "select a series in the guided meeting wizard",
        "use the date agreed in the previous meeting",
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
    "test_live_view_is_available_in_draft_and_respects_add_policy": [
        "open draft meeting workspace",
        "respect series point-add policy",
    ],
    "test_live_header_shows_coordinator_before_minutes_secretary": [
        "show meeting coordinator in live header",
        "place coordinator before minutes secretary",
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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        requested_locale = os.environ.get("MM_CAPTURE_LANGUAGE")
        cls.capture_locale = cls.session.verify_locale(
            requested_locale or cls.session.session_info().get("user_context", {}).get("lang")
        )

    def setUp(self):
        self.errors_before = len(self.console_errors)
        super().setUp()
        self.page.set_default_timeout(10000)
        if os.environ.get("PLAYWRIGHT_TRACE", "1").lower() not in {
            "0",
            "false",
            "no",
        }:
            self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self.addCleanup(self.save_trace)

    def effective_locale(self):
        return self.capture_locale

    def capture_visual_screenshot(self, name, viewport=None):
        self.session.verify_locale(self.effective_locale())
        if not hasattr(self, "_visual_capture_locale"):
            self._visual_capture_locale = self.effective_locale()
        capture_checkpoint(
            self.page,
            name,
            self.id().replace(".", "-"),
            self._visual_capture_locale,
            viewport,
        )

    def locale_formats(self):
        languages = self.rpc(
            "res.lang",
            "search_read",
            [[("code", "=", self.effective_locale())]],
            {"fields": ["date_format", "time_format"], "limit": 1},
        )
        if len(languages) != 1:
            raise AssertionError(f"Odoo has no unique language config for {self.effective_locale()!r}")
        return languages[0]

    def localized_date(self, value):
        date_value = datetime.strptime(value, "%Y-%m-%d")
        return date_value.strftime(self.locale_formats()["date_format"])

    def localized_datetime(self, value):
        date_value = datetime.strptime(value, "%m/%d/%Y %H:%M")
        formats = self.locale_formats()
        return date_value.strftime(f"{formats['date_format']} {formats['time_format']}")

    def unresolved_points_warning(self, points):
        source = (
            "%(count)s agenda point(s) are not resolved:\n"
            "%(points)s%(more)s\n\n"
            "Finish the meeting anyway?"
        )
        translated = self.ui_text("community_meetings", source)
        point_list = "\n".join(f"• {point}" for point in points)
        return translated % {"count": len(points), "points": point_list, "more": ""}

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
            "checkbox", name=self.ui_text("community_meetings", "Review at next meeting")
        )
        checkbox.click()
        expect(self.page.get_by_role("alert").filter(has_text=self.ui_text("community_meetings", "Some changes could not be saved."))).to_be_visible()
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
            "checkbox", name=self.ui_text("community_meetings", "Review at next meeting")
        )
        self.assertTrue(checkbox.evaluate("el => Boolean(el.closest('.o_live_point_footer'))"))
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
        expect(
            self.card("information").locator('[contenteditable="true"]').first
        ).to_be_visible()

    def test_navigation_and_filter(self):
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
        expect(self.card("information", begin=False).locator(".o_live_expand")).to_have_attribute(
            "aria-expanded", "false"
        )
        self.card("information", begin=False).locator(".o_live_expand").click()
        expect(self.card("information", begin=False).locator(".o_live_expand")).to_have_attribute(
            "aria-expanded", "true"
        )
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Next agenda point")).click()
        expect(self.card("discussion", begin=False)).to_have_class(re.compile("o_live_current"))
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Previous agenda point")).click()
        expect(self.card("information", begin=False)).to_have_class(re.compile("o_live_current"))
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"))).to_be_visible()
        information = self.card("information", begin=False)
        information.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        information.get_by_role("button", name=self.ui_text("community_meetings", "Done")).click()
        expect(self.outcome("information")).to_have_text(self.ui_text("community_meetings", "Done"))
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pending only")).click()
        expect(
            self.page.locator(".o_live_agenda_card").filter(has_text="Browser Information case")
        ).to_have_count(0)
        expect(self.page.locator(".o_live_agenda_card")).to_have_count(3)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pending only")).click()
        expect(self.card("information")).to_be_visible()

    def test_notes_autosave_and_reload(self):
        self.edit_rich(
            self.card("discussion").locator(
                self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes")
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
            self.page.locator(self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Meeting minutes"]', "Meeting minutes")),
            "Session notes persisted",
        )
        self.wait_field(
            "community.meeting",
            self.meeting_id,
            "minutes_notes",
            "Session notes persisted",
        )
        self.open_form()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
        expect(
            self.card("discussion").locator(
                self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes")
            )
        ).to_contain_text("Discussion persisted")
        expect(
            self.page.locator(self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Meeting minutes"]', "Meeting minutes"))
        ).to_contain_text("Session notes persisted")

    def test_private_note_create_and_edit(self):
        details = (
            self.card("discussion")
            .locator("details")
            .filter(has_text=self.ui_text("community_meetings", "Private editorial notes"))
        )
        details.locator("summary").click()
        details.get_by_role("button", name=self.ui_text("community_meetings", "Add private note"), exact=True).click()
        details.get_by_label(self.ui_text("community_meetings", "Private editorial note"), exact=True).fill("Private draft")
        details.get_by_role("button", name=self.ui_text("community_meetings", "Add private note"), exact=True).click()
        expect(details.locator(".o_live_rich_readonly")).to_contain_text(
            "Private draft"
        )
        note = self.related("community.meeting.editor.note", "discussion")
        details.get_by_role("button", name=self.ui_text("community_meetings", "Edit private note"), exact=True).click()
        self.edit_rich(
            details.locator('[contenteditable="true"]'), "Revised private draft"
        )
        self.wait_field(
            "community.meeting.editor.note", note, "content", "Revised private draft"
        )

    def test_task_editing(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label(self.ui_text("community_meetings", "Task name"), exact=True).fill("Browser follow-up")
        owners = (
            form.get_by_label(self.ui_text("community_meetings", "Task owner"))
            .locator("option")
            .evaluate_all("(els) => els.map(e => e.value).filter(Boolean)")
        )
        self.assertTrue(owners)
        editor_id = self.rpc(
            "res.users", "search", [[("login", "=", os.environ["ODOO_LOGIN"])]]
        )[0]
        form.get_by_label(self.ui_text("community_meetings", "Task owner")).select_option(str(editor_id))
        form.get_by_label(self.ui_text("community_meetings", "Deadline"), exact=True).fill("2027-02-01")
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up")).click()
        row = card.locator(self.ui_selector("community_meetings", 'li:has(select[aria-label="Task status"])', "Task status"))
        expect(row).to_be_visible()
        task = self.related("community.meeting.action", "discussion")
        self.assertEqual(
            self.record("community.meeting.action", task, ["responsible_user_id"])[
                "responsible_user_id"
            ][0],
            editor_id,
        )
        row.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Renamed follow-up")
        row.get_by_label(self.ui_text("community_meetings", "Task name")).press("Tab")
        self.wait_field("community.meeting.action", task, "name", "Renamed follow-up")
        row.get_by_label(self.ui_text("community_meetings", "Task deadline")).fill("2027-02-02")
        row.get_by_label(self.ui_text("community_meetings", "Task deadline")).press("Tab")
        self.wait_field("community.meeting.action", task, "deadline", "2027-02-02")
        for state in ("in_progress", "done", "open", "cancelled"):
            row.get_by_label(self.ui_text("community_meetings", "Task status")).select_option(state)
            self.wait_field("community.meeting.action", task, "state", state)

    def test_followup_can_be_deleted_while_point_is_open(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Remove this follow-up")
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        row = card.locator(self.ui_selector("community_meetings", 'li:has(select[aria-label="Task status"])', "Task status")).last
        expect(row.get_by_role("button", name=self.ui_text("community_meetings", "Delete follow-up"))).to_be_visible()
        action_id = self.related("community.meeting.action", "discussion")
        row.get_by_role("button", name=self.ui_text("community_meetings", "Delete follow-up")).click()
        expect(row).not_to_be_visible()
        self.assertFalse(self.rpc("community.meeting.action", "search", [[("id", "=", action_id)]]))

    def test_dissent_editing(self):
        self.test_dissent_author_reason_and_statement_are_usable()
        row = self.card("discussion").locator(".o_live_record_list li").first
        row.get_by_text(self.ui_text("community_meetings", "Edit details"), exact=True).click()
        row.get_by_label(self.ui_text("community_meetings", "Author"), exact=True).fill("Grace Hopper")
        row.get_by_label(self.ui_text("community_meetings", "Author"), exact=True).press("Tab")
        record_id = self.related("community.meeting.dissent", "discussion")
        self.wait_field(
            "community.meeting.dissent",
            record_id,
            "author_display_name",
            "Grace Hopper",
        )
        row.get_by_label(self.ui_text("community_meetings", "Dissent reason")).select_option(label=self.ui_text("community_meetings", "Dissent"))
        dissent_reason = self.rpc(
            "community.meeting.dissent.reason", "search", [[("name", "=", "Dissent")]], {"limit": 1}
        )[0]
        deadline = time.time() + 10
        saved = self.record("community.meeting.dissent", record_id, ["reason_id"])["reason_id"]
        while time.time() < deadline and (not saved or saved[0] != dissent_reason):
            self.page.wait_for_timeout(100)
            saved = self.record("community.meeting.dissent", record_id, ["reason_id"])["reason_id"]
        self.assertEqual(saved[1], "Dissent")
        row.get_by_role("button", name=self.ui_text("community_meetings", "Edit statement")).click()
        self.edit_rich(
            row.locator('[contenteditable="true"]'), "Alternative proposal in detail"
        )
        self.wait_field(
            "community.meeting.dissent", record_id, "body", "Alternative proposal"
        )

    def test_deferral_cancel(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).click()
        card.get_by_label(self.ui_text("community_meetings", "Reason for postponing")).fill("Unconfirmed reason")
        card.locator(".o_live_deferral").get_by_role(
            "button", name=self.ui_text("community_meetings", "Cancel"), exact=True
        ).click()
        expect(card.get_by_label(self.ui_text("community_meetings", "Reason for postponing"))).to_have_count(0)
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Edit attendees")).click()
        self.page.get_by_label(self.ui_text("community_meetings", "Find contacts")).fill(partner_name)
        option = self.page.locator(".o_live_attendee_options").get_by_label(
            partner_name, exact=True
        )
        option.check()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Save attendees")).click()
        self.wait_field(
            "community.meeting", self.meeting_id, "attendee_partner_ids", [partner_id]
        )
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Edit attendees")).click()
        self.page.locator(".o_live_selected_attendees").get_by_label(
            partner_name, exact=True
        ).uncheck()
        self.page.locator(".o_live_attendee_editor").get_by_role(
            "button", name=self.ui_text("community_meetings", "Cancel"), exact=True
        ).click()
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["attendee_partner_ids"])[
                "attendee_partner_ids"
            ],
            [partner_id],
        )
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Edit attendees")).click()
        self.page.locator(".o_live_selected_attendees").get_by_label(
            partner_name, exact=True
        ).uncheck()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Save attendees")).click()
        self.wait_field(
            "community.meeting", self.meeting_id, "attendee_partner_ids", []
        )

    def test_session_lifecycle(self):
        self.rpc("community.meeting", "write", [[self.meeting_id], {"duration_minutes": 95}])
        self.page.reload(wait_until="domcontentloaded")
        expect(self.page.locator(".o_live_duration_chip")).to_contain_text("01:35")
        reorder_toggle = self.page.locator(".o_live_reorder_mode_toggle")
        expect(reorder_toggle).to_be_visible()
        expect(self.page.locator(".o_live_reorder_rail")).to_have_count(0)
        reorder_toggle.click()
        expect(self.page.locator(".o_live_reorder_rail").first).to_be_visible()
        reorder_toggle.click()
        expect(self.page.locator(".o_live_reorder_rail")).to_have_count(0)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting"), exact=True).click()
        expect(
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"), exact=True)
        ).to_be_visible()
        reorder_toggle = self.page.locator(".o_live_reorder_mode_toggle")
        expect(reorder_toggle).to_be_visible()
        expect(self.page.locator(".o_live_reorder_rail")).to_have_count(0)
        self.capture_visual_screenshot("live-agenda-reordering-hidden")
        reorder_toggle.click()
        expect(reorder_toggle).to_have_attribute("aria-pressed", "true")
        first_rail = self.page.locator(".o_live_reorder_rail").first
        first_card = self.page.locator(".o_live_agenda_card").first
        expect(first_rail).to_be_visible()
        rail_box = first_rail.bounding_box()
        card_box = first_card.bounding_box()
        self.assertIsNotNone(rail_box)
        self.assertIsNotNone(card_box)
        self.assertLess(
            rail_box["x"] + rail_box["width"],
            card_box["x"],
            "The live reorder controls must sit to the left of the agenda card.",
        )
        expect(reorder_toggle).to_contain_text(self.ui_text("community_meetings", "Done reordering"))
        self.capture_visual_screenshot("live-agenda-reordering-active")
        move_down_label = self.ui_text(
            "community_meetings",
            "Move %(point)s down from position %(position)s of %(total)s",
        ) % {"point": "Browser Information case", "position": 1, "total": 4}
        move_down = self.page.get_by_role("button", name=move_down_label)
        expect(move_down).to_be_visible()
        move_down.focus()
        move_down.press("Enter")
        expect(self.page.locator(".o_live_agenda_card").first).to_contain_text(
            "Browser Discussion case"
        )
        self.page.set_viewport_size({"width": 390, "height": 844})
        mobile_rail = self.page.locator(".o_live_reorder_rail").first
        mobile_card = self.page.locator(".o_live_agenda_card").first
        mobile_rail_box = mobile_rail.bounding_box()
        mobile_card_box = mobile_card.bounding_box()
        self.assertIsNotNone(mobile_rail_box)
        self.assertIsNotNone(mobile_card_box)
        self.assertLessEqual(
            mobile_rail_box["y"] + mobile_rail_box["height"],
            mobile_card_box["y"],
            "On mobile, reorder controls must appear above the agenda card.",
        )
        for button in mobile_rail.locator(".btn").all():
            button_box = button.bounding_box()
            self.assertIsNotNone(button_box)
            self.assertGreaterEqual(button_box["width"], 44)
            self.assertGreaterEqual(button_box["height"], 44)
        mobile_move_down_label = self.ui_text(
            "community_meetings",
            "Move %(point)s down from position %(position)s of %(total)s",
        ) % {"point": "Browser Discussion case", "position": 1, "total": 4}
        mobile_move_down = self.page.get_by_role("button", name=mobile_move_down_label)
        expect(mobile_move_down).to_be_visible()
        expect(mobile_move_down).to_be_enabled()
        mobile_move_down.tap()
        expect(self.page.locator(".o_live_agenda_card").first).to_contain_text(
            "Browser Information case"
        )
        self.capture_visual_screenshot("live-agenda-reordering-active")
        self.page.set_viewport_size({"width": 1440, "height": 1000})
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Done reordering"), exact=True
        ).click()
        expect(
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Reorder agenda"), exact=True)
        ).to_have_attribute(
            "aria-pressed", "false"
        )
        expect(self.page.locator(".o_live_reorder_rail")).to_have_count(0)
        self.page.reload(wait_until="domcontentloaded")
        expect(self.page.locator(".o_live_agenda_card").first).to_contain_text(
            "Browser Information case"
        )
        self.assertTrue(
            self.record(
                "community.meeting", self.meeting_id, ["actual_start_datetime"]
            )["actual_start_datetime"]
        )
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"), exact=True).click()
        dialog = self.page.get_by_role("dialog")
        expect(
            dialog
        ).to_contain_text(
            self.unresolved_points_warning(
                [
                    "Browser Information case",
                    "Browser Discussion case",
                    "Browser Decision case",
                    "Browser Todo case",
                ]
            )
        )
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Continue meeting"), exact=True).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"), exact=True)).to_be_visible()
        self.assertEqual(self.record("community.meeting", self.meeting_id, ["state"])["state"], "scheduled")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"), exact=True).click()
        self.page.get_by_role("dialog").get_by_role("button", name=self.ui_text("community_meetings", "Finish meeting"), exact=True).click()
        expect(
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Prepare Minutes"), exact=True)
        ).to_be_visible()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Prepare Minutes"), exact=True).click()
        self.wait_field("community.meeting", self.meeting_id, "state", "minutes_draft")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Back to Meetings")).click()
        expect(self.page.locator(".o_list_view")).to_be_visible()

    def test_already_held(self):
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Record as Already Held"), exact=True
        ).click()
        dialog = self.page.get_by_role("dialog")
        expect(
            dialog
        ).to_contain_text(
            self.unresolved_points_warning(
                [
                    "Browser Information case",
                    "Browser Discussion case",
                    "Browser Decision case",
                    "Browser Todo case",
                ]
            )
        )
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Finish meeting"), exact=True).click()
        expect(
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Prepare Minutes"), exact=True)
        ).to_be_visible()
        record = self.record(
            "community.meeting", self.meeting_id, ["state", "actual_end_datetime"]
        )
        self.assertEqual(record["state"], "held")
        self.assertTrue(record["actual_end_datetime"])

    def test_point_type(self):
        card = self.card("information")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Change point type")).click()
        type_id = self.record(
            "community.meeting.agenda.item",
            self.item_ids["discussion"],
            ["agenda_type_id"],
        )["agenda_type_id"][0]
        card.get_by_label(self.ui_text("community_meetings", "Point type"), exact=True).select_option(str(type_id))
        expect(card.get_by_role("button", name=self.ui_text("community_meetings", "Done"))).to_be_visible()
        self.wait_field(
            "community.meeting.agenda.item",
            self.item_ids["information"],
            "kind",
            "discussion",
        )

    def test_point_presenter_badge_and_related_points(self):
        discussion_item = self.item_ids["discussion"]
        decision_item = self.item_ids["decision"]
        decision_topic = self.record(
            "community.meeting.agenda.item", decision_item, ["topic_id"]
        )["topic_id"][0]
        self.rpc(
            "community.meeting.topic", "write",
            [[decision_topic], {"presenter_partner_id": False}],
        )
        user = self.rpc("res.users", "read", [[self.current_user()], ["partner_id"]])[0]
        partner_id, partner_name = user["partner_id"]
        self.rpc(
            "community.meeting.agenda.item", "write",
            [[discussion_item], {"priority": "2"}],
        )

        def make_outside_point(name):
            meeting = self.rpc(
                "community.meeting", "create",
                [{"name": "Outside relation %s" % uuid.uuid4().hex[:6]}],
            )
            self.addCleanup(self.rpc, "community.meeting", "unlink", [[meeting]])
            self.addCleanup(self.rpc, "community.meeting", "action_cancel", [[meeting]])
            item = self.rpc(
                "community.meeting.agenda.item", "create",
                [{
                    "meeting_id": meeting,
                    "name": name,
                    "kind": "discussion",
                    "agenda_type_id": self.rpc(
                        "community.meeting.agenda.type", "search",
                        [[("behavior", "=", "discussion"), ("active", "=", True)]],
                        {"limit": 1},
                    )[0],
                }],
            )
            return self.record("community.meeting.agenda.item", item, ["topic_id"])["topic_id"][0]

        outside_related = make_outside_point("Outside related point")
        outside_origin = make_outside_point("Outside origin point")
        self.rpc(
            "community.meeting.topic", "write",
            [[outside_related], {"description": "Background from the related point, with its own decision history."}],
        )
        discussion_topic = self.record(
            "community.meeting.agenda.item", discussion_item, ["topic_id"]
        )["topic_id"][0]
        action = self.rpc(
            "community.meeting.action", "create",
            [{
                "meeting_id": self.meeting_id,
                "agenda_item_id": discussion_item,
                "name": "Promoted origin follow-up",
                "description": "Prior follow-up discussion and owner context.",
            }],
        )
        activity_type = self.rpc(
            "mail.activity.type", "search",
            [[("active", "=", True)]], {"limit": 1, "order": "sequence, id"},
        )[0]
        self.rpc(
            "community.meeting.action", "write",
            [[action], {"followup_kind": "activity", "followup_activity_type_id": activity_type}],
        )
        self.rpc(
            "community.meeting.agenda.item", "write",
            [[discussion_item], {"presenter_partner_id": partner_id}],
        )
        self.rpc(
            "community.meeting.topic", "write",
            [[discussion_topic], {
                "related_topic_ids": [(6, 0, [decision_topic, outside_related])],
                "origin_topic_id": outside_origin,
                "origin_action_id": action,
            }],
        )

        self.page.reload(wait_until="domcontentloaded")
        self.page.locator(".o_live_agenda_card").first.wait_for()
        card = self.page.locator(".o_live_agenda_card").filter(
            has_text="Browser Discussion case"
        )
        badge = card.locator(".o_live_presenter_badge")
        expect(badge).to_contain_text(partner_name)
        expect(badge.locator("img")).to_have_attribute(
            "src", "/web/image/res.partner/%s/avatar_128" % partner_id
        )
        priority_badge = card.locator(".o_live_priority")
        type_badge = card.locator(".o_live_type_badge")
        outcome_badge = card.locator(".o_live_outcome_badge")
        self.assertLess(badge.bounding_box()["x"], priority_badge.bounding_box()["x"])
        self.assertLess(
            priority_badge.bounding_box()["x"], type_badge.bounding_box()["x"]
        )
        self.assertLess(type_badge.bounding_box()["x"], outcome_badge.bounding_box()["x"])

        expand = card.locator(".o_live_expand")
        if expand.get_attribute("aria-expanded") == "false":
            expand.click()
        relations = card.locator(".o_live_related_points")
        expect(relations).to_be_visible()
        expect(relations).to_contain_text("Browser Decision case")
        expect(relations).to_contain_text("Outside related point")
        expect(relations).to_contain_text("Outside origin point")
        expect(relations).to_contain_text("Promoted origin follow-up")

        outside_chip = relations.locator(
            ".o_live_related_point", has_text="Outside related point"
        )
        expect(outside_chip.first).to_have_js_property("tagName", "BUTTON")
        outside_chip.first.click()
        preview = relations.get_by_role(
            "region", name=self.ui_text("community_meetings", "Related") + ": Outside related point"
        )
        expect(preview).to_be_visible()
        expect(preview).to_contain_text("Background from the related point")
        expect(preview).to_contain_text(self.ui_text("community_meetings", "From meeting"))
        expect(preview.locator(".o_live_relation_source_title")).to_contain_text("Outside relation")
        expect(preview.locator(".o_live_relation_source_facts")).to_contain_text(self.ui_text("community_meetings", "Not set"))
        expect(preview.get_by_role("button", name=self.ui_text("community_meetings", "Open minutes"))).to_be_visible()
        origin_chip = relations.locator(
            ".o_live_related_point", has_text="Outside origin point"
        )
        expect(origin_chip.first).to_have_js_property("tagName", "BUTTON")
        followup_chip = relations.locator(
            ".o_live_related_point", has_text="Promoted origin follow-up"
        )
        followup_chip.click()
        followup_preview = relations.get_by_role(
            "region", name="Follow-up details: Promoted origin follow-up"
        )
        expect(followup_preview).to_contain_text("Prior follow-up discussion and owner context")
        expect(followup_preview.locator(".o_live_activity_preview")).to_contain_text(self.ui_text("community_meetings", "Odoo activities"))
        expect(followup_preview.locator(".o_live_activity_entry")).to_contain_text("Promoted origin follow-up")
        expect(followup_preview.locator(".o_live_activity_entry")).to_contain_text(
            self.rpc(
                "mail.activity.type",
                "read",
                [[activity_type], ["name"]],
                {"context": {"lang": self.effective_locale()}},
            )[0]["name"]
        )
        expect(followup_preview.get_by_role("button", name=self.ui_text("community_meetings", "Open activity"))).to_be_visible()
        followup_preview.get_by_role("button", name=self.ui_text("community_meetings", "Open activity")).click()
        activity_dialog = self.page.locator(".o_dialog").last
        expect(activity_dialog.locator('.o_field_widget[name="summary"] input')).to_have_value(
            "Promoted origin follow-up"
        )
        activity_dialog.get_by_role("button", name=self.ui_text("community_meetings_project", "Close")).click()
        expect(followup_preview).to_contain_text(self.ui_text("community_meetings", "From meeting"))
        expect(followup_preview.locator(".o_live_relation_source_heading").filter(has_text=self.ui_text("community_meetings", "From meeting"))).to_be_visible()
        expect(followup_preview.get_by_role("button", name=self.ui_text("community_meetings", "Open minutes"))).to_be_visible()
        relations.locator(
            ".o_live_related_point", has_text="Browser Decision case"
        ).first.click()
        decision_card = self.page.locator("#agenda-card-%s" % decision_item)
        expect(decision_card.locator(".o_live_expand")).to_have_attribute(
            "aria-expanded", "true"
        )
        expect(relations.get_by_role("region")).to_have_count(0)
        expect(decision_card.locator(".o_live_presenter_badge")).to_have_count(0)
        expect(decision_card.locator(".o_live_related_points")).to_have_count(0)

    def test_mobile_layout(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        try:
            main = self.page.locator("main.o_community_live_meeting")
            overflow = main.evaluate("el => ({width: el.clientWidth, scrollWidth: el.scrollWidth, offenders: [...el.querySelectorAll('*')].filter(x => x.scrollWidth > x.clientWidth + 2).map(x => ({tag: x.tagName, className: x.className, text: (x.innerText || '').slice(0, 80), width: x.clientWidth, scrollWidth: x.scrollWidth})).slice(0, 12)})")
            self.assertLessEqual(overflow["scrollWidth"] - overflow["width"], 1, overflow)
            self.card("information").get_by_role("button", name=self.ui_text("community_meetings", "Done")).click()
            expect(self.outcome("information")).to_have_text(self.ui_text("community_meetings", "Done"))
        finally:
            self.page.set_viewport_size({"width": 1440, "height": 1000})

    def test_focus_mode_presents_one_point_at_a_time(self):
        cards = self.page.locator(".o_live_agenda_card")
        expect(cards).to_have_count(4)
        focus = self.page.get_by_role("button", name=self.ui_text("community_meetings", "Focus on one point"))
        focus.click()
        agenda = self.page.locator(".o_live_agenda")
        expect(agenda).to_have_class(re.compile("o_live_focus_mode"))
        expect(cards).to_have_count(1)
        expect(cards.first).to_contain_text("Browser Information case")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Next agenda point")).click()
        expect(cards).to_have_count(1)
        expect(cards.first).to_contain_text("Browser Discussion case")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        cards.first.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        expect(cards.first.locator(".o_live_discussion_notes")).to_be_visible()
        expect(cards.first.get_by_role("button", name=self.ui_text("community_meetings", "Edit point options"))).to_be_visible()
        next_date = self.page.get_by_label(self.ui_text("community_meetings", "Next meeting date"), exact=True)
        if next_date.count():
            expect(next_date).to_be_disabled()
        footer = cards.first.locator(".o_live_point_footer")
        if footer.count():
            card_bottom = cards.first.evaluate("el => el.getBoundingClientRect().bottom")
            footer_bottom = footer.evaluate("el => el.getBoundingClientRect().bottom")
            self.assertLessEqual(footer_bottom, card_bottom + 1, "Focus card border must contain the point action footer")
        expect(cards.first.get_by_role("button", name=self.ui_text("community_meetings", "Enlarge editor"))).to_be_visible()
        expect(self.page.locator(".o_live_minutes")).to_be_hidden()
        self.page.set_viewport_size({"width": 390, "height": 844})
        main = self.page.locator("main.o_community_live_meeting")
        overflow = main.evaluate("el => ({width: el.clientWidth, scrollWidth: el.scrollWidth})")
        self.assertLessEqual(overflow["scrollWidth"] - overflow["width"], 1, overflow)
        self.page.set_viewport_size({"width": 1440, "height": 1000})
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Show full agenda")).click()
        expect(agenda).not_to_have_class(re.compile("o_live_focus_mode"))
        expect(cards).to_have_count(4)

    def test_discussion_notes_can_expand_and_description_stays_visible(self):
        discussion_id = self.item_ids["discussion"]
        self.rpc("community.meeting.agenda.item", "write", [[discussion_id], {
            "description": "<p>Background everyone should read before the discussion.</p>",
            "estimated_minutes": 25,
        }])
        self.page.reload(wait_until="domcontentloaded")
        card = self.card("discussion")
        description = card.locator(".o_live_planned")
        expect(description).to_be_visible()
        expect(description).to_contain_text("Background everyone should read")
        expect(card.locator(".o_live_estimate_badge")).to_contain_text("Est. 25 min")
        self.assertEqual(description.locator("details, summary").count(), 0)
        card.locator(".o_live_expand").click()
        expect(card.locator(".o_live_expand")).to_have_attribute("aria-expanded", "false")
        expect(description).to_be_visible()
        card.locator(".o_live_expand").click()
        editor = card.locator(".o_live_richtext")
        expect(editor.locator('[contenteditable="true"]')).to_be_visible()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Enlarge editor")).click()
        expect(editor).to_have_class(re.compile("o_live_richtext_expanded"))
        self.assertGreaterEqual(editor.bounding_box()["height"], 300)
        card.get_by_role("button", name=self.ui_text("community_meetings", "Reduce editor")).click()
        expect(editor).not_to_have_class(re.compile("o_live_richtext_expanded"))

    def test_next_meeting_datetime_is_primary_in_agenda(self):
        next_meeting_type = self.rpc(
            "community.meeting.agenda.type", "search",
            [[("behavior", "=", "next_meeting"), ("active", "=", True)]],
            {"limit": 1},
        )[0]
        self.rpc("community.meeting.agenda.item", "create", [{
            "meeting_id": self.meeting_id,
            "name": "Browser Next Meeting case",
            "agenda_type_id": next_meeting_type,
            "sequence": 99,
            "next_meeting_datetime": "2027-04-12 10:30:00",
            "estimated_minutes": 15,
        }])
        self.page.reload(wait_until="domcontentloaded")
        card = self.page.locator(".o_live_agenda_card").filter(
            has_text="Browser Next Meeting case"
        )
        feature = card.locator(".o_live_next_meeting_feature")
        expect(feature).to_be_visible()
        expect(feature.get_by_label(self.ui_text("community_meetings", "Next meeting date"))).to_be_visible()
        expect(feature.get_by_label(self.ui_text("community_meetings", "Next meeting date"))).to_be_disabled()
        expect(card.locator(".o_live_estimate_badge")).to_contain_text("Est. 15 min")
        self.assertEqual(
            card.locator(".o_live_card_header").evaluate(
                "el => el.nextElementSibling?.classList.contains('o_live_next_meeting_feature')"
            ),
            True,
        )
        card.locator(".o_live_expand").click()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Focus on one point")).click()
        focused = self.page.locator(".o_live_agenda_card")
        expect(focused).to_have_count(1)
        expect(focused.locator(".o_live_next_meeting_feature")).to_be_visible()
        next_date = focused.get_by_label(self.ui_text("community_meetings", "Next meeting date"))
        expect(next_date).to_be_visible()
        if self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting"), exact=True).count():
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting"), exact=True).click()
            expect(next_date).to_be_disabled()
            focused.get_by_role("button", name=self.ui_text("community_meetings", "Begin point"), exact=True).click()
            expect(next_date).to_be_enabled()
            focused.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"), exact=True).click()
            expect(next_date).to_be_disabled()
            focused.get_by_role("button", name=self.ui_text("community_meetings", "Resume point"), exact=True).click()
            expect(next_date).to_be_enabled()

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
        schedule_heading = self.page.locator(
            ".o_horizontal_separator",
            has_text=re.compile("When and where|Cuándo y dónde", re.IGNORECASE),
        )
        people_heading = self.page.locator(
            ".o_horizontal_separator",
            has_text=re.compile("People and series|Personas y serie", re.IGNORECASE),
        )
        expect(schedule_heading).to_be_visible()
        expect(people_heading).to_be_visible()
        schedule_box = schedule_heading.bounding_box()
        people_box = people_heading.bounding_box()
        self.assertLess(
            abs(schedule_box["y"] - people_box["y"]),
            100,
            "Schedule and people should share the desktop identity row.",
        )
        self.capture_visual_screenshot("meeting-form-desktop")
        # The half-width desktop viewport exercises the reflow expected at
        # 200% zoom on a 1440px display while keeping the test deterministic.
        self.page.set_viewport_size({"width": 720, "height": 900})
        zoomed = self.page.locator(".o_form_view").evaluate(
            "el => ({width: el.clientWidth, scrollWidth: el.scrollWidth})"
        )
        self.assertLessEqual(zoomed["scrollWidth"] - zoomed["width"], 1, zoomed)
        self.page.set_viewport_size({"width": 390, "height": 844})
        responsive = self.page.locator(".o_form_view").evaluate(
            "el => ({width: el.clientWidth, scrollWidth: el.scrollWidth})"
        )
        self.assertLessEqual(
            responsive["scrollWidth"] - responsive["width"],
            1,
            responsive,
        )
        self.capture_visual_screenshot("meeting-form-mobile")
        self.page.set_viewport_size({"width": 1440, "height": 900})
        self.page.locator('.o_field_widget[name="location"] input').fill("Browser room")
        self.page.get_by_role(
            "button", name=re.compile("^(Schedule|Programar)$", re.IGNORECASE)
        ).click()
        deadline = time.monotonic() + 30
        record = self.record("community.meeting", draft, ["location", "state"])
        while record["state"] != "scheduled" and time.monotonic() < deadline:
            self.page.wait_for_timeout(250)
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
        for title in ("Created agenda title", "Second agenda title"):
            wizard.locator('button[name="action_add_point"]').click()
            point = self.page.get_by_role("dialog").last
            point.locator('.o_field_widget[name="name"] input').fill(title)
            point.locator('button[name="action_save"]').click()
            wizard = self.page.get_by_role("dialog").last
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
            {"fields": ["name"], "order": "sequence,id"},
        )
        self.assertEqual(
            [i["name"] for i in items],
            ["Created agenda title", "Second agenda title"],
        )
        agenda_tab = self.page.get_by_role(
            "tab", name=self.ui_text("community_meetings", "Agenda"), exact=True
        )
        if agenda_tab.count():
            agenda_tab.click()
        agenda_rows = self.page.locator(
            '.o_field_widget[name="agenda_item_ids"] tr.o_data_row'
        )
        expect(agenda_rows).to_have_count(2)
        move_down = agenda_rows.nth(0).get_by_role(
            "button", name=self.ui_text("community_meetings", "Move down")
        )
        move_down_box = move_down.bounding_box()
        name_cell = agenda_rows.nth(0).get_by_role("cell").filter(
            has_text="Created agenda title"
        )
        name_box = name_cell.bounding_box()
        self.assertIsNotNone(move_down_box)
        self.assertIsNotNone(name_box)
        self.assertLessEqual(
            move_down_box["x"] + move_down_box["width"],
            name_box["x"],
            "The move control overlaps the agenda point name.",
        )
        move_down.click()
        expect(agenda_rows.nth(0)).to_contain_text("Second agenda title")
        persisted_order = self.rpc(
            "community.meeting.agenda.item",
            "search_read",
            [[("meeting_id", "=", rows[0])]],
            {"fields": ["name"], "order": "sequence,id"},
        )
        self.assertEqual(
            [item["name"] for item in persisted_order],
            ["Second agenda title", "Created agenda title"],
        )

    def test_series_creation(self):
        name = "Browser series " + uuid.uuid4().hex[:8]
        self.page.goto(
            BASE_URL + "/odoo/action-community_meetings.action_community_meeting_series"
        )
        self.page.locator(".o_list_button_add").click()
        series_wizard = self.page.get_by_role("dialog").last
        self.capture_visual_screenshot("series-wizard")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.capture_visual_screenshot("series-wizard", {"width": 390, "height": 844})
        self.assertLessEqual(
            series_wizard.evaluate("el => el.scrollWidth - el.clientWidth"),
            1,
        )
        self.page.set_viewport_size({"width": 1440, "height": 900})
        series_wizard.locator('.o_field_widget[name="name"] input').fill(name)
        for step in range(3):
            series_wizard.locator('button[name="action_next"]').click()
            self.capture_visual_screenshot(f"series-wizard-step-{step + 2}")
        series_wizard.locator('button[name="action_finish"]').click()
        expect(series_wizard).not_to_be_visible()
        rows = self.rpc("community.meeting.series", "search", [[("name", "=", name)]])
        self.assertEqual(len(rows), 1)
        wizard_save_errors = []

        def has_wizard_endpoint(response, method):
            return response.url.split("?", 1)[0].endswith(
                f"/community.meeting.create.wizard/{method}"
            )

        def capture_wizard_save_error(response):
            if not has_wizard_endpoint(response, "web_save"):
                return
            try:
                payload = response.json()
            except ValueError as error:
                wizard_save_errors.append(
                    f"web_save returned invalid JSON (HTTP {response.status}): {error}"
                )
                return
            if response.status >= 400 or payload.get("error"):
                wizard_save_errors.append(
                    f"web_save failed (HTTP {response.status}): {payload!r}"
                )

        self.page.on("response", capture_wizard_save_error)
        self.addCleanup(
            self.page.remove_listener, "response", capture_wizard_save_error
        )
        self.addCleanup(
            lambda: self.assertFalse(
                wizard_save_errors,
                "Meeting wizard save errors: " + repr(wizard_save_errors),
            )
        )
        self.addCleanup(self.rpc, "community.meeting.series", "unlink", [rows])
        # Wait until Odoo has loaded and initialized the wizard before closing it.
        # The response listener above catches any unexpected deferred web_save.
        with self.page.expect_response(
            lambda response: has_wizard_endpoint(response, "onchange")
        ):
            self.page.locator('button[name="action_new_meeting"]').click()
        meeting_wizard = self.page.get_by_role("dialog").last
        expect(
            meeting_wizard.locator('.o_field_widget[name="series_id"] input')
        ).to_have_value(name)
        meeting_wizard.get_by_role(
            "button", name=self.ui_text("community_meetings", "Cancel")
        ).click()
        expect(meeting_wizard).not_to_be_visible()

    def test_mobile_new_meeting_wizard_with_many_attendees(self):
        suffix = uuid.uuid4().hex[:8]
        attendee_values = self.rpc(
            "res.partner", "search_read", [[]], {"fields": ["name"], "limit": 5}
        )
        attendee_ids = [row["id"] for row in attendee_values]
        self.assertEqual(len(attendee_ids), 5, "The disposable DB needs five readable contacts.")
        series_id = self.rpc(
            "community.meeting.series",
            "create",
            [{
                "name": "Long attendee series " + suffix,
                "attendee_partner_ids": [(6, 0, attendee_ids)],
            }],
        )
        self.addCleanup(self.rpc, "community.meeting.series", "unlink", [[series_id]])
        self.page.goto(
            "%s/web#model=community.meeting.series&id=%s&view_type=form"
            % (BASE_URL, series_id)
        )
        self.page.locator('button[name="action_new_meeting"]').click()
        wizard = self.page.get_by_role("dialog").last
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.addCleanup(
            self.page.set_viewport_size, {"width": 1440, "height": 1000}
        )
        self.capture_visual_screenshot(
            "new-meeting-many-attendees-start", {"width": 390, "height": 844}
        )
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('.o_field_widget[name="name"] input').fill(
            "Quarterly planning and follow-up review " + "long agenda title " * 4
        )
        self.assertLessEqual(wizard.evaluate("el => el.scrollWidth - el.clientWidth"), 1)
        wizard.locator('button[name="action_next"]').click()
        attendee_field = wizard.locator('.o_field_widget[name="attendee_partner_ids"]')
        expect(attendee_field).to_contain_text(attendee_values[0]["name"])
        expect(attendee_field).to_contain_text(attendee_values[-1]["name"])
        self.assertLessEqual(wizard.evaluate("el => el.scrollWidth - el.clientWidth"), 1)
        self.capture_visual_screenshot(
            "new-meeting-attendee-selection", {"width": 390, "height": 844}
        )
        next_button = wizard.locator('button[name="action_next"]')
        next_button.scroll_into_view_if_needed()
        self.capture_visual_screenshot(
            "new-meeting-attendee-selection-footer", {"width": 390, "height": 844}
        )
        button_box = next_button.bounding_box()
        self.assertGreaterEqual(button_box["y"], 0, button_box)
        self.assertLessEqual(button_box["y"] + button_box["height"], 844, button_box)

    def test_recurring_agenda_template_selection_and_lineage(self):
        suffix = uuid.uuid4().hex[:8]
        series_name = "Browser recurring " + suffix
        template_name = "Recurring review " + suffix
        series_id = self.rpc("community.meeting.series", "create", [{"name": series_name}])
        self.retained.append({"model": "community.meeting.series", "id": series_id})
        self.page.goto(
            "%s/web#model=community.meeting.series&id=%s&view_type=form"
            % (BASE_URL, series_id)
        )
        self.page.get_by_role(
            "tab", name=self.ui_text("community_meetings", "Recurring agenda")
        ).click()
        template_list = self.page.locator(
            '.o_field_widget[name="recurring_point_ids"]'
        )
        template_list.locator(".o_field_x2many_list_row_add a").click()
        new_row = template_list.locator("tr.o_data_row").last
        name_cell = new_row.locator('td[name="name"]')
        name_cell.click()
        name_input = name_cell.locator("input")
        name_input.fill(template_name)
        expect(name_input).to_have_value(template_name)
        name_input.press("Tab")
        self.page.locator(".o_form_button_save").click()
        template_row = template_list.locator("tr.o_data_row").filter(
            has_text=template_name
        )
        expect(template_row).to_be_visible()
        reorderable_toggle = template_row.locator(
            '.o_field_widget[name="reorderable"] input[type="checkbox"]'
        )
        self.assertEqual(
            reorderable_toggle.count(),
            1,
            "Could not identify the recurring-point toggle in the rendered row: "
            + template_row.evaluate("el => el.outerHTML"),
        )
        expect(reorderable_toggle).to_be_checked()
        reorderable_toggle.click()
        expect(reorderable_toggle).not_to_be_checked()
        self.page.locator(".o_form_button_save").click()
        self.capture_visual_screenshot("series-form-recurring-template")
        template_ids = self.rpc(
            "community.meeting.series.agenda.template", "search",
            [[("series_id", "=", series_id), ("name", "=", template_name)]],
        )
        self.assertEqual(len(template_ids), 1)
        template_values = self.rpc(
            "community.meeting.series.agenda.template", "write",
            [template_ids, {"estimated_minutes": 12}],
        )
        self.assertTrue(template_values)
        template_values = self.rpc(
            "community.meeting.series.agenda.template", "read",
            [template_ids, ["reorderable"]],
        )
        self.assertFalse(template_values[0]["reorderable"])

        def create_meeting(title, start, include):
            self.page.goto(
                "%s/web#model=community.meeting.series&id=%s&view_type=form"
                % (BASE_URL, series_id)
            )
            self.page.locator('button[name="action_new_meeting"]').click()
            wizard = self.page.get_by_role("dialog").last
            wizard.locator('button[name="action_next"]').click()
            wizard.locator('.o_field_widget[name="name"] input').fill(title)
            wizard.locator('.o_field_widget[name="start_datetime"] input').fill(start)
            wizard.locator('button[name="action_next"]').click()
            wizard.locator('button[name="action_next"]').click()
            wizard.locator('button[name="action_next"]').click()
            row = wizard.locator(
                '.o_field_widget[name="recurring_line_ids"] tr.o_data_row'
            ).filter(has_text=template_name)
            expect(row).to_be_visible()
            toggle = row.locator('input[type="checkbox"]')
            expect(toggle).to_be_checked()
            if not include:
                toggle.uncheck()
                expect(toggle).not_to_be_checked()
            wizard.locator('button[name="action_next"]').click()
            summary = wizard.locator('.o_field_widget[name="review_summary"]')
            if include:
                expect(summary).to_contain_text(template_name)
            else:
                expect(summary).not_to_contain_text(template_name)
            wizard.locator('button[name="action_finish"]').click()
            expect(wizard).not_to_be_visible(timeout=30000)
            ids = self.rpc(
                "community.meeting", "search",
                [[("series_id", "=", series_id), ("name", "=", title)]],
            )
            self.assertEqual(len(ids), 1)
            self.retained.append({"model": "community.meeting", "id": ids[0]})
            return ids[0]

        first_meeting = create_meeting(
            series_name + " first", "11/02/2026 10:00:00", True
        )
        skipped_meeting = create_meeting(
            series_name + " skipped", "11/09/2026 10:00:00", False
        )
        later_meeting = create_meeting(
            series_name + " later", "11/16/2026 10:00:00", True
        )

        for meeting_id in (first_meeting, later_meeting):
            occurrence_values = self.rpc(
                "community.meeting.agenda.item", "search_read",
                [[("meeting_id", "=", meeting_id), ("name", "=", template_name)]],
                {"fields": ["reorderable"]},
            )
            self.assertEqual(len(occurrence_values), 1)
            self.assertFalse(occurrence_values[0]["reorderable"])

        self.page.goto(
            "%s/web#model=community.meeting&id=%s&view_type=form"
            % (BASE_URL, first_meeting)
        )
        agenda_tab_name = self.ui_text("community_meetings", "Agenda")
        agenda_tab = self.page.get_by_role("tab", name=agenda_tab_name, exact=True)
        if agenda_tab.count():
            agenda_tab.click()
        occurrence_row = self.page.locator(
            '.o_field_widget[name="agenda_item_ids"] tr.o_data_row'
        ).filter(has_text=template_name)
        expect(occurrence_row).to_be_visible()
        move_up_name = self.ui_text("community_meetings", "Move up")
        move_down_name = self.ui_text("community_meetings", "Move down")
        expect(occurrence_row.get_by_role("button", name=move_up_name)).to_have_count(0)
        expect(occurrence_row.get_by_role("button", name=move_down_name)).to_have_count(0)

        def recurring_topic(meeting_id):
            item_ids = self.rpc(
                "community.meeting.agenda.item", "search",
                [[("meeting_id", "=", meeting_id)]],
            )
            if not item_ids:
                return False
            topic_ids = self.rpc(
                "community.meeting.agenda.item", "search_read",
                [[("id", "in", item_ids)]], {"fields": ["topic_id"]},
            )
            ids = [row["topic_id"][0] for row in topic_ids if row["topic_id"]]
            topics = self.rpc(
                "community.meeting.topic", "search_read",
                [[("id", "in", ids), ("recurring_template_id", "!=", False)]],
                {"fields": ["id", "previous_occurrence_id"]},
            )
            return topics[0] if topics else False

        first_topic = recurring_topic(first_meeting)
        self.assertTrue(first_topic)
        self.assertFalse(recurring_topic(skipped_meeting))
        later_topic = recurring_topic(later_meeting)
        self.assertTrue(later_topic)
        self.assertEqual(later_topic["previous_occurrence_id"][0], first_topic["id"])

        self.rpc("community.meeting", "action_schedule", [[later_meeting]])
        self.page.goto(
            "%s/web#model=community.meeting&id=%s&view_type=form"
            % (BASE_URL, later_meeting)
        )
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Open Meeting")
        ).click()
        card = self.page.locator(".o_live_agenda_card").filter(has_text=template_name)
        expect(card).to_contain_text(
            self.ui_text("community_meetings", "Previous occurrence")
        )

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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).click()
        card.get_by_label(self.ui_text("community_meetings", "Reason for postponing")).fill("Review next week")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Move to another meeting series")).click()
        dialog = self.page.get_by_role("dialog")
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Request Move"), exact=True).click()
        expect(dialog).not_to_be_visible()
        transfers = self.rpc(
            "community.meeting.carryover",
            "search_read",
            [[("origin_agenda_item_id", "=", self.item_ids["discussion"])]],
            {"fields": ["status"]},
        )
        self.assertEqual(len(transfers), 1)
        expect(self.outcome("discussion")).to_have_text(self.ui_text("community_meetings", "Postponed"))
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
        self.page.get_by_role("tab", name=self.ui_text("community_meetings", "Incoming Carryovers")).click()
        incoming = self.page.locator('.o_field_widget[name="incoming_carryover_ids"]')
        row = incoming.locator("tr.o_data_row").filter(
            has_text="Browser Discussion case"
        )
        row.locator('button[name="action_accept"]').click()
        expect(row).to_contain_text(self.ui_text("community_meetings", "Accepted"))
        other = incoming.locator("tr.o_data_row").filter(
            has_text="Browser Information case"
        )
        other.locator('button[name="action_dismiss"]').click()
        expect(other).to_contain_text(self.ui_text("community_meetings", "Dismissed"))
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
        self.capture_visual_screenshot("new-meeting-wizard")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.capture_visual_screenshot(
            "new-meeting-wizard", {"width": 390, "height": 844}
        )
        self.assertLessEqual(wizard.evaluate("el => el.scrollWidth - el.clientWidth"), 1)
        self.page.set_viewport_size({"width": 1440, "height": 1000})
        expect(wizard.locator('.o_field_widget[name="series_id"] input')).to_have_value(
            re.compile("Guided series")
        )
        wizard.locator('button[name="action_next"]').click()
        self.capture_visual_screenshot("new-meeting-when")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.capture_visual_screenshot("new-meeting-when", {"width": 390, "height": 844})
        self.assertLessEqual(wizard.evaluate("el => el.scrollWidth - el.clientWidth"), 1)
        self.page.set_viewport_size({"width": 1440, "height": 1000})
        expect(
            wizard.get_by_text(self.ui_text("community_meetings", "Estimated Start Datetime"), exact=True)
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
                self.ui_text("community_meetings", "There are no points to carry forward into this meeting."), exact=True
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
        decision_type = point.get_by_role(
            "radio",
            name=re.compile("^" + re.escape(self.ui_text("community_meetings", "Decision"))),
        )
        decision_type.click()
        expect(
            decision_type
        ).to_have_attribute("aria-checked", "true")
        decision_type.focus()
        decision_type.press("ArrowRight")
        todo_type = point.get_by_role(
            "radio",
            name=re.compile("^" + re.escape(self.ui_text("community_meetings", "TODO"))),
        )
        expect(todo_type).to_have_attribute("aria-checked", "true")
        decision_type.click()
        point.get_by_role(
            "radio",
            name=re.compile("^" + re.escape(self.ui_text("community_meetings", "Critical"))),
        ).click()
        expect(
            point.get_by_role("spinbutton", name=self.ui_text("community_meetings", "Custom estimate in minutes"))
        ).to_be_visible()
        point.get_by_role("spinbutton", name=self.ui_text("community_meetings", "Custom estimate in minutes")).fill("20")
        point.locator('.o_field_widget[name="deadline"] input').fill(
            self.localized_date("2026-12-20")
        )
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
                    "kind",
                    "description",
                    "priority",
                    "estimated_minutes",
                    "deadline",
                    "topic_id",
                ]
            },
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "decision")
        self.assertEqual(
            (items[0]["priority"], items[0]["estimated_minutes"], items[0]["deadline"]),
            ("3", 20, "2026-12-20"),
        )
        self.assertIn("Background", items[0]["description"])
        self.rpc("community.meeting", "action_schedule", [[meeting_id]])
        self.open_live(meeting_id)
        expect(self.page.locator(".o_live_priority_3")).to_have_attribute(
            "aria-label", self.ui_text("community_meetings", "Critical")
        )
        expect(self.page.locator(".o_live_estimate_badge")).to_contain_text("Est. 20 min")
        expect(self.page.locator(".o_live_planned")).to_contain_text("Background")

    def test_guided_meeting_uses_agreed_date_when_selecting_series(self):
        series_name = "Agreed guided date " + uuid.uuid4().hex[:8]
        series = self.rpc("community.meeting.series", "create", [{
            "name": series_name, "has_next_meeting_point": True,
        }])
        self.retained.append({"model": "community.meeting.series", "id": series})
        previous = self.rpc("community.meeting", "create", [{
            "name": series_name + " previous", "series_id": series,
            "start_datetime": "2030-04-01 10:00:00",
        }])
        self.retained.append({"model": "community.meeting", "id": previous})
        next_point = self.rpc("community.meeting.agenda.item", "search", [[
            ("meeting_id", "=", previous), ("kind", "=", "next_meeting"),
        ]])[0]
        self.rpc("community.meeting.agenda.item", "write", [[next_point], {
            "next_meeting_datetime": "2030-04-15 17:30:00",
        }])

        self.page.goto(BASE_URL + "/web")
        self.page.locator(".o_navbar_apps_menu").click()
        self.page.locator(
            'a[data-menu-xmlid="community_meetings.menu_community_meetings_root"]'
        ).click()
        self.page.locator(
            'a[data-menu-xmlid="community_meetings.menu_prepare_meeting"]'
        ).click()
        wizard = self.page.get_by_role("dialog").last
        series_input = wizard.locator('.o_field_widget[name="series_id"] input')
        series_input.fill(series_name)
        option = self.page.locator(".o-autocomplete--dropdown-item").filter(
            has_text=series_name
        ).first
        expect(option).to_be_visible()
        option.click()
        expect(series_input).to_have_value(series_name)
        wizard.locator('button[name="action_next"]').click()
        expect(
            wizard.locator('.o_field_widget[name="start_datetime"] input')
        ).to_have_value(re.compile(r"(?:04/15/2030|15/04/2030)"))

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
            self.localized_datetime("10/08/2026 10:00")
        )
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        self.capture_visual_screenshot("new-meeting-carryovers")
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
            self.localized_datetime("10/08/2026 10:00")
        )
        wizard.locator('button[name="action_next"]').click()
        wizard.locator('button[name="action_next"]').click()
        row = wizard.locator(
            '.o_field_widget[name="carry_line_ids"] tr.o_data_row'
        ).filter(has_text=source_name)
        expect(row).to_be_visible()
        expect(
            row.get_by_role("button", name=self.ui_text("community_meetings", "Accept"), exact=True)
        ).to_have_class(re.compile(r"(?:^|\s)is-selected(?:\s|$)"))
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True).click()
        dialog = self.page.get_by_role("dialog").last
        dialog.locator('.o_field_widget[name="name"] input').fill(
            "Cancelled point draft"
        )
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Cancel"), exact=True).click()
        expect(dialog).not_to_be_visible()
        self.assertEqual(
            self.rpc(
                "community.meeting.agenda.item",
                "search_count",
                [[("meeting_id", "=", self.meeting_id)]],
            ),
            before,
        )
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True).click()
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

    def test_live_draft_meeting_can_be_scheduled_and_cancelled(self):
        meeting_id = self.rpc(
            "community.meeting",
            "create",
            [{"name": "Browser lifecycle " + uuid.uuid4().hex[:8], "start_datetime": "2030-01-01 10:00:00"}],
        )

        def cleanup_meeting():
            state = self.record("community.meeting", meeting_id, ["state"])["state"]
            if state in ("draft", "scheduled"):
                self.rpc("community.meeting", "action_cancel", [[meeting_id]])
            self.rpc("community.meeting", "unlink", [[meeting_id]])

        self.addCleanup(cleanup_meeting)
        self.open_live(meeting_id)
        schedule = self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Schedule Meeting"), exact=True
        )
        expect(schedule).to_be_visible()
        schedule.click()
        self.wait_field("community.meeting", meeting_id, "state", "scheduled")
        cancel = self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Cancel Meeting"), exact=True
        )
        expect(cancel).to_be_visible()
        cancel.click()
        dialog = self.page.get_by_role("dialog")
        expect(dialog).to_contain_text(
            self.ui_text("community_meetings", "This meeting will be marked as cancelled.")
        )
        dialog.get_by_role(
            "button", name=self.ui_text("community_meetings", "Cancel meeting"), exact=True
        ).click()
        self.wait_field("community.meeting", meeting_id, "state", "cancelled")
        expect(
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Schedule Meeting"), exact=True)
        ).to_have_count(0)

    def test_live_view_is_available_in_draft_and_respects_add_policy(self):
        series = self.rpc(
            "community.meeting.series",
            "create",
            [{"name": "Browser draft-only " + uuid.uuid4().hex[:8], "add_point_policy": "draft"}],
        )
        self.rpc("community.meeting", "write", [[self.meeting_id], {"series_id": series}])
        self.open_form()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True)).to_have_count(0)

        draft = self.rpc("community.meeting", "create", [{
            "name": "Draft workspace " + uuid.uuid4().hex[:8],
            "start_datetime": "2030-01-01 10:00:00",
        }])
        self.addCleanup(self.delete_draft, draft)
        self.rpc(
            "community.meeting.agenda.item",
            "create",
            [{"meeting_id": draft, "name": "Draft reorder point one"}],
        )
        self.rpc(
            "community.meeting.agenda.item",
            "create",
            [{"meeting_id": draft, "name": "Draft reorder point two"}],
        )
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, draft))
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        expect(self.page.locator(self.ui_selector("community_meetings", '.o_live_header input[aria-label="Meeting name"]', "Meeting name"))).to_have_value(re.compile("Draft workspace"))
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True)).to_be_visible()
        reorder_toggle = self.page.locator(".o_live_reorder_mode_toggle")
        expect(reorder_toggle).to_be_visible()
        expect(self.page.locator(".o_live_reorder_rail")).to_have_count(0)
        reorder_toggle.click()
        expect(reorder_toggle).to_have_attribute("aria-pressed", "true")
        expect(self.page.locator(".o_live_reorder_rail").first).to_be_visible()
        reorder_toggle.click()
        expect(self.page.locator(".o_live_reorder_rail")).to_have_count(0)

    def test_live_header_shows_coordinator_before_minutes_secretary(self):
        self.open_live(self.meeting_id)
        header = self.page.locator(".o_live_header_primary")
        coordinator = header.locator(".o_live_header_coordinator")
        secretary = header.locator(".o_live_header_secretary")
        expect(coordinator).to_be_visible()
        expect(secretary).to_be_visible()
        self.assertLess(
            coordinator.evaluate("element => [...element.parentElement.children].indexOf(element)"),
            secretary.evaluate("element => [...element.parentElement.children].indexOf(element)"),
        )
        self.assertTrue(coordinator.inner_text().strip())

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
        expect(dialog).to_contain_text(self.ui_text("community_meetings", "New Meeting"))
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Cancel")).click()
        expect(dialog).not_to_be_visible()

    def test_followup_activity_uses_configured_activity_type(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Native meeting follow-up")
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up")).click()
        expect(form).to_have_count(0)
        row = card.locator(self.ui_selector("community_meetings", 'li:has(select[aria-label="Task status"])', "Task status")).last
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

        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        expect(form).to_be_visible()
        form.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Odoo call activity")
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
        form.get_by_label(self.ui_text("community_meetings", "Activity type")).select_option(str(activity_type))
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up")).click()
        record = self.wait_action_record("Odoo call activity")
        activity_row = card.locator("li").filter(has_text="Odoo call activity")
        expect(activity_row.get_by_role("button", name=self.ui_text("community_meetings_project", "Create Project task"))).to_have_count(0)
        self.assertEqual(record["agenda_item_id"][0], self.item_ids["discussion"])
        self.assertEqual(record["followup_kind"], "activity")
        self.assertTrue(record["followup_activity_id"])
        self.assertEqual(
            self.record(
                "mail.activity", record["followup_activity_id"][0], ["activity_type_id"]
            )["activity_type_id"][0],
            activity_type,
        )

        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        expect(form).to_be_visible()
        form.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Native Odoo to-do")
        native_todo = self.rpc(
            "mail.activity.type",
            "search_read",
            [[("name", "=", "To-Do")]],
            {"fields": ["id"], "limit": 1},
        )
        self.assertTrue(native_todo, "The native Odoo To-Do type must be installed")
        form.get_by_label(self.ui_text("community_meetings", "Activity type")).select_option(str(native_todo[0]["id"]))
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up")).click()
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
        card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).click()
        card.get_by_label(self.ui_text("community_meetings", "Reason for postponing")).fill("Continue this point next time")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Leave postponed"), exact=True).click()
        expect(self.outcome("discussion")).to_have_text(self.ui_text("community_meetings", "Postponed"))
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
            "aria-label", self.ui_text("community_meetings", "High")
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
        inbox = self.page.get_by_role("region", name=self.ui_text("community_meetings", "Points to continue"))
        expect(inbox).to_be_visible()
        discussion = inbox.locator("div.mb-2").filter(
            has_text="Browser Discussion case"
        )
        discussion.get_by_role("button", name=self.ui_text("community_meetings", "Accept"), exact=True).click()
        expect(self.card("discussion")).to_be_visible()
        information = inbox.locator("div.mb-2").filter(
            has_text="Browser Information case"
        )
        information.get_by_role("button", name=self.ui_text("community_meetings", "Dismiss"), exact=True).click()
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
        agreement_title = (
            "Aprobar el calendario revisado del proyecto"
            if os.environ.get("MM_CAPTURE_LANGUAGE") == "es_ES"
            else "Approve the revised project timeline"
        )
        agreement_body = (
            "Se aprueba el calendario revisado, dejando constancia de los riesgos de entrega y del disenso expuesto."
            if os.environ.get("MM_CAPTURE_LANGUAGE") == "es_ES"
            else "The revised timeline is approved, with the delivery risks and dissent recorded above."
        )
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        card.get_by_placeholder(self.ui_text("community_meetings", "Agreement title")).fill(
            agreement_title
        )
        card.get_by_placeholder(self.ui_text("community_meetings", "What was agreed?")).fill(
            agreement_body
        )
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Approved"))
        private = (
            self.card("discussion")
            .locator("details")
            .filter(has_text=self.ui_text("community_meetings", "Private editorial notes"))
        )
        private.locator("summary").click()
        private.get_by_role("button", name=self.ui_text("community_meetings", "Add private note"), exact=True).click()
        private.get_by_label(self.ui_text("community_meetings", "Private editorial note"), exact=True).fill(
            "PRIVATE_NOT_FOR_PUBLICATION"
        )
        private.get_by_role("button", name=self.ui_text("community_meetings", "Add private note"), exact=True).click()
        expect(private.locator(".o_live_rich_readonly")).to_contain_text(
            "PRIVATE_NOT_FOR_PUBLICATION"
        )
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"), exact=True).click()
        self.page.get_by_role("dialog").get_by_role("button", name=self.ui_text("community_meetings", "Finish meeting"), exact=True).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Prepare Minutes"), exact=True)).to_be_visible()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Prepare Minutes"), exact=True).click()
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
        self.assertIn(agreement_title, snapshot["snapshot_json"])
        if os.environ.get("MM_CAPTURE_MINUTES_PREVIEW"):
            public_snapshot = json.loads(snapshot["snapshot_json"])
            self.assertGreaterEqual(len(public_snapshot["dissents"]), 2)
            self.assertGreaterEqual(len(public_snapshot["actions"]), 2)
            resolutions = [
                resolution
                for item in public_snapshot["agenda"]
                for resolution in item["resolutions"]
            ]
            self.assertGreaterEqual(len(resolutions), 4)
            discussion_label = (
                "Calendario:"
                if os.environ.get("MM_CAPTURE_FIXTURE_LANGUAGE", self.effective_locale())
                .lower()
                .startswith("es")
                else "Schedule:"
            )
            self.assertTrue(
                any(
                    discussion_label in item["discussion"]
                    for item in public_snapshot["agenda"]
                )
            )
            self.assertTrue(
                any(
                    "contingency" in resolution["body"].lower()
                    or "contingencia" in resolution["body"].lower()
                    for resolution in resolutions
                )
            )
        self.page.locator('button[name="action_view_approved_minutes"]').click()
        expect(self.page.locator(".o_community_minutes_preview_body .o_meeting_minutes_document")).to_be_visible()
        self.capture_visual_screenshot("approved-minutes-html-report")
        self.page.locator(".o_minutes_preview_back").click()
        expect(self.page.locator('button[name="action_view_approved_minutes"]')).to_be_visible()
        self.page.get_by_role("tab", name=self.ui_text("community_meetings", "Approved Revisions")).click()
        with self.page.expect_download(timeout=30000) as downloaded:
            self.page.locator('.o_field_widget[name="revision_ids"] button').filter(
                has_text=self.ui_text("community_meetings", "PDF")
            ).click()
        download = downloaded.value
        pdf = Path(download.path()).read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF"))
        artifact_dir = Path(os.environ.get("PLAYWRIGHT_ARTIFACTS", "/tmp/meeting-playwright"))
        artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        pdf_artifact = artifact_dir / f"approved-minutes-report-{self.meeting_id}.pdf"
        download.save_as(str(pdf_artifact))
        pdf_artifact.chmod(0o600)
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
            self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes")
        )
        self.edit_rich(editor, "Unsaved text must survive an error")
        expect(self.page.get_by_role("alert").filter(has_text=self.ui_text("community_meetings", "Some changes could not be saved."))).to_be_visible()
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
        try:
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True).click()
            dialog = self.page.get_by_role("dialog").last
            expect(dialog).to_be_visible()
            self.capture_visual_screenshot("add-point-wizard")
            self.assertEqual(dialog.get_attribute("role"), "dialog")
            self.page.set_viewport_size({"width": 390, "height": 844})
            expect(dialog).to_be_visible()
            self.capture_visual_screenshot(
                "add-point-wizard", {"width": 390, "height": 844}
            )
            title = dialog.locator('.o_field_widget[name="name"] input')
            title.click()
            title.press_sequentially("Keyboard-only draft " + "long agenda text " * 12)
            title.press("Tab")
            self.assertLessEqual(
                dialog.evaluate("el => el.scrollWidth - el.clientWidth"), 1
            )
            cancel = dialog.get_by_role("button", name=self.ui_text("community_meetings", "Cancel"), exact=True)
            cancel.focus()
            self.assertTrue(cancel.evaluate("el => el.matches(':focus-visible')"))
            self.assertTrue(cancel.is_visible())
            self.capture_visual_screenshot(
                "add-point-wizard-bottom", {"width": 390, "height": 844}
            )
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
        discard = row.get_by_role("button", name=self.ui_text("community_meetings", "Discard"), exact=True)
        discard.click()
        expect(discard).to_have_class(re.compile(r"(?:^|\s)is-selected(?:\s|$)"))
        wizard.locator('button[name="action_back"]').click()
        wizard.locator('button[name="action_next"]').click()
        expect(
            row.get_by_role("button", name=self.ui_text("community_meetings", "Discard"), exact=True)
        ).to_have_class(re.compile(r"(?:^|\s)is-selected(?:\s|$)"))
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
        try:
            capture_failure(test.page, test.id().replace(".", "-"))
        except Exception:
            pass  # Preserve the original failure if the browser itself has died.


def run_suite(test_case=FullMeetingBrowserChecks, actions=ACTIONS):
    if "--list-actions" in sys.argv:
        print(json.dumps(actions, indent=2))
        raise SystemExit(0)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_case)
    selectors = [argument.rsplit(".", 1)[-1] for argument in sys.argv[1:] if not argument.startswith("-")]
    if selectors:
        suite = unittest.TestSuite(
            t for t in suite if any(part in t._testMethodName for part in selectors)
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
        if result.wasSuccessful()
        and result.testsRun > 0
        and not result.skipped
        and (selectors or report["percent"] >= 90)
        else 1
    )


if __name__ == "__main__":
    run_suite()
