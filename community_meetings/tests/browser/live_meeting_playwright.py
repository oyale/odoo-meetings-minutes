#!/usr/bin/env python3
"""Reusable authenticated browser checks for the Community Meetings live screen.

Run with ODOO_BASE_URL, ODOO_LOGIN and ODOO_PASSWORD set to an existing meeting
editor account, and Python Playwright installed. Example:
    ODOO_BASE_URL=http://localhost:8069 \\
    ODOO_LOGIN=dev ODOO_PASSWORD=... python3 live_meeting_playwright.py
The suite creates and removes one scheduled meeting per case.
"""
import json
import os
import re
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import expect

TESTS_ROOT = Path(__file__).resolve().parents[3] / "tests"
sys.path.insert(0, str(TESTS_ROOT))
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from browser_support.odoo_browser import OdooBrowserSession, normalize_locale
from browser_support.screenshot_capture import capture_checkpoint
from browser_support.ui_text import LocalizedUI

BASE_URL = os.environ.get("ODOO_BASE_URL", "http://localhost:8069").rstrip("/")
DB = os.environ.get("ODOO_DB", "")
LOGIN = os.environ.get("ODOO_LOGIN")
PASSWORD = os.environ.get("ODOO_PASSWORD")


class LiveWriteTrace:
    """Track concurrent live point writes while a browser action flushes editors."""

    def __init__(self, page):
        self.page = page
        self.rpc = []
        self.active_note_writes = 0
        self.max_active_note_writes = 0
        self.empty_note_writes = []
        page.on("request", self.on_request)
        page.on("response", self.on_response)

    def on_request(self, request):
        if "/web/dataset/call_kw/" not in request.url:
            return
        payload = request.post_data_json
        self.rpc.append({"phase": "request", "url": request.url, "payload": payload})
        if request.url.endswith("community.meeting.agenda.item/write"):
            self.active_note_writes += 1
            self.max_active_note_writes = max(self.max_active_note_writes, self.active_note_writes)
            values = payload["params"]["args"][1]
            if values.get("discussion_notes") == "<p><br></p>":
                self.empty_note_writes.append(payload)

    def on_response(self, response):
        if "/web/dataset/call_kw/" not in response.url:
            return
        payload = response.json()
        self.rpc.append({
            "phase": "response",
            "url": response.url,
            "status": response.status,
            "payload": payload,
        })
        if response.url.endswith("community.meeting.agenda.item/write"):
            self.active_note_writes -= 1

    def stop(self):
        self.page.remove_listener("request", self.on_request)
        self.page.remove_listener("response", self.on_response)


