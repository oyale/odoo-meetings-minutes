#!/usr/bin/env python3
"""Reusable authenticated browser checks for the Community Meetings live screen.

Run with ODOO_BASE_URL, ODOO_LOGIN and ODOO_PASSWORD set to an existing meeting
editor account, and Python Playwright installed. Example:
    ODOO_BASE_URL=http://localhost:8069 \\
    ODOO_LOGIN=dev ODOO_PASSWORD=... python3 live_meeting_playwright.py
The suite creates and removes one scheduled meeting per case.
"""
import os
import time
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("ODOO_BASE_URL", "http://localhost:8069").rstrip("/")
DB = os.environ.get("ODOO_DB", "")
LOGIN = os.environ.get("ODOO_LOGIN")
PASSWORD = os.environ.get("ODOO_PASSWORD")


class LiveMeetingBrowserChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LOGIN or not PASSWORD:
            raise unittest.SkipTest("Set ODOO_LOGIN and ODOO_PASSWORD to an editor account.")
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            headless=os.environ.get("PLAYWRIGHT_HEADFUL") != "1",
            args=["--no-sandbox"],
        )
        cls.context = cls.browser.new_context(viewport={"width": 1440, "height": 1000})
        cls.page = cls.context.new_page()
        cls.console_errors = []
        cls.page.on("pageerror", lambda error: cls.console_errors.append(str(error)))
        cls.page.on("console", lambda msg: cls.console_errors.append(msg.text) if msg.type == "error" else None)
        cls.page.goto(urljoin(BASE_URL + "/", "web/login" + (("?db=%s" % DB) if DB else "")), wait_until="domcontentloaded")
        cls.page.locator('input[name="login"]').fill(LOGIN)
        cls.page.locator('input[name="password"]').fill(PASSWORD)
        cls.page.locator('button[type="submit"]').click()
        cls.page.wait_for_url("**/odoo**", timeout=30000)

    @classmethod
    def tearDownClass(cls):
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()

    def rpc(self, model, method, args, kwargs=None, page=None):
        response = (page or self.page).request.post(
            urljoin(BASE_URL + "/", "web/dataset/call_kw/%s/%s" % (model, method)),
            data={"jsonrpc": "2.0", "method": "call", "params": {
                "model": model, "method": method, "args": args, "kwargs": kwargs or {},
            }, "id": 1},
        )
        payload = response.json()
        if response.status != 200 or payload.get("error"):
            raise AssertionError("Odoo RPC failed: %r" % payload.get("error", payload))
        return payload["result"]

    def setUp(self):
        self.errors_before = len(self.console_errors)
        self.meeting_id = False
        self.item_ids = {}
        start = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0)
        self.meeting_id = self.rpc("community.meeting", "create", [{
            "name": "Playwright live case %s" % self.id().rsplit(".", 1)[-1],
            "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
        }])
        self.addCleanup(self.cleanup_meeting)
        for kind in ("information", "discussion", "decision", "todo"):
            agenda_type = self.rpc("community.meeting.agenda.type", "search", [[("behavior", "=", kind), ("active", "=", True)]], {"limit": 1})
            if not agenda_type:
                self.fail("No active agenda type for %s" % kind)
            self.item_ids[kind] = self.rpc("community.meeting.agenda.item", "create", [{
                "meeting_id": self.meeting_id,
                "name": "Browser %s case" % kind.title(),
                "kind": kind,
                "agenda_type_id": agenda_type[0],
            }])
        self.rpc("community.meeting", "action_schedule", [[self.meeting_id]])
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, self.meeting_id))
        self.page.get_by_role("button", name="Open Meeting").click(timeout=30000)
        try:
            self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        except Exception as error:
            raise AssertionError(
                "Live meeting did not render agenda cards; browser errors: %r; URL: %s"
                % (self.console_errors, self.page.url)
            ) from error
        self.page.get_by_role("button", name="Expand / Collapse all").click()

    def cleanup_meeting(self):
        if not self.meeting_id:
            return
        state = self.record("community.meeting", self.meeting_id, ["state"])["state"]
        if state not in ("draft", "scheduled"):
            # The standard workflow does not allow deleting terminal meetings.
            return
        transfers = self.rpc("community.meeting.carryover", "search", [["|", ("origin_meeting_id", "=", self.meeting_id), ("destination_meeting_id", "=", self.meeting_id)]])
        if transfers:
            return
        self.rpc("community.meeting", "action_cancel", [[self.meeting_id]])
        resolutions = self.rpc("community.meeting.resolution", "search", [[("meeting_id", "=", self.meeting_id)]])
        if resolutions:
            self.rpc("community.meeting.resolution", "unlink", [resolutions])
        self.rpc("community.meeting", "unlink", [[self.meeting_id]])

    def card(self, kind, begin=True):
        card = self.page.locator(".o_live_agenda_card").filter(has_text="Browser %s case" % kind.title())
        if begin:
            expand = card.locator(".o_live_expand")
            if expand.get_attribute("aria-expanded") == "false":
                expand.click()
            start_button = self.page.get_by_role("button", name="Start Meeting")
            if start_button.count():
                if start_button.is_enabled():
                    start_button.click()
                expect(self.page.get_by_role("button", name="Finish Meeting")).to_be_visible()
            item = self.record("community.meeting.agenda.item", self.item_ids[kind], ["has_started", "disposition", "actual_started_at"])
            if not item["actual_started_at"] and item["disposition"] not in ("closed", "discussed"):
                button_name = "Resume point" if item["has_started"] else "Begin point"
                card.get_by_role("button", name=button_name).click()
                expect(card.get_by_role("button", name="Pause point")).to_be_visible()
        return card

    def outcome(self, kind):
        return self.card(kind, begin=False).locator(".o_live_outcome_badge")

    def record(self, model, record_id, fields, page=None):
        return self.rpc(model, "read", [[record_id], fields], page=page)[0]

    def wait_timer(self, item_id, running):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = self.record("community.meeting.agenda.item", item_id, ["actual_started_at"])["actual_started_at"]
            if bool(value) == running:
                return
            time.sleep(0.1)
        self.fail("Point timer did not reach running=%r" % running)

    def test_scroll_and_meeting_wide_records_visibility(self):
        self.card("discussion")
        main = self.page.locator("main.o_community_live_meeting")
        self.assertEqual(main.evaluate("el => getComputedStyle(el).overflowY"), "auto")
        self.assertGreater(main.evaluate("el => el.scrollHeight - el.clientHeight"), 0)
        main.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        self.assertGreater(main.evaluate("el => el.scrollTop"), 0)
        self.assertFalse(self.page.get_by_text("Meeting level records", exact=True).count())

    def test_previous_discussion_is_read_only_and_can_be_cleared_or_restored(self):
        destination = self.record("community.meeting", self.meeting_id, ["start_datetime"])
        source_start = datetime.strptime(destination["start_datetime"], "%Y-%m-%d %H:%M:%S") - timedelta(days=1)
        source_meeting = self.rpc("community.meeting", "create", [{
            "name": "Earlier discussion source",
            "start_datetime": source_start.strftime("%Y-%m-%d %H:%M:%S"),
        }])
        self.addCleanup(self.cleanup_meeting_record, source_meeting)
        source_item = self.rpc("community.meeting.agenda.item", "create", [{
            "meeting_id": source_meeting,
            "name": "Earlier discussion source",
        }])
        self.rpc("community.meeting.agenda.item", "write", [[source_item], {
            "discussion_notes": "<p>Context from the earlier meeting</p>",
        }])
        transfer = self.rpc("community.meeting.carryover", "create", [{
            "origin_model": "agenda_item",
            "origin_record_id": source_item,
            "destination_meeting_id": self.meeting_id,
        }])
        self.rpc("community.meeting.carryover", "action_accept", [[transfer]])
        current_item = self.record("community.meeting.carryover", transfer, ["destination_item_id"])["destination_item_id"][0]
        item_state = self.record("community.meeting.agenda.item", current_item, ["name", "discussion_history", "previous_discussion_html"])
        self.assertIn("Context from the earlier meeting", item_state["previous_discussion_html"], repr(item_state))

        self.page.reload(wait_until="domcontentloaded")
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible(timeout=20000)
        carried_card = self.page.locator("#agenda-card-%s" % current_item)
        expect(carried_card).to_be_visible(timeout=20000)
        if carried_card.locator(".o_live_expand").get_attribute("aria-expanded") == "false":
            carried_card.locator(".o_live_expand").click()
        history = carried_card.locator(".o_live_previous_discussion")
        expect(history).to_be_visible(timeout=20000)
        expect(history.get_by_text("Context from the earlier meeting")).to_be_visible()
        expect(history.get_by_text("Read-only context from earlier meetings. It is not added to these minutes.")).to_be_visible()

        screenshot_dir = Path(os.environ.get("MM_SCREENSHOT_DIR", "/tmp"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        history.screenshot(path=str(screenshot_dir / "discussion-history-desktop.png"))
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        history.screenshot(path=str(screenshot_dir / "discussion-history-mobile.png"))
        self.page.set_viewport_size({"width": 1440, "height": 1000})

        history.get_by_role("button", name="Start without previous notes").click()
        dialog = self.page.locator(".modal").last
        expect(dialog.get_by_text("The original notes and this meeting’s notes are preserved.")).to_be_visible()
        dialog.get_by_role("button", name="Start without previous notes").click()
        expect(history.get_by_text("This point starts without earlier discussion.")).to_be_visible()
        self.assertTrue(self.record("community.meeting.agenda.item", current_item, ["discard_previous_discussion"])["discard_previous_discussion"])

        history.get_by_role("button", name="Show previous notes").click()
        expect(history.get_by_text("Context from the earlier meeting")).to_be_visible()
        self.assertFalse(self.record("community.meeting.agenda.item", current_item, ["discard_previous_discussion"])["discard_previous_discussion"])

    def cleanup_meeting_record(self, meeting_id):
        state = self.record("community.meeting", meeting_id, ["state"])["state"]
        if state in ("draft", "scheduled"):
            transfers = self.rpc("community.meeting.carryover", "search", [["|", ("origin_meeting_id", "=", meeting_id), ("destination_meeting_id", "=", meeting_id)]])
            if transfers:
                return
            self.rpc("community.meeting", "action_cancel", [[meeting_id]])
            self.rpc("community.meeting", "unlink", [[meeting_id]])

    def test_information_point_can_be_marked_done(self):
        card = self.card("information")
        card.get_by_role("button", name="Done").click()
        expect(self.outcome("information")).to_have_text("Done")
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["information"], ["disposition"])["disposition"], "discussed")

    def test_discussion_point_can_be_resolved(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Done").click()
        expect(self.outcome("discussion")).to_have_text("Resolved")
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["disposition"])["disposition"], "closed")

    def test_postponing_a_point_enables_next_meeting_review(self):
        card = self.card("discussion")
        self.assertEqual(card.locator(".o_live_point_footer").get_by_role("button", name="Postpone agenda point").count(), 1)
        self.assertEqual(card.locator(".o_live_point_actions").get_by_role("button", name="Postpone agenda point").count(), 0)
        card.get_by_role("button", name="Postpone agenda point").click()
        card.get_by_label("Reason for postponing").fill("Continue next time")
        card.get_by_role("button", name="Leave postponed").click()
        expect(card.get_by_text("Will be reviewed at the next meeting", exact=True)).to_be_visible()
        self.assertTrue(self.record(
            "community.meeting.agenda.item", self.item_ids["discussion"],
            ["review_next_meeting"],
        )["review_next_meeting"])

    def test_live_result_can_be_undone_and_manual_actual_time_is_hidden(self):
        header = self.page.locator(".o_live_header_primary")
        expect(header.get_by_label("Minutes secretary")).to_be_visible()
        expect(self.page.get_by_text("Estimated duration", exact=True)).not_to_be_visible()
        self.page.locator(".o_live_more_details > summary").click()
        expect(self.page.get_by_text("Estimated duration", exact=True)).to_be_visible()
        card = self.card("discussion")
        card.get_by_role("button", name="Done").click()
        expect(self.outcome("discussion")).to_have_text("Resolved")
        self.assertEqual(card.get_by_label("Actual minutes for this point").count(), 0)
        card.get_by_role("button", name="Undo point result").click()
        reason = card.get_by_label("Why reopen this point?")
        reason.fill("We need to revise the conclusion.")
        card.get_by_role("button", name="Reopen point").click()
        expect(self.outcome("discussion")).to_have_text("Pending")
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["disposition"])["disposition"], "open")

    def test_point_timer_navigation_collapses_and_resume_accumulates(self):
        self.page.get_by_role("button", name="Start Meeting").click()
        expect(self.page.get_by_role("button", name="Finish Meeting")).to_be_visible()
        first = self.card("information", begin=False)
        second = self.card("discussion", begin=False)
        first.get_by_role("button", name="Begin point").click()
        expect(first.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", "Point in progress")
        self.wait_timer(self.item_ids["information"], True)
        started = self.record(
            "community.meeting.agenda.item", self.item_ids["information"],
            ["actual_started_at"],
        )["actual_started_at"]
        self.assertTrue(
            started,
            "Point timer did not start. Meeting=%r; alerts=%r; browser errors=%r"
            % (
                self.record("community.meeting", self.meeting_id, ["state", "actual_start_datetime"]),
                self.page.locator('[role="alert"]').all_text_contents(),
                self.console_errors[self.errors_before:],
            ),
        )
        self.rpc("community.meeting.agenda.item", "write", [
            [self.item_ids["information"]],
            {"actual_started_at": (datetime.utcnow() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")},
        ])
        self.page.get_by_role("button", name="Next agenda point").click()
        expect(first.locator(".o_live_card_body")).to_be_hidden()
        expect(second.locator(".o_live_card_body")).to_be_visible()
        first_seconds = self.record(
            "community.meeting.agenda.item", self.item_ids["information"],
            ["actual_seconds"],
        )["actual_seconds"]
        self.assertGreaterEqual(first_seconds, 120)

        second.get_by_role("button", name="Begin point").click()
        expect(second.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", "Point in progress")
        self.page.get_by_role("button", name="Previous agenda point").click()
        first.get_by_role("button", name="Resume point").click()
        expect(first.get_by_role("button", name="Pause point")).to_be_visible()
        self.assertTrue(
            self.record("community.meeting.agenda.item", self.item_ids["information"], ["actual_started_at"])["actual_started_at"]
        )
        self.rpc("community.meeting.agenda.item", "write", [
            [self.item_ids["information"]],
            {"actual_started_at": (datetime.utcnow() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")},
        ])
        self.assertTrue(self.record(
            "community.meeting.agenda.item", self.item_ids["information"], ["actual_started_at"]
        )["actual_started_at"])
        first.get_by_role("button", name="Pause point").click()
        self.wait_timer(self.item_ids["information"], False)
        timing = self.record(
            "community.meeting.agenda.item", self.item_ids["information"],
            ["actual_seconds", "actual_minutes", "actual_started_at"],
        )
        self.assertGreaterEqual(
            timing["actual_seconds"], first_seconds + 60,
            "Timer did not accumulate after resume: first=%r final=%r"
            % (first_seconds, timing),
        )
        self.assertGreaterEqual(timing["actual_minutes"], 3)
        self.assertFalse(timing["actual_started_at"])

    def test_point_live_editing_requires_begin_and_pause_is_read_only(self):
        self.rpc("community.meeting.agenda.item", "write", [
            [self.item_ids["discussion"]],
            {"description": "Context that belongs immediately before the live notes."},
        ])
        self.page.reload(wait_until="domcontentloaded")
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        card = self.card("discussion", begin=False)
        self.assertEqual(
            card.locator('[contenteditable="true"][aria-label="Discussion notes"]').count(),
            0,
            "Unexpected editor before Begin: item=%r; editors=%r"
            % (
                self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["has_started", "actual_started_at"]),
                card.locator('[contenteditable="true"]').evaluate_all("els => els.map(el => el.outerHTML)"),
            ),
        )
        self.assertEqual(card.get_by_role("button", name="Add agreement").count(), 0)
        self.page.get_by_role("button", name="Start Meeting").click()
        card.get_by_role("button", name="Begin point").click()
        expect(card.locator('[contenteditable="true"][aria-label="Discussion notes"]')).to_be_visible()
        self.assertTrue(
            card.locator(".o_live_planned").evaluate(
                "el => el.nextElementSibling?.querySelector('.o_live_discussion_notes') !== null"
            ),
            "Discussion notes should sit directly below the point description.",
        )
        record_actions = card.locator(".o_live_record_actions")
        self.assertTrue(
            card.get_by_role("heading", name="Agreements and resolutions").evaluate(
                "el => el.nextElementSibling?.classList.contains('o_live_record_actions')"
            ),
            "The agreement/dissent actions should follow their heading.",
        )
        self.assertEqual(
            [button.inner_text().strip() for button in record_actions.locator("button").all()],
            ["Add agreement", "Add dissent"],
        )
        expect(record_actions.get_by_role("button", name="Add dissent")).to_be_visible()
        expect(record_actions.get_by_role("button", name="Add agreement")).to_be_visible()
        card.get_by_role("button", name="Pause point").click()
        expect(card.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", "Point paused")
        self.assertEqual(
            card.locator('[contenteditable="true"][aria-label="Discussion notes"]').count(),
            0,
            "Editor remained after pause: item=%r; editor=%r; card=%r"
            % (
                self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["has_started", "actual_started_at"]),
                card.locator('[contenteditable="true"][aria-label="Discussion notes"]').evaluate_all("els => els.map(el => el.outerHTML)"),
                card.locator(".o_live_card_body").inner_text(),
            ),
        )
        self.assertEqual(card.get_by_role("button", name="Add agreement").count(), 0)

        editor = card.locator('[aria-label="Discussion notes"]')
        for _ in range(3):
            card.get_by_role("button", name="Resume point").click()
            expect(card.get_by_role("button", name="Pause point")).to_be_visible()
            self.assertEqual(editor.count(), 1, "Discussion editor was duplicated after resuming a point")
            card.get_by_role("button", name="Pause point").click()
            expect(card.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", "Point paused")
            self.assertEqual(editor.count(), 0, "A paused point must show notes read-only")

    def test_live_meeting_survives_browser_refresh(self):
        self.assertLessEqual(
            self.page.url.count("/community.meeting/"),
            1,
            "Opening the live meeting retained a deeply nested record route: %s" % self.page.url,
        )
        self.page.reload(wait_until="domcontentloaded")
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible(timeout=30000)
        expect(self.page.locator(".o_live_agenda_card")).to_have_count(4)
        self.assertFalse(
            any("Invalid ids list" in error for error in self.console_errors[self.errors_before:]),
            "Refreshing the live meeting lost its meeting id: %r" % self.console_errors[self.errors_before:],
        )

    def test_meeting_pause_and_resume_locks_points_without_finishing(self):
        self.page.get_by_role("button", name="Start Meeting").click()
        card = self.card("discussion", begin=False)
        card.get_by_role("button", name="Begin point").click()
        editor = card.locator('[aria-label="Discussion notes"]')
        expect(editor).to_have_attribute("contenteditable", "true")
        self.page.get_by_role("button", name="Pause Meeting").click()
        expect(self.page.get_by_role("button", name="Resume Meeting")).to_be_visible()
        expect(editor).to_have_count(0)
        expect(card.locator(".o_live_rich_readonly").first).to_be_visible()
        meeting = self.record("community.meeting", self.meeting_id, ["actual_paused_at", "actual_end_datetime"])
        self.assertTrue(meeting["actual_paused_at"])
        self.assertFalse(meeting["actual_end_datetime"])
        self.page.get_by_role("button", name="Resume Meeting").click()
        expect(self.page.get_by_role("button", name="Pause Meeting")).to_be_visible()
        expect(card.get_by_role("button", name="Resume point")).to_be_visible()
        self.assertFalse(self.record("community.meeting", self.meeting_id, ["actual_paused_at"])["actual_paused_at"])

    def test_minutes_draft_allows_editing_discussion_notes(self):
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["state"])["state"],
            "minutes_draft",
        )
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, self.meeting_id))
        self.page.get_by_role("button", name="Open Meeting").click(timeout=30000)
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        card = self.card("discussion", begin=False)
        expect(card.locator('[aria-label="Discussion notes"]')).to_have_attribute(
            "contenteditable", "true",
        )

    def test_minutes_preview_returns_to_draft_meeting(self):
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, self.meeting_id))
        self.page.get_by_role("button", name="Open Meeting").click(timeout=30000)
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)

        self.page.get_by_role("button", name="Preview Minutes", exact=True).click()
        preview = self.page.locator(".o_community_minutes_preview")
        expect(preview).to_contain_text("Draft preview · saved content")
        expect(preview).to_contain_text("Browser Discussion case")
        expect(preview.get_by_role("button", name="Return to meeting to edit")).to_be_visible()
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["state"])["state"],
            "minutes_draft",
        )

        preview.get_by_role("button", name="Return to meeting to edit").click()
        expect(self.page.locator(".o_form_view")).to_be_visible(timeout=30000)
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["state"])["state"],
            "minutes_draft",
        )

    def test_series_structural_points_render_in_live_meeting(self):
        series = self.rpc("community.meeting.series", "create", [{
            "name": "Structural live " + uuid.uuid4().hex[:8],
            "has_minutes_approval_point": True,
            "has_next_meeting_point": True,
        }])
        previous = self.rpc("community.meeting", "create", [{
            "name": "Structural previous meeting",
            "series_id": series,
            "start_datetime": "2026-10-01 10:00:00",
        }])
        self.rpc("community.meeting", "action_schedule", [[previous]])
        self.rpc("community.meeting", "action_mark_held", [[previous]])
        start = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0)
        meeting_id = self.rpc("community.meeting", "create", [{
            "name": "Structural live meeting",
            "series_id": series,
            "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
        }])
        self.rpc("community.meeting", "action_schedule", [[meeting_id]])
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, meeting_id))
        self.page.get_by_role("button", name="Open Meeting").click(timeout=30000)
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        self.page.get_by_role("button", name="Expand / Collapse all").click()
        expect(self.page.locator('[aria-label="Next meeting date"]')).to_be_visible()
        expect(self.page.locator(".o_live_minutes_approval")).to_be_visible()
        expect(self.page.locator(".o_live_minutes_approval")).to_contain_text("Structural previous meeting")

    def test_review_previous_minutes_opens_live_and_approves(self):
        series = self.rpc(
            "community.meeting.series", "create",
            [{"name": "Review minutes series " + uuid.uuid4().hex[:8]}],
        )
        self.rpc("community.meeting", "write", [[self.meeting_id], {"series_id": series}])
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        current = self.rpc("community.meeting", "create", [{
            "name": "Review previous minutes", "series_id": series,
            "start_datetime": (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
        }])
        agenda_type = self.rpc("community.meeting.agenda.type", "search", [[("behavior", "=", "minutes_approval")]], {"limit": 1})[0]
        self.rpc("community.meeting.agenda.item", "create", [{"meeting_id": current, "name": "Approve previous minutes", "agenda_type_id": agenda_type}])
        self.rpc("community.meeting", "action_schedule", [[current]])
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, current))
        self.page.get_by_role("button", name="Open Meeting").click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        if self.page.locator(".o_live_expand").first.get_attribute("aria-expanded") == "false":
            self.page.locator(".o_live_expand").first.click()
        self.page.get_by_role("button", name="Open minutes", exact=True).click()
        expect(self.page.get_by_role("button", name="Approve Minutes", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="Approve Minutes", exact=True).click()
        expect(self.page.get_by_role("button", name="Approve Minutes", exact=True)).to_have_count(0, timeout=30000)
        self.assertEqual(self.record("community.meeting", self.meeting_id, ["state"])["state"], "approved")
        previous_code = self.record("community.meeting", self.meeting_id, ["code"])["code"]
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, current))
        self.page.get_by_role("button", name="Open Meeting").click()
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        if self.page.locator(".o_live_expand").first.get_attribute("aria-expanded") == "false":
            self.page.locator(".o_live_expand").first.click()
        approval = self.page.locator(".o_live_minutes_approval")
        expect(approval).to_contain_text("Approved previous minutes")
        expect(approval).to_contain_text(previous_code)
        approval.get_by_role("button", name="Open minutes").first.click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        expect(self.page.get_by_role("button", name="Add Point", exact=True)).to_have_count(0)
        expect(self.page.get_by_role("button", name="Approve Minutes", exact=True)).to_have_count(0)
        expect(self.page.locator(".o_live_rich_readonly").first).to_be_visible()

    def test_agreement_followup_asks_for_series(self):
        self.retain_carryover = True
        series_name = "Agreement followup series " + str(self.meeting_id)
        series = self.rpc("community.meeting.series", "create", [{"name": series_name}])
        self.rpc("community.meeting", "write", [[self.meeting_id], {"series_id": series}])
        self.page.reload(wait_until="domcontentloaded")
        card = self.card("discussion")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        card.get_by_placeholder("Agreement title").fill("Follow this agreement")
        card.get_by_placeholder("What was agreed?").fill("Review progress in the next assembly")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        card.get_by_role("button", name="Follow up at another meeting").click()
        dialog = self.page.get_by_role("dialog")
        expect(dialog.locator('.o_field_widget[name="destination_meeting_id"]')).to_have_count(0)
        expect(dialog.locator('.o_field_widget[name="destination_series_id"] input')).to_have_value(series_name)
        dialog.get_by_role("button", name="Request Move", exact=True).click()
        expect(dialog).not_to_be_visible()
        transfers = self.rpc("community.meeting.carryover", "search_read", [[("origin_meeting_id", "=", self.meeting_id), ("origin_model", "=", "resolution")]], {"fields": ["destination_series_id", "destination_meeting_id"]})
        self.assertEqual(transfers[0]["destination_series_id"][0], series)
        self.assertFalse(transfers[0]["destination_meeting_id"])

    def test_approver_without_editor_can_review_and_approve_live(self):
        login = os.environ.get("ODOO_REVIEWER_LOGIN")
        if not login:
            self.skipTest("Disposable reviewer is not configured")
        reviewer = self.rpc("res.users", "search", [[("login", "=", login)]], {"limit": 1})[0]
        self.rpc("community.meeting", "write", [[self.meeting_id], {"reader_user_ids": [[4, reviewer]]}])
        self.rpc("community.meeting.editor.note", "create", [{"meeting_id": self.meeting_id, "agenda_item_id": self.item_ids["discussion"], "content": "PRIVATE_EDITORIAL_CONTENT"}])
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        context = self.browser.new_context()
        try:
            page = context.new_page()
            page.goto(BASE_URL + "/web/login" + (("?db=%s" % DB) if DB else ""))
            page.locator('input[name="login"]').fill(login)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/odoo**")
            page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, self.meeting_id))
            page.get_by_role("button", name="Open Meeting").click()
            expect(page.get_by_role("button", name="Approve Minutes", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Add Point", exact=True)).to_have_count(0)
            expect(page.locator('[contenteditable="true"]')).to_have_count(0)
            expect(page.get_by_text("PRIVATE_EDITORIAL_CONTENT")).to_have_count(0)
            page.get_by_role("button", name="Approve Minutes", exact=True).click()
            expect(page.locator(".o_live_topbar")).to_contain_text("Approved")
            self.assertEqual(
                self.record("community.meeting", self.meeting_id, ["state"], page=page)["state"],
                "approved",
            )
        finally:
            context.close()

    def test_multiple_responsible_people_persist(self):
        login = os.environ.get("ODOO_REVIEWER_LOGIN")
        if not login:
            self.skipTest("Disposable reviewer is not configured")
        reviewer = self.rpc("res.users", "search", [[("login", "=", login)]], {"limit": 1})[0]
        owner = self.record("community.meeting", self.meeting_id, ["organizer_id"])["organizer_id"][0]
        self.rpc("community.meeting", "write", [[self.meeting_id], {"reader_user_ids": [[4, reviewer]]}])
        self.page.reload(wait_until="domcontentloaded")
        card = self.card("discussion")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label("Task name").fill("Shared native to-do")
        form.get_by_text("Assign to multiple people", exact=False).click()
        form.get_by_label("Responsible people").select_option([str(owner), str(reviewer)])
        form.get_by_role("button", name="Add follow-up", exact=True).click()
        expect(form).to_have_count(0)
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        expect(row.get_by_label("Task name")).to_have_value("Shared native to-do")
        rows = self.rpc("community.meeting.action", "search_read", [[("agenda_item_id", "=", self.item_ids["discussion"])]], {"fields": ["responsible_user_ids", "followup_activity_ids"]})
        self.assertEqual(set(rows[0]["responsible_user_ids"]), {owner, reviewer})
        self.assertEqual(len(rows[0]["followup_activity_ids"]), 2)
        self.page.reload(wait_until="domcontentloaded")
        card = self.card("discussion")
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        expect(row.get_by_label("Task name")).to_have_value("Shared native to-do")
        row.get_by_text("Multiple people", exact=False).click()
        row.get_by_label("Responsible people").select_option([str(owner)])
        expect(row.get_by_label("Responsible people").locator("option:checked")).to_have_count(1)

    def test_convert_menu_matches_available_containers(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label("Task name").fill("Single container follow-up")
        form.get_by_role("button", name="Add follow-up").click()
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        allowed = self.rpc(
            "community.meeting", "get_followup_defaults",
            [[self.meeting_id], self.item_ids["discussion"]],
        )["allowed_kinds"]
        expect(row.locator(".o_live_followup_convert")).to_have_count(1 if len(allowed) > 1 else 0)

    def test_header_details_and_add_point_remain_available_while_paused(self):
        self.page.get_by_role("button", name="Start Meeting").click()
        self.page.get_by_role("button", name="Pause Meeting").click()
        expect(self.page.get_by_role("button", name="Add Point")).to_be_visible()
        expect(self.page.get_by_role("button", name="Add Point")).to_be_enabled()
        self.page.get_by_role("button", name="Edit attendees").click()
        expect(self.page.get_by_role("button", name="Save attendees")).to_be_visible()
        self.page.get_by_role("button", name="Cancel").click()

        self.page.get_by_label("Meeting name").fill("Paused meeting header edited")
        self.page.get_by_label("Meeting name").press("Tab")
        secretary = self.rpc(
            "res.users", "search_read", [[("login", "=", LOGIN)]],
            {"fields": ["name"], "limit": 1},
        )[0]
        self.page.get_by_label("Minutes secretary").select_option(
            value=str(secretary["id"])
        )
        self.page.locator(".o_live_more_details > summary").click()
        self.page.get_by_label("Location").fill("Board Room")
        self.page.get_by_label("Location").press("Tab")
        self.page.get_by_label("Meeting link").fill("https://meet.example.test/board")
        self.page.get_by_label("Meeting link").press("Tab")
        expect(self.page.get_by_role("status")).to_have_text("All changes saved")
        self.page.wait_for_timeout(500)
        saved = self.record(
            "community.meeting", self.meeting_id,
            ["name", "secretary_id", "location", "meeting_url"],
        )
        self.assertEqual(saved["name"], "Paused meeting header edited")
        self.assertEqual(saved["secretary_id"][0], secretary["id"])
        self.assertEqual(saved["location"], "Board Room")
        self.assertEqual(saved["meeting_url"], "https://meet.example.test/board")
        self.page.reload(wait_until="domcontentloaded")
        self.page.locator(".o_live_more_details > summary").click()
        expect(self.page.get_by_label("Meeting name")).to_have_value("Paused meeting header edited")
        expect(self.page.get_by_label("Location", exact=True)).to_have_value("Board Room")
        expect(self.page.get_by_label("Minutes secretary").locator("option:checked")).to_have_text(secretary["name"])


    def test_decision_can_be_undone_during_running_meeting(self):
        self.page.get_by_role("button", name="Start Meeting").click()
        expect(self.page.get_by_role("button", name="Finish Meeting")).to_be_visible()
        card = self.card("decision")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        card.get_by_placeholder("Agreement title").fill("Approve during live session")
        card.get_by_placeholder("What was agreed?").fill("Approved pending verification")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        expect(self.outcome("decision")).to_have_text("Approved")
        card.get_by_role("button", name="Undo point result").click()
        card.get_by_label("Why reopen this point?").fill("The vote needs checking.")
        card.get_by_role("button", name="Reopen point").click()
        expect(self.outcome("decision")).to_have_text("Pending")
        agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["status"], "limit": 1})[0]
        self.assertEqual(agreement["status"], "withdrawn")

    def test_todo_requires_a_followup_task_before_resolution(self):
        card = self.card("todo")
        button = card.get_by_role("button", name="Done")
        expect(self.outcome("todo")).to_have_text("Task required")
        expect(button).to_be_disabled()
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        card.get_by_label("Task name").fill("Prepare the requested draft")
        card.get_by_role("button", name="Add follow-up").click()
        expect(self.outcome("todo")).to_have_text("Task assigned")
        expect(button).to_be_enabled()

        button.click()
        expect(self.outcome("todo")).to_have_text("Resolved")
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["todo"], ["disposition"])["disposition"], "closed")

    def test_decision_requires_and_uses_agreement_without_direct_edit(self):
        card = self.card("decision")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        expect(self.outcome("decision")).to_have_text("Pending")
        title = card.get_by_placeholder("Agreement title")
        title.fill("Approve the decision")
        card.get_by_placeholder("What was agreed?").fill("Approved after discussion")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        expect(self.outcome("decision")).to_have_text("Approved")
        agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["decision_outcome", "status"], "limit": 1})[0]
        self.assertEqual((agreement["decision_outcome"], agreement["status"]), ("approved", "active"))
        self.assertEqual(card.get_by_label("Decision result", exact=True).count(), 0)
        card.get_by_role("button", name="Undo point result").click()
        card.get_by_role("button", name="Reopen point").click()
        expect(self.outcome("decision")).to_have_text("Pending")
        card.get_by_role("button", name="Resume point").click()
        card.get_by_role("button", name="Add agreement", exact=True).click()
        card.get_by_placeholder("Agreement title").fill("Reject the decision")
        card.get_by_label("New decision result").select_option("denied")
        card.get_by_placeholder("What was agreed?").fill("Rejected after reconsideration")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        expect(self.outcome("decision")).to_have_text("Rejected")
        self.assertFalse(self.console_errors[self.errors_before:], self.console_errors[self.errors_before:])

    def test_postponing_an_approved_decision_withdraws_its_agreement(self):
        card = self.card("decision")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        card.get_by_placeholder("Agreement title").fill("Approve before postponing")
        card.get_by_placeholder("What was agreed?").fill("Approval must be revisited.")
        card.get_by_role("button", name="Add agreement", exact=True).click()
        expect(self.outcome("decision")).to_have_text("Approved")
        card.get_by_role("button", name="Undo point result").click()
        card.get_by_role("button", name="Reopen point").click()
        card.get_by_role("button", name="Resume point").click()
        deadline = time.time() + 8
        point = self.record(
            "community.meeting.agenda.item", self.item_ids["decision"],
            ["actual_started_at"],
        )
        while time.time() < deadline and not point["actual_started_at"]:
            time.sleep(0.2)
            point = self.record(
                "community.meeting.agenda.item", self.item_ids["decision"],
                ["actual_started_at"],
            )
        self.assertTrue(point["actual_started_at"], "Point should be resumed before postponing it")
        expand = card.locator(".o_live_expand")
        if expand.get_attribute("aria-expanded") == "false":
            expand.click()
        expect(card.get_by_role("button", name="Postpone agenda point")).to_be_visible()
        card.get_by_role("button", name="Postpone agenda point").click()
        if expand.get_attribute("aria-expanded") == "false":
            expand.click()
        reason = card.get_by_label("Reason for postponing")
        expect(reason).to_be_visible()
        reason.fill("The approval needs review.")
        card.get_by_role("button", name="Leave postponed").click()
        deadline = time.time() + 8
        point = self.record("community.meeting.agenda.item", self.item_ids["decision"], ["disposition"])
        agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["status"], "limit": 1})[0]
        while time.time() < deadline and point["disposition"] != "deferred":
            time.sleep(0.2)
            point = self.record("community.meeting.agenda.item", self.item_ids["decision"], ["disposition"])
            agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["status"], "limit": 1})[0]
        self.assertEqual(point["disposition"], "deferred")
        self.assertEqual(agreement["status"], "withdrawn")
        expect(self.outcome("decision")).to_have_text("Postponed")

    def test_dissent_author_reason_and_statement_are_usable(self):
        card = self.card("discussion")
        card.get_by_role("button", name="Add dissent").click()
        author = card.get_by_label("Dissent author")
        kind = card.get_by_label("Dissent reason")
        statement = card.get_by_label("Dissent statement")
        expect(author).to_be_visible()
        expect(statement).to_be_visible()
        author.fill("Ada Lovelace")
        kind.select_option(label="Reservation")
        statement.fill("I disagree with the proposed deadline.")
        card.get_by_role("button", name="Add dissent").click()
        deadline = time.time() + 8
        dissent = []
        while time.time() < deadline and not dissent:
            dissent = self.rpc("community.meeting.dissent", "search_read", [[("meeting_id", "=", self.meeting_id)]], {"fields": ["author_display_name", "reason_id", "body"], "limit": 1})
            if not dissent:
                time.sleep(0.2)
        self.assertTrue(dissent, "The dissent form did not create a record.")
        dissent = dissent[0]
        self.assertEqual(dissent["author_display_name"], "Ada Lovelace")
        self.assertEqual(dissent["reason_id"][1], "Reservation")
        self.assertIn("proposed deadline", dissent["body"])

    def test_defer_works_for_each_point_type(self):
        for kind in ("information", "discussion", "decision", "todo"):
            with self.subTest(kind=kind):
                card = self.card(kind)
                card.get_by_role("button", name="Postpone agenda point").click()
                card.get_by_label("Reason for postponing").fill("Waiting for more information.")
                card.get_by_role("button", name="Leave postponed").click()
                expect(self.outcome(kind)).to_have_text("Postponed")
                deadline = time.time() + 8
                saved = self.record("community.meeting.agenda.item", self.item_ids[kind], ["disposition"])
                while time.time() < deadline and saved["disposition"] != "deferred":
                    time.sleep(0.2)
                    saved = self.record("community.meeting.agenda.item", self.item_ids[kind], ["disposition"])
                self.assertEqual(saved["disposition"], "deferred")

    def test_private_note_form_stays_collapsed_until_requested(self):
        card = self.card("discussion")
        expect(card.get_by_label("Private editorial note")).not_to_be_visible()
        card.locator("details").filter(has_text="Private editorial notes").locator("summary").click()
        card.get_by_role("button", name="Add private note").click()
        expect(card.get_by_label("Private editorial note")).to_be_visible()


if __name__ == "__main__":
    unittest.main(verbosity=2)