class LiveMeetingBrowserChecks(LocalizedUI, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LOGIN or not PASSWORD:
            raise unittest.SkipTest("Set ODOO_LOGIN and ODOO_PASSWORD to an editor account.")
        cls.session = OdooBrowserSession.login(
            BASE_URL,
            DB,
            LOGIN,
            PASSWORD,
            headless=os.environ.get("PLAYWRIGHT_HEADFUL") != "1",
            viewport={"width": 1440, "height": 1000},
            has_touch=True,
        )
        cls.playwright = cls.session.playwright
        cls.browser = cls.session.browser
        cls.context = cls.session.context
        cls.page = cls.session.page
        cls.console_errors = cls.session.console_errors
        capture_language = os.environ.get("MM_CAPTURE_LANGUAGE")
        if capture_language:
            user_ids = cls.session.rpc("res.users", "search", [[("login", "=", LOGIN)]])
            if len(user_ids) != 1:
                raise AssertionError("expected one disposable browser user")
            cls.session.rpc("res.users", "write", [user_ids, {"lang": capture_language}])
            cls.session.switch_user(LOGIN, PASSWORD)
            cls.session.verify_locale(capture_language)

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def effective_locale(self):
        return normalize_locale(self.session.session_info().get("user_context", {}).get("lang"))

    def rpc(self, model, method, args, kwargs=None, page=None):
        return self.session.rpc(model, method, args, kwargs, page=page)

    def setUp(self):
        self.errors_before = len(self.console_errors)
        self.fixture = LiveMeetingFixture.create_scheduled_live_meeting(
            self.session, self.id().rsplit(".", 1)[-1]
        )
        self.meeting_id = self.fixture.meeting_id
        self.item_ids = self.fixture.item_ids
        self.addCleanup(self.cleanup_meeting)
        if os.environ.get("MM_CAPTURE_MINUTES_PREVIEW"):
            capture_language = os.environ.get("MM_CAPTURE_LANGUAGE", "en_US")
            fixture_language = os.environ.get("MM_CAPTURE_FIXTURE_LANGUAGE", capture_language)
            spanish_fixture = fixture_language.lower().startswith("es")
            reviewer_ids = self.rpc(
                "res.users", "search", [[("login", "=", os.environ["ODOO_REVIEWER_LOGIN"])]],
            )
            self.assertEqual(len(reviewer_ids), 1, "expected one disposable reviewer")
            reviewer = self.rpc("res.users", "read", [reviewer_ids, ["partner_id"]])[0]
            self.rpc("community.meeting", "write", [[self.meeting_id], {
                "name": (
                    "Planificación del segundo trimestre"
                    if spanish_fixture
                    else "Planning for the second quarter"
                ),
                "location": "Sala de reuniones" if spanish_fixture else "Meeting room",
                "description": (
                    "<p>Revisar prioridades, calendario y recursos.</p>"
                    if spanish_fixture
                    else "<p>Review priorities, schedule, and resources.</p>"
                ),
                "minutes_notes": (
                    "<p>Se acuerda preparar una propuesta para la siguiente sesión.</p>"
                    if spanish_fixture
                    else "<p>Prepare a proposal for the next session.</p>"
                ),
                "attendee_partner_ids": [(6, 0, [reviewer["partner_id"][0]])],
            }])
            agenda_names = (
                {
                    "information": "Apertura y acuerdos anteriores",
                    "discussion": "Seguimiento del proyecto comunitario",
                    "decision": "Presupuesto del próximo trimestre",
                    "todo": "Preparar calendario de actividades",
                }
                if spanish_fixture
                else {
                    "information": "Opening and previous decisions",
                    "discussion": "Community project update",
                    "decision": "Next quarter budget",
                    "todo": "Prepare the activity calendar",
                }
            )
            for kind, item_id in self.item_ids.items():
                values = {"name": agenda_names[kind]}
                if kind == "discussion":
                    values["discussion_notes"] = (
                        "<p>El equipo revisa los avances y los riesgos.</p>"
                        if spanish_fixture
                        else "<p>The team reviews progress and risks.</p>"
                    )
                self.rpc("community.meeting.agenda.item", "write", [[item_id], values])
        else:
            open_live_meeting(self.session, self.meeting_id)

    def cleanup_meeting(self):
        if not self.meeting_id:
            return
        self.fixture.cleanup()

    def card(self, kind, begin=True):
        card = self.page.locator(".o_live_agenda_card").filter(has_text="Browser %s case" % kind.title())
        if begin:
            expand = card.locator(".o_live_expand")
            if expand.get_attribute("aria-expanded") == "false":
                expand.click()
            start_button = self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting"))
            if start_button.count():
                if start_button.is_enabled():
                    start_button.click()
                expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"))).to_be_visible()
            item = self.record("community.meeting.agenda.item", self.item_ids[kind], ["has_started", "disposition", "actual_started_at"])
            if not item["actual_started_at"] and item["disposition"] not in ("closed", "discussed"):
                source_button_name = "Resume point" if item["has_started"] else "Begin point"
                button_name = self.ui_text("community_meetings", source_button_name)
                card.get_by_role("button", name=button_name).click()
                expect(card.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"))).to_be_visible()
        return card

    def outcome(self, kind):
        return self.card(kind, begin=False).locator(".o_live_outcome_badge")

    def capture_checkpoint(self, name, viewport=None, capture_target=None):
        locale = self.effective_locale()
        if not locale:
            raise AssertionError("Odoo session has no effective locale for screenshot metadata")
        return capture_checkpoint(
            self.page,
            name,
            self.id().replace(".", "-"),
            locale,
            viewport,
            capture_target,
        )

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
        expect(history.get_by_text(self.ui_text("community_meetings", "Read-only context from earlier meetings. It is not added to these minutes."))).to_be_visible()

        self.capture_checkpoint("discussion-history-desktop", capture_target=history)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        self.capture_checkpoint(
            "discussion-history-mobile",
            {"width": 390, "height": 844},
            history,
        )
        self.page.set_viewport_size({"width": 1440, "height": 1000})

        history.get_by_role("button", name=self.ui_text("community_meetings", "Start without previous notes")).click()
        dialog = self.page.locator(".modal").last
        expect(
            dialog.get_by_text(
                self.ui_text(
                    "community_meetings",
                    "Earlier discussion will be hidden for this point and later continuations. The original notes and this meeting’s notes are preserved.",
                )
            )
        ).to_be_visible()
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Start without previous notes")).click()
        expect(
            history.get_by_text(
                self.ui_text(
                    "community_meetings",
                    "This point starts without earlier discussion. Its notes remain available on the original meeting.",
                )
            )
        ).to_be_visible()
        self.assertTrue(self.record("community.meeting.agenda.item", current_item, ["discard_previous_discussion"])["discard_previous_discussion"])

        history.get_by_role("button", name=self.ui_text("community_meetings", "Show previous notes")).click()
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
        card.get_by_role("button", name=self.ui_text("community_meetings", "Done")).click()
        expect(self.outcome("information")).to_have_text(self.ui_text("community_meetings", "Done"))
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["information"], ["disposition"])["disposition"], "discussed")

    def test_discussion_point_can_be_resolved(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Done")).click()
        expect(self.outcome("discussion")).to_have_text(self.ui_text("community_meetings", "Resolved"))
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["disposition"])["disposition"], "closed")

    def test_postponing_a_point_enables_next_meeting_review(self):
        card = self.card("discussion")
        self.assertEqual(card.locator(".o_live_point_footer").get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).count(), 1)
        self.assertEqual(card.locator(".o_live_point_actions").get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).count(), 0)
        card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).click()
        card.get_by_label(self.ui_text("community_meetings", "Reason for postponing")).fill("Continue next time")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Leave postponed")).click()
        expect(card.get_by_text(self.ui_text("community_meetings", "Will be reviewed at the next meeting"), exact=True)).to_be_visible()
        self.assertTrue(self.record(
            "community.meeting.agenda.item", self.item_ids["discussion"],
            ["review_next_meeting"],
        )["review_next_meeting"])

    def test_live_result_can_be_undone_and_manual_actual_time_is_hidden(self):
        header = self.page.locator(".o_live_header_primary")
        expect(header.get_by_label(self.ui_text("community_meetings", "Minutes secretary"))).to_be_visible()
        expect(self.page.get_by_text(self.ui_text("community_meetings", "Estimated duration"), exact=True)).not_to_be_visible()
        self.page.locator(".o_live_more_details > summary").click()
        expect(self.page.get_by_text(self.ui_text("community_meetings", "Estimated duration"), exact=True)).to_be_visible()
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Done")).click()
        expect(self.outcome("discussion")).to_have_text(self.ui_text("community_meetings", "Resolved"))
        self.assertEqual(card.get_by_label("Actual minutes for this point").count(), 0)
        card.get_by_role("button", name=self.ui_text("community_meetings", "Undo point result")).click()
        reason = card.get_by_label(
            self.ui_text("community_meetings", "Why reopen this point? (optional)")
        )
        reason.fill("We need to revise the conclusion.")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Reopen point")).click()
        expect(self.outcome("discussion")).to_have_text(self.ui_text("community_meetings", "Pending"))
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["disposition"])["disposition"], "open")

    def test_point_timer_navigation_collapses_and_resume_accumulates(self):
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"))).to_be_visible()
        first = self.card("information", begin=False)
        second = self.card("discussion", begin=False)
        first.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        expect(first.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", self.ui_text("community_meetings", "Point in progress"))
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Next agenda point")).click()
        expect(first.locator(".o_live_card_body")).to_be_hidden()
        expect(second.locator(".o_live_card_body")).to_be_visible()
        first_seconds = self.record(
            "community.meeting.agenda.item", self.item_ids["information"],
            ["actual_seconds"],
        )["actual_seconds"]
        self.assertGreaterEqual(first_seconds, 120)

        second.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        expect(second.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", self.ui_text("community_meetings", "Point in progress"))
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Previous agenda point")).click()
        first.get_by_role("button", name=self.ui_text("community_meetings", "Resume point")).click()
        expect(first.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"))).to_be_visible()
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
        first.get_by_role("button", name=self.ui_text("community_meetings", "Pause point")).click()
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
            card.locator(self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes")).count(),
            0,
            "Unexpected editor before Begin: item=%r; editors=%r"
            % (
                self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["has_started", "actual_started_at"]),
                card.locator('[contenteditable="true"]').evaluate_all("els => els.map(el => el.outerHTML)"),
            ),
        )
        self.assertEqual(card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement")).count(), 0)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        expect(card.locator(self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes"))).to_be_visible()
        self.assertTrue(
            card.locator(".o_live_planned").evaluate(
                "el => el.nextElementSibling?.querySelector('.o_live_discussion_notes') !== null"
            ),
            "Discussion notes should sit directly below the point description.",
        )
        record_actions = card.locator(".o_live_record_actions")
        self.assertTrue(
            card.get_by_role("heading", name=self.ui_text("community_meetings", "Agreements and resolutions")).evaluate(
                "el => el.nextElementSibling?.classList.contains('o_live_record_actions')"
            ),
            "The agreement/dissent actions should follow their heading.",
        )
        self.assertEqual(
            [button.inner_text().strip() for button in record_actions.locator("button").all()],
            [
                self.ui_text("community_meetings", "Add agreement"),
                self.ui_text("community_meetings", "Add dissent"),
            ],
        )
        expect(record_actions.get_by_role("button", name=self.ui_text("community_meetings", "Add dissent"))).to_be_visible()
        expect(record_actions.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"))).to_be_visible()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Pause point")).click()
        expect(card.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", self.ui_text("community_meetings", "Point paused"))
        self.assertEqual(
            card.locator(self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes")).count(),
            0,
            "Editor remained after pause: item=%r; editor=%r; card=%r"
            % (
                self.record("community.meeting.agenda.item", self.item_ids["discussion"], ["has_started", "actual_started_at"]),
                card.locator(self.ui_selector("community_meetings", '[contenteditable="true"][aria-label="Discussion notes"]', "Discussion notes")).evaluate_all("els => els.map(el => el.outerHTML)"),
                card.locator(".o_live_card_body").inner_text(),
            ),
        )
        self.assertEqual(card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement")).count(), 0)

        editor = card.locator(self.ui_selector("community_meetings", '[aria-label="Discussion notes"]', "Discussion notes"))
        for _ in range(3):
            card.get_by_role("button", name=self.ui_text("community_meetings", "Resume point")).click()
            expect(card.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"))).to_be_visible()
            self.assertEqual(editor.count(), 1, "Discussion editor was duplicated after resuming a point")
            card.get_by_role("button", name=self.ui_text("community_meetings", "Pause point")).click()
            expect(card.locator(".o_live_point_timer_status")).to_have_attribute("aria-label", self.ui_text("community_meetings", "Point paused"))
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        card = self.card("discussion", begin=False)
        card.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        editor = card.locator(self.ui_selector("community_meetings", '[aria-label="Discussion notes"]', "Discussion notes"))
        expect(editor).to_have_attribute("contenteditable", "true")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pause Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Resume Meeting"))).to_be_visible()
        expect(editor).to_have_count(0)
        expect(card.locator(".o_live_rich_readonly").first).to_be_visible()
        meeting = self.record("community.meeting", self.meeting_id, ["actual_paused_at", "actual_end_datetime"])
        self.assertTrue(meeting["actual_paused_at"])
        self.assertFalse(meeting["actual_end_datetime"])
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Resume Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pause Meeting"))).to_be_visible()
        expect(card.get_by_role("button", name=self.ui_text("community_meetings", "Resume point"))).to_be_visible()
        self.assertFalse(self.record("community.meeting", self.meeting_id, ["actual_paused_at"])["actual_paused_at"])

    def test_minutes_draft_allows_editing_discussion_notes(self):
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["state"])["state"],
            "minutes_draft",
        )
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, self.meeting_id))
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Open Meeting")
        ).click(timeout=30000)
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
        card = self.card("discussion", begin=False)
        expect(card.locator(self.ui_selector("community_meetings", '[aria-label="Discussion notes"]', "Discussion notes"))).to_have_attribute(
            "contenteditable", "true",
        )

    def test_minutes_preview_returns_to_draft_meeting(self):
        capture_path = os.environ.get("MM_CAPTURE_MINUTES_PREVIEW")
        capture_language = os.environ.get("MM_CAPTURE_LANGUAGE")
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        if capture_language:
            localized_html = self.rpc(
                "community.meeting",
                "get_minutes_preview_html",
                [[self.meeting_id]],
                {"context": {"lang": capture_language}},
            )
            preview_labels = (
                "Agenda and discussion",
                "Meeting minutes",
                "Draft — not approved.",
                "This preview reflects current saved meeting data.",
            )
            for source_label in preview_labels:
                localized_label = self.ui_text("community_meetings", source_label)
                self.assertIn(localized_label, localized_html)
                if not capture_language.lower().startswith("en"):
                    self.assertNotIn(source_label, localized_html)
            html_trace = os.environ.get("MM_CAPTURE_PREVIEW_HTML")
            if html_trace:
                Path(html_trace).write_text(localized_html)
        self.page.goto("%s/web#model=community.meeting&id=%s&view_type=form" % (BASE_URL, self.meeting_id))
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Open Meeting")
        ).click(timeout=30000)
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)

        write_trace = LiveWriteTrace(self.page)
        self.addCleanup(write_trace.stop)
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Expand / Collapse all")
        ).click()
        notes_label = self.ui_text("community_meetings", "Discussion notes")
        notes = self.page.locator(
            f'.o_live_discussion_notes [contenteditable="true"][aria-label="{notes_label}"]'
        )
        expect(notes).to_have_count(4)
        notes.nth(0).fill("Se confirma el orden del día y el acta de la sesión anterior.")
        notes.nth(1).fill("Se revisan los avances del proyecto y se acuerda preparar el calendario.")
        self.page.wait_for_timeout(850)
        self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Preview Minutes")
        ).click()
        preview = self.page.locator(".o_community_minutes_preview")
        try:
            expect(preview).to_be_visible(timeout=10000)
        except AssertionError:
            debug_dir = Path(tempfile.gettempdir()) / "mm_minutes_preview_debug"
            if capture_language:
                debug_dir.mkdir(parents=True, exist_ok=True)
                self.capture_checkpoint("minutes-preview-debug-page")
                (debug_dir / "minutes-preview-debug-dom.html").write_text(self.page.locator("body").inner_html())
                (debug_dir / "minutes-preview-debug-trace.json").write_text(json.dumps({
                    "url": self.page.url,
                    "console_errors": self.console_errors[self.errors_before:],
                    "rpc": write_trace.rpc,
                    "body_text": self.page.locator("body").inner_text(),
                }, ensure_ascii=False, indent=2))
            self.fail(
                f"Minutes preview did not render; debug artifacts are in "
                f"{debug_dir if capture_language else 'browser test logs'}; "
                f"console={self.console_errors[self.errors_before:]!r} rpc={write_trace.rpc!r}"
            )
        expect(preview).to_contain_text(
            self.ui_text("community_meetings", "Draft preview · saved content")
        )
        expected_discussion = "Se revisan los avances del proyecto y se acuerda preparar el calendario."
        expect(preview).to_contain_text(expected_discussion)
        self.assertFalse(write_trace.empty_note_writes, "opening the preview must not write untouched empty editors")
        self.assertEqual(write_trace.max_active_note_writes, 1, "writes for a single meeting must be serialized")
        expect(preview.locator(".o_community_minutes_preview_body")).to_be_visible()
        self.page.set_viewport_size({"width": 1440, "height": 2000})
        preview.evaluate("""element => {
            element.style.minHeight = "0";
            element.style.height = "auto";
            element.style.overflow = "visible";
            for (let node = element; node; node = node.parentElement) node.scrollTop = 0;
            window.scrollTo(0, 0);
        }""")
        captured = self.capture_checkpoint(
            "minutes-preview",
            {"width": 1440, "height": 2000},
            preview,
        )
        if capture_path and captured:
            target_path = Path(capture_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(captured[0].read_bytes())
        if capture_language:
            expect(preview).to_contain_text(
                self.ui_text("community_meetings", "Agenda and discussion")
            )
            expect(preview).to_contain_text(self.ui_text("community_meetings", "Meeting date"))
        expect(
            preview.get_by_role(
                "button",
                name=self.ui_text("community_meetings", "Return to meeting to edit"),
            )
        ).to_be_visible()
        self.assertEqual(
            self.record("community.meeting", self.meeting_id, ["state"])["state"],
            "minutes_draft",
        )

        preview.get_by_role(
            "button", name=self.ui_text("community_meetings", "Return to meeting to edit")
        ).click()
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
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click(timeout=30000)
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Expand / Collapse all")).click()
        expect(self.page.locator(self.ui_selector("community_meetings", '[aria-label="Next meeting date"]', "Next meeting date"))).to_be_visible()
        expect(self.page.locator(".o_live_minutes_approval")).to_be_visible()
        expect(self.page.locator(".o_live_minutes_approval")).to_contain_text("Structural previous meeting")

    def test_review_previous_minutes_opens_live_and_approves(self):
        series = self.rpc(
            "community.meeting.series", "create",
            [{"name": "Review minutes series " + uuid.uuid4().hex[:8], "has_minutes_approval_point": True}],
        )
        self.rpc("community.meeting", "write", [[self.meeting_id], {
            "series_id": series,
            "minutes_notes": "<p>Draft text for the previous meeting.</p>",
        }])
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        self.page.goto(
            f"{BASE_URL}/web#model=community.meeting&id={self.meeting_id}&view_type=form"
        )
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Approve Minutes"), exact=True)).to_have_count(0)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Approve Minutes"), exact=True)).to_have_count(0)
        approval_notice = self.ui_text(
            "community_meetings",
            "The assigned minutes secretary can approve earlier minutes during a live meeting "
            "or while preparing minutes for an offline meeting. In a live meeting, the secretary "
            "also needs the Editor role and edit access.",
        )
        expect(self.page.locator(".o_live_minutes_approval")).to_contain_text(approval_notice)
        editor_id = self.rpc("res.users", "search", [[("login", "=", LOGIN)]], {"limit": 1})[0]
        current = self.rpc("community.meeting", "create", [{
            "name": "Review previous minutes", "series_id": series,
            "start_datetime": (datetime.now(timezone.utc) + timedelta(days=3))
            .replace(tzinfo=None, microsecond=0)
            .strftime("%Y-%m-%d %H:%M:%S"),
            "secretary_id": editor_id,
        }])
        discussion_type = self.rpc(
            "community.meeting.agenda.type", "search",
            [[("behavior", "=", "discussion"), ("active", "=", True)]], {"limit": 1},
        )[0]
        running_item = self.rpc("community.meeting.agenda.item", "create", [{
            "meeting_id": current,
            "name": "Keep discussion timer running",
            "kind": "discussion",
            "agenda_type_id": discussion_type,
        }])
        self.rpc("community.meeting", "action_schedule", [[current]])
        self.page.goto(f"{BASE_URL}/web#model=community.meeting&id={current}&view_type=form")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        if self.page.locator(".o_live_expand").first.get_attribute("aria-expanded") == "false":
            self.page.locator(".o_live_expand").first.click()
        approval = self.page.locator(".o_live_minutes_approval")
        expect(approval).to_contain_text(approval_notice)
        expect(approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True)).to_have_count(0)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting"), exact=True).click()
        running_point = self.page.locator(".o_live_agenda_card").filter(has_text="Keep discussion timer running")
        if running_point.locator(".o_live_expand").get_attribute("aria-expanded") == "false":
            running_point.locator(".o_live_expand").click()
        running_point.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        expect(running_point.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"))).to_be_visible()
        running_started_at = self.record(
            "community.meeting.agenda.item", running_item, ["actual_started_at"]
        )["actual_started_at"]
        approval_point = approval.locator("xpath=ancestor::article[1]")
        if approval_point.locator(".o_live_expand").get_attribute("aria-expanded") == "false":
            approval_point.locator(".o_live_expand").click()
        expect(approval).to_contain_text(approval_notice)
        expect(approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True)).to_be_visible()
        approval.get_by_role("button", name=self.ui_text("community_meetings", "Open minutes")).click()
        preview = self.page.locator(".o_community_minutes_preview")
        expect(preview).to_contain_text(self.ui_text("community_meetings", "Draft preview · saved content"))
        expect(preview).to_contain_text("Draft text for the previous meeting.")
        preview.get_by_role(
            "button", name=re.compile("Back to live meeting|Volver a la reunión en vivo", re.IGNORECASE)
        ).click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        approval = self.page.locator(".o_live_minutes_approval")
        self.assertIn(
            "btn-success",
            approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True).get_attribute("class"),
        )

        self.assertEqual(
            self.record("community.meeting.agenda.item", running_item, ["actual_started_at"])["actual_started_at"],
            running_started_at,
            "Reviewing earlier minutes must not stop the active agenda point.",
        )
        running_point = self.page.locator(".o_live_agenda_card").filter(has_text="Keep discussion timer running")
        if running_point.locator(".o_live_expand").get_attribute("aria-expanded") == "false":
            running_point.locator(".o_live_expand").click()
        expect(running_point.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"))).to_be_visible()
        approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True).click()
        expect(
            approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True)
        ).to_have_count(0, timeout=30000)
        self.assertEqual(self.record("community.meeting", self.meeting_id, ["state"])["state"], "approved")
        previous_code = self.record("community.meeting", self.meeting_id, ["code"])["code"]
        self.page.goto(f"{BASE_URL}/web#model=community.meeting&id={current}&view_type=form")
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        self.page.locator(".o_live_agenda_card").first.wait_for(timeout=30000)
        if self.page.locator(".o_live_expand").first.get_attribute("aria-expanded") == "false":
            self.page.locator(".o_live_expand").first.click()
        approval = self.page.locator(".o_live_minutes_approval")
        expect(approval).to_contain_text(self.ui_text("community_meetings", "Approved previous minutes"))
        expect(approval).to_contain_text(previous_code)
        approval.get_by_role("button", name=self.ui_text("community_meetings", "Open minutes")).first.click()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True)).to_have_count(0)
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Approve Minutes"), exact=True)).to_have_count(0)
        expect(self.page.locator(".o_live_rich_readonly").first).to_be_visible()

    def test_held_previous_minutes_are_not_offered_for_approval(self):
        series = self.rpc("community.meeting.series", "create", [{
            "name": "Mixed pending minutes " + uuid.uuid4().hex[:8],
            "has_minutes_approval_point": True,
        }])
        editor_id = self.rpc("res.users", "search", [[("login", "=", LOGIN)]], {"limit": 1})[0]
        current_start = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)

        def create_previous(name, days_before, draft=False):
            start = current_start - timedelta(days=days_before)
            meeting_id = self.rpc("community.meeting", "create", [{
                "name": name,
                "series_id": series,
                "secretary_id": editor_id,
                "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
            }])
            self.rpc("community.meeting", "action_schedule", [[meeting_id]])
            self.rpc("community.meeting", "action_mark_held", [[meeting_id]])
            if draft:
                self.rpc("community.meeting", "action_draft_minutes", [[meeting_id]])
            return meeting_id

        held_name = "Still held " + uuid.uuid4().hex[:6]
        draft_name = "Ready to approve " + uuid.uuid4().hex[:6]
        create_previous(held_name, 2)
        create_previous(draft_name, 1, draft=True)
        current = self.rpc("community.meeting", "create", [{
            "name": "Current mixed approval meeting",
            "series_id": series,
            "secretary_id": editor_id,
            "start_datetime": current_start.strftime("%Y-%m-%d %H:%M:%S"),
        }])
        self.rpc("community.meeting", "action_schedule", [[current]])
        self.rpc("community.meeting", "action_start_meeting", [[current]])
        self.page.goto(f"{BASE_URL}/web#model=community.meeting&id={current}&view_type=form")
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Cancel"), exact=True)).to_have_count(0)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Cancel Meeting"), exact=True)).to_have_count(0)

        approval = self.page.locator(".o_live_minutes_approval")
        expect(approval).to_contain_text(self.ui_text("community_meetings", "Preparation pending"))
        held_row = approval.locator("li").filter(has_text=held_name)
        expect(held_row.get_by_role(
            "button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True,
        )).to_have_count(0)
        ready_row = approval.locator("li").filter(has_text=draft_name)
        expect(ready_row.get_by_role(
            "button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True,
        )).to_be_visible()
        approval.scroll_into_view_if_needed()
        self.capture_checkpoint("minutes-approval-readiness", capture_target=approval)

    def test_live_timing_mode_survives_company_or_series_setting_changes(self):
        series = self.rpc("community.meeting.series", "create", [{
            "name": "Fixed live timing " + uuid.uuid4().hex[:8],
            "time_tracking": "on",
        }])
        self.rpc("community.meeting", "write", [[self.meeting_id], {"series_id": series}])
        open_live_meeting(self.session, self.meeting_id)
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting"), exact=True).click()
        with self.page.expect_response(lambda response: "action_pause_meeting" in response.url):
            self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pause Meeting"), exact=True).click()
        resume = self.page.get_by_role("button", name=self.ui_text("community_meetings", "Resume Meeting"), exact=True)
        expect(resume).to_be_visible()
        paused_at = self.record("community.meeting", self.meeting_id, ["actual_paused_at"])["actual_paused_at"]
        self.assertTrue(paused_at)

        self.rpc("community.meeting.series", "write", [[series], {"time_tracking": "off"}])
        self.page.reload()
        expect(self.page.locator(".o_community_live_meeting")).to_be_visible(timeout=30000)
        resume = self.page.get_by_role("button", name=self.ui_text("community_meetings", "Resume Meeting"), exact=True)
        expect(resume).to_be_visible()
        with self.page.expect_response(lambda response: "action_resume_meeting" in response.url):
            resume.click()
        pause = self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pause Meeting"), exact=True)
        expect(pause).to_be_visible()
        self.assertFalse(self.record("community.meeting", self.meeting_id, ["actual_paused_at"])["actual_paused_at"])

        discussion = self.page.locator(".o_live_agenda_card").filter(has_text="Browser Discussion case")
        if discussion.locator(".o_live_expand").get_attribute("aria-expanded") == "false":
            discussion.locator(".o_live_expand").click()
        with self.page.expect_response(lambda response: "action_start_timing" in response.url):
            discussion.get_by_role("button", name=self.ui_text("community_meetings", "Begin point")).click()
        expect(discussion.get_by_role("button", name=self.ui_text("community_meetings", "Pause point"))).to_be_visible()
        self.assertTrue(self.record(
            "community.meeting.agenda.item", self.item_ids["discussion"], ["actual_started_at"]
        )["actual_started_at"])
        self.capture_checkpoint("live-timing-mode-fixed")

    def test_proposal_admission_requires_review_over_rpc(self):
        login = os.environ.get("ODOO_REVIEWER_LOGIN")
        if not login:
            self.fail("This regression requires a disposable reviewer without Editor")
        series = self.rpc("community.meeting.series", "create", [{
            "name": "Programme planning " + uuid.uuid4().hex[:8],
        }])
        context = self.browser.new_context()
        try:
            page = context.new_page()
            page.goto(BASE_URL + "/web/login" + ((f"?db={DB}") if DB else ""))
            page.locator('input[name="login"]').fill(login)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/odoo**")
            reviewer = self.rpc("res.users", "search", [[("login", "=", login)]], {"limit": 1})[0]
            self.assertFalse(self.rpc("res.users", "has_group", [
                [reviewer], "community_meetings.group_meeting_editor",
            ], page=page))
            point_type = self.rpc("community.meeting.agenda.type", "search", [[
                ("behavior", "=", "discussion"), ("active", "=", True),
            ]], {"limit": 1})[0]
            self.rpc("community.meeting.topic", "propose", [{
                "name": "An intervention proposed by an internal user", "series_id": series,
                "agenda_type_id": point_type,
            }], page=page)
            topic = self.rpc("community.meeting.topic", "search", [[
                ("series_id", "=", series), ("submitted_by_user_id", "=", reviewer),
            ]], page=page)[0]
            for method in ("action_admit", "action_accept_proposal"):
                with self.subTest(method=method), self.assertRaisesRegex(AssertionError, "AccessError"):
                    self.rpc("community.meeting.topic", method, [[topic]], page=page)
            state = self.record("community.meeting.topic", topic, [
                "state", "proposal_status", "responded_by_id", "responded_at",
            ], page=page)
            self.assertEqual(state, {
                "id": topic, "state": "proposed", "proposal_status": "submitted",
                "responded_by_id": False, "responded_at": False,
            })
            self.rpc("community.meeting.topic", "action_admit", [[topic]])
            state = self.record(
                "community.meeting.topic", topic, ["state", "proposal_status", "responded_at"], page=page,
            )
            self.assertEqual(state["state"], "open")
            self.assertEqual(state["proposal_status"], "accepted")
            self.assertTrue(state["responded_at"])
            own_name = (
                "Revisar el programa comunitario"
                if self.effective_locale().startswith("es") else "Review the community programme"
            )
            self.rpc("community.meeting.topic", "propose", [{
                "name": own_name, "series_id": series, "agenda_type_id": point_type,
                "presenter_partner_id": False,
            }])
            own_topic = self.rpc("community.meeting.topic", "search", [[
                ("series_id", "=", series), ("name", "=", own_name),
            ]])[0]
            self.rpc("community.meeting.topic", "action_admit", [[own_topic]])
            self.page.goto(f"{BASE_URL}/web#model=community.meeting.topic&id={own_topic}&view_type=form")
            badge = self.page.locator('.o_field_widget[name="proposal_status"]')
            expect(badge).to_contain_text(self.ui_text("community_meetings", "Accepted"))
            self.capture_checkpoint("proposal-review-status")
        finally:
            context.close()

    def test_legacy_admission_upgrade_status(self):
        topics = self.rpc("community.meeting.topic", "search", [[
            ("name", "=", "An intervention proposed by an internal user"),
            ("proposal_status", "=", "legacy_admitted"),
        ]])
        if not topics:
            self.skipTest("Requires a pre-upgrade admission fixture from the previous version")
        for topic in topics:
            state = self.record("community.meeting.topic", topic, [
                "state", "proposal_status", "responded_by_id", "responded_at",
            ])
            self.assertEqual(state["state"], "open")
            self.assertEqual(state["proposal_status"], "legacy_admitted")
            self.assertFalse(state["responded_by_id"])
            self.assertFalse(state["responded_at"])
        self.page.goto(f"{BASE_URL}/web#model=community.meeting.topic&id={topics[0]}&view_type=form")
        expect(self.page.locator('.o_field_widget[name="proposal_status"]')).to_contain_text(
            self.ui_text("community_meetings", "Admitted without recorded review")
        )
        self.capture_checkpoint("legacy-proposal-review-status")

    def test_addition_deadline_blocks_ui_and_rpc(self):
        series = self.rpc("community.meeting.series", "create", [{
            "name": "Draft-only additions " + uuid.uuid4().hex[:8], "add_point_policy": "draft",
        }])
        self.rpc("community.meeting", "write", [[self.meeting_id], {"series_id": series}])
        open_live_meeting(self.session, self.meeting_id)
        expect(self.page.get_by_role(
            "button", name=self.ui_text("community_meetings", "Add Point"), exact=True,
        )).to_have_count(0)
        for model, method, args in (
            ("community.meeting.agenda.item", "create", [{"meeting_id": self.meeting_id, "name": "Direct bypass"}]),
            ("community.meeting", "write", [
                [self.meeting_id], {"agenda_item_ids": [[0, 0, {"name": "Nested bypass"}]]},
            ]),
            ("community.meeting", "action_add_point_live", [[self.meeting_id]]),
        ):
            with self.subTest(method=method), self.assertRaisesRegex(
                AssertionError, "odoo.exceptions.(UserError|ValidationError)",
            ):
                self.rpc(model, method, args)
        self.assertEqual(self.rpc("community.meeting.agenda.item", "search_count", [[
            ("meeting_id", "=", self.meeting_id), ("name", "in", ["Direct bypass", "Nested bypass"]),
        ]]), 0)
        self.capture_checkpoint("agenda-addition-deadline")

    def test_offline_approver_can_approve_previous_minutes_from_point(self):
        login = os.environ.get("ODOO_REVIEWER_LOGIN")
        if not login:
            self.skipTest("Disposable reviewer is not configured")
        reviewer = self.rpc("res.users", "search", [[("login", "=", login)]], {"limit": 1})[0]
        series = self.rpc(
            "community.meeting.series", "create",
            [{"name": "Offline approval " + uuid.uuid4().hex[:8], "has_minutes_approval_point": True}],
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        previous = self.rpc("community.meeting", "create", [{
            "name": "Offline previous minutes",
            "series_id": series,
            "start_datetime": (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "reader_user_ids": [[4, reviewer]],
        }])
        self.rpc("community.meeting.agenda.item", "create", [{
            "meeting_id": previous, "name": "Previous agenda", "kind": "discussion",
        }])
        self.rpc("community.meeting", "action_schedule", [[previous]])
        self.rpc("community.meeting", "action_mark_held", [[previous]])
        self.rpc("community.meeting", "action_draft_minutes", [[previous]])
        self.rpc("community.meeting", "write", [[self.meeting_id], {
            "series_id": series, "secretary_id": reviewer, "reader_user_ids": [[4, reviewer]],
        }])
        self.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])
        context = self.browser.new_context()
        try:
            page = context.new_page()
            page.goto(BASE_URL + "/web/login" + ((f"?db={DB}") if DB else ""))
            page.locator('input[name="login"]').fill(login)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/odoo**")
            page.goto(f"{BASE_URL}/web#model=community.meeting&id={self.meeting_id}&view_type=form")
            page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
            if page.locator(".o_live_expand").first.get_attribute("aria-expanded") == "false":
                page.locator(".o_live_expand").first.click()
            approval = page.locator(".o_live_minutes_approval")
            expect(approval).to_be_visible()
            expect(approval).to_contain_text(
                self.ui_text("community_meetings", "The assigned minutes secretary can approve earlier minutes during a live meeting "
                "or while preparing minutes for an offline meeting. In a live meeting, the secretary "
                "also needs the Editor role and edit access.")
            )
            expect(approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True)).to_be_visible()
            expect(page.get_by_role("button", name=self.ui_text("community_meetings", "Approve Minutes"), exact=True)).to_have_count(0)
            approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True).click()
            expect(approval.get_by_role("button", name=self.ui_text("community_meetings", "Approve earlier minutes"), exact=True)).to_have_count(0)
            self.assertEqual(self.record("community.meeting", previous, ["state"], page=page)["state"], "approved")
            meeting_state = self.record("community.meeting", self.meeting_id, ["state"], page=page)["state"]
            self.assertEqual(meeting_state, "minutes_draft")
            point = self.rpc("community.meeting.agenda.item", "search_read", [[
                ("meeting_id", "=", self.meeting_id), ("kind", "=", "minutes_approval"),
            ]], {"fields": ["disposition"]}, page=page)[0]
            self.assertEqual(point["disposition"], "closed")
        finally:
            context.close()

    def test_agreement_followup_asks_for_series(self):
        self.retain_carryover = True
        series_name = "Agreement followup series " + str(self.meeting_id)
        series = self.rpc("community.meeting.series", "create", [{"name": series_name}])
        self.rpc("community.meeting", "write", [[self.meeting_id], {"series_id": series}])
        self.page.reload(wait_until="domcontentloaded")
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        card.get_by_placeholder(self.ui_text("community_meetings", "Agreement title")).fill("Follow this agreement")
        card.get_by_placeholder(self.ui_text("community_meetings", "What was agreed?")).fill("Review progress in the next assembly")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Follow up at another meeting")).click()
        dialog = self.page.get_by_role("dialog")
        expect(dialog.locator('.o_field_widget[name="destination_meeting_id"]')).to_have_count(0)
        expect(dialog.locator('.o_field_widget[name="destination_series_id"] input')).to_have_value(series_name)
        dialog.get_by_role("button", name=self.ui_text("community_meetings", "Request Move"), exact=True).click()
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
            page.get_by_role("button", name=self.ui_text("community_meetings", "Open Meeting")).click()
            expect(page.get_by_role("button", name=self.ui_text("community_meetings", "Approve Minutes"), exact=True)).to_be_visible()
            expect(page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"), exact=True)).to_have_count(0)
            expect(page.locator('[contenteditable="true"]')).to_have_count(0)
            expect(page.get_by_text("PRIVATE_EDITORIAL_CONTENT")).to_have_count(0)
            page.get_by_role("button", name=self.ui_text("community_meetings", "Approve Minutes"), exact=True).click()
            expect(page.locator(".o_live_topbar")).to_contain_text(self.ui_text("community_meetings", "Approved"))
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
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Shared native to-do")
        form.get_by_text(self.ui_text("community_meetings", "Assign to multiple people"), exact=False).click()
        form.get_by_label(self.ui_text("community_meetings", "Responsible people")).select_option([str(owner), str(reviewer)])
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        expect(form).to_have_count(0)
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        expect(row.get_by_label(self.ui_text("community_meetings", "Task name"))).to_have_value("Shared native to-do")
        rows = self.rpc("community.meeting.action", "search_read", [[("agenda_item_id", "=", self.item_ids["discussion"])]], {"fields": ["responsible_user_ids", "followup_activity_ids"]})
        self.assertEqual(set(rows[0]["responsible_user_ids"]), {owner, reviewer})
        self.assertEqual(len(rows[0]["followup_activity_ids"]), 2)
        self.page.reload(wait_until="domcontentloaded")
        card = self.card("discussion")
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        expect(row.get_by_label(self.ui_text("community_meetings", "Task name"))).to_have_value("Shared native to-do")
        row.get_by_text(self.ui_text("community_meetings", "Multiple people"), exact=False).click()
        row.get_by_label(self.ui_text("community_meetings", "Responsible people")).select_option([str(owner)])
        expect(row.get_by_label(self.ui_text("community_meetings", "Responsible people")).locator("option:checked")).to_have_count(1)

    def test_convert_menu_matches_available_containers(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Single container follow-up")
        form.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up")).click()
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        allowed = self.rpc(
            "community.meeting", "get_followup_defaults",
            [[self.meeting_id], self.item_ids["discussion"]],
        )["allowed_kinds"]
        expect(row.locator(".o_live_followup_convert")).to_have_count(1 if len(allowed) > 1 else 0)

    def test_header_details_and_add_point_remain_available_while_paused(self):
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Pause Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"))).to_be_visible()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Add Point"))).to_be_enabled()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Edit attendees")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Save attendees"))).to_be_visible()
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Cancel"), exact=True).click()

        self.page.get_by_label(self.ui_text("community_meetings", "Meeting name")).fill("Paused meeting header edited")
        self.page.get_by_label(self.ui_text("community_meetings", "Meeting name")).press("Tab")
        secretary = self.rpc(
            "res.users", "search_read", [[("login", "=", LOGIN)]],
            {"fields": ["name"], "limit": 1},
        )[0]
        self.page.get_by_label(self.ui_text("community_meetings", "Minutes secretary")).select_option(
            value=str(secretary["id"])
        )
        self.page.locator(".o_live_more_details > summary").click()
        self.page.get_by_label(self.ui_text("community_meetings", "Location")).fill("Board Room")
        self.page.get_by_label(self.ui_text("community_meetings", "Location")).press("Tab")
        self.page.get_by_label(self.ui_text("community_meetings", "Meeting link")).fill("https://meet.example.test/board")
        self.page.get_by_label(self.ui_text("community_meetings", "Meeting link")).press("Tab")
        expect(self.page.get_by_role("status")).to_have_text(self.ui_text("community_meetings", "All changes saved"))
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
        expect(self.page.get_by_label(self.ui_text("community_meetings", "Meeting name"))).to_have_value("Paused meeting header edited")
        expect(self.page.get_by_label(self.ui_text("community_meetings", "Location"), exact=True)).to_have_value("Board Room")
        expect(self.page.get_by_label(self.ui_text("community_meetings", "Minutes secretary")).locator("option:checked")).to_have_text(secretary["name"])


    def test_decision_can_be_undone_during_running_meeting(self):
        self.page.get_by_role("button", name=self.ui_text("community_meetings", "Start Meeting")).click()
        expect(self.page.get_by_role("button", name=self.ui_text("community_meetings", "Finish Meeting"))).to_be_visible()
        card = self.card("decision")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        card.get_by_placeholder(self.ui_text("community_meetings", "Agreement title")).fill("Approve during live session")
        card.get_by_placeholder(self.ui_text("community_meetings", "What was agreed?")).fill("Approved pending verification")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Approved"))
        card.get_by_role("button", name=self.ui_text("community_meetings", "Undo point result")).click()
        card.get_by_label(
            self.ui_text("community_meetings", "Why reopen this point? (optional)")
        ).fill("The vote needs checking.")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Reopen point")).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Pending"))
        agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["status"], "limit": 1})[0]
        self.assertEqual(agreement["status"], "withdrawn")

    def test_todo_requires_a_followup_task_before_resolution(self):
        card = self.card("todo")
        button = card.get_by_role("button", name=self.ui_text("community_meetings", "Done"))
        expect(self.outcome("todo")).to_have_text(self.ui_text("community_meetings", "Task required"))
        expect(button).to_be_disabled()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up"), exact=True).click()
        card.get_by_label(self.ui_text("community_meetings", "Task name")).fill("Prepare the requested draft")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add follow-up")).click()
        expect(self.outcome("todo")).to_have_text(self.ui_text("community_meetings", "Task assigned"))
        expect(button).to_be_enabled()

        button.click()
        expect(self.outcome("todo")).to_have_text(self.ui_text("community_meetings", "Resolved"))
        self.assertEqual(self.record("community.meeting.agenda.item", self.item_ids["todo"], ["disposition"])["disposition"], "closed")

    def test_decision_requires_and_uses_agreement_without_direct_edit(self):
        card = self.card("decision")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Pending"))
        title = card.get_by_placeholder(self.ui_text("community_meetings", "Agreement title"))
        title.fill("Approve the decision")
        card.get_by_placeholder(self.ui_text("community_meetings", "What was agreed?")).fill("Approved after discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Approved"))
        agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["decision_outcome", "status"], "limit": 1})[0]
        self.assertEqual((agreement["decision_outcome"], agreement["status"]), ("approved", "active"))
        self.assertEqual(card.get_by_label(self.ui_text("community_meetings", "Decision result"), exact=True).count(), 0)
        card.get_by_role("button", name=self.ui_text("community_meetings", "Undo point result")).click()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Reopen point")).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Pending"))
        card.get_by_role("button", name=self.ui_text("community_meetings", "Resume point")).click()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        card.get_by_placeholder(self.ui_text("community_meetings", "Agreement title")).fill("Reject the decision")
        card.get_by_label(self.ui_text("community_meetings", "New decision result")).select_option("denied")
        card.get_by_placeholder(self.ui_text("community_meetings", "What was agreed?")).fill("Rejected after reconsideration")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Rejected"))
        self.assertFalse(self.console_errors[self.errors_before:], self.console_errors[self.errors_before:])

    def test_postponing_an_approved_decision_withdraws_its_agreement(self):
        card = self.card("decision")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        card.get_by_placeholder(self.ui_text("community_meetings", "Agreement title")).fill("Approve before postponing")
        card.get_by_placeholder(self.ui_text("community_meetings", "What was agreed?")).fill("Approval must be revisited.")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add agreement"), exact=True).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Approved"))
        card.get_by_role("button", name=self.ui_text("community_meetings", "Undo point result")).click()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Reopen point")).click()
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Pending"))
        card.get_by_role("button", name=self.ui_text("community_meetings", "Resume point")).click()
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
        expect(card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point"))).to_be_visible()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).click()
        if expand.get_attribute("aria-expanded") == "false":
            expand.click()
        reason = card.get_by_label(self.ui_text("community_meetings", "Reason for postponing"))
        expect(reason).to_be_visible()
        reason.fill("The approval needs review.")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Leave postponed")).click()
        deadline = time.time() + 8
        point = self.record("community.meeting.agenda.item", self.item_ids["decision"], ["disposition"])
        agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["status"], "limit": 1})[0]
        while time.time() < deadline and point["disposition"] != "deferred":
            time.sleep(0.2)
            point = self.record("community.meeting.agenda.item", self.item_ids["decision"], ["disposition"])
            agreement = self.rpc("community.meeting.resolution", "search_read", [[("agenda_item_id", "=", self.item_ids["decision"])]], {"fields": ["status"], "limit": 1})[0]
        self.assertEqual(point["disposition"], "deferred")
        self.assertEqual(agreement["status"], "withdrawn")
        expect(self.outcome("decision")).to_have_text(self.ui_text("community_meetings", "Postponed"))

    def test_dissent_author_reason_and_statement_are_usable(self):
        card = self.card("discussion")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add dissent")).click()
        author = card.get_by_label(self.ui_text("community_meetings", "Dissent author"))
        kind = card.get_by_label(self.ui_text("community_meetings", "Dissent reason"))
        statement = card.get_by_label(self.ui_text("community_meetings", "Dissent statement"))
        expect(author).to_be_visible()
        expect(statement).to_be_visible()
        author.fill("Ada Lovelace")
        kind.select_option(label=self.ui_text("community_meetings", "Reservation"))
        statement.fill("I disagree with the proposed deadline.")
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add dissent")).click()
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
                card.get_by_role("button", name=self.ui_text("community_meetings", "Postpone agenda point")).click()
                card.get_by_label(self.ui_text("community_meetings", "Reason for postponing")).fill("Waiting for more information.")
                card.get_by_role("button", name=self.ui_text("community_meetings", "Leave postponed")).click()
                expect(self.outcome(kind)).to_have_text(self.ui_text("community_meetings", "Postponed"))
                deadline = time.time() + 8
                saved = self.record("community.meeting.agenda.item", self.item_ids[kind], ["disposition"])
                while time.time() < deadline and saved["disposition"] != "deferred":
                    time.sleep(0.2)
                    saved = self.record("community.meeting.agenda.item", self.item_ids[kind], ["disposition"])
                self.assertEqual(saved["disposition"], "deferred")

    def test_private_note_form_stays_collapsed_until_requested(self):
        card = self.card("discussion")
        expect(card.get_by_label(self.ui_text("community_meetings", "Private editorial note"))).not_to_be_visible()
        card.locator("details").filter(has_text=self.ui_text("community_meetings", "Private editorial notes")).locator("summary").click()
        card.get_by_role("button", name=self.ui_text("community_meetings", "Add private note")).click()
        expect(card.get_by_label(self.ui_text("community_meetings", "Private editorial note"))).to_be_visible()


if __name__ == "__main__":
    unittest.main(verbosity=2)
