"""Reusable meeting records and navigation for browser acceptance tests."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from playwright.sync_api import Page, expect

from browser_support.odoo_browser import OdooBrowserSession


@dataclass
class LiveMeetingFixture:
    session: OdooBrowserSession
    meeting_id: int
    item_ids: dict[str, int]

    @classmethod
    def create_draft_meeting(cls, session: OdooBrowserSession, label: str) -> LiveMeetingFixture:
        unique_name = f"Browser {label} {uuid.uuid4().hex[:8]}"
        meeting_id = session.rpc("community.meeting", "create", [{"name": unique_name}])
        return cls(session, meeting_id, {})

    @classmethod
    def create_minutes_draft_without_agenda(cls, session: OdooBrowserSession, label: str) -> LiveMeetingFixture:
        start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
        unique_name = f"Browser {label} {uuid.uuid4().hex[:8]}"
        meeting_id = session.rpc(
            "community.meeting",
            "create",
            [{"name": unique_name, "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S")}],
        )
        session.rpc("community.meeting", "action_schedule", [[meeting_id]])
        session.rpc("community.meeting", "action_mark_held", [[meeting_id]])
        session.rpc("community.meeting", "action_draft_minutes", [[meeting_id]])
        return cls(session, meeting_id, {})

    @classmethod
    def create_scheduled_live_meeting(cls, session: OdooBrowserSession, label: str) -> LiveMeetingFixture:
        start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
        unique_name = f"Browser {label} {uuid.uuid4().hex[:8]}"
        meeting_id = session.rpc(
            "community.meeting",
            "create",
            [
                {
                    "name": unique_name,
                    "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
                }
            ],
        )
        item_ids: dict[str, int] = {}
        fixture = cls(session, meeting_id, item_ids)
        try:
            for kind in ("information", "discussion", "decision", "todo"):
                agenda_types = session.rpc(
                    "community.meeting.agenda.type",
                    "search",
                    [[("behavior", "=", kind), ("active", "=", True)]],
                    {"limit": 1},
                )
                if not agenda_types:
                    raise AssertionError(f"No active agenda type for {kind}")
                item_ids[kind] = session.rpc(
                    "community.meeting.agenda.item",
                    "create",
                    [
                        {
                            "meeting_id": meeting_id,
                            "name": f"Browser {kind.title()} case",
                            "kind": kind,
                            "agenda_type_id": agenda_types[0],
                        }
                    ],
                )
            session.rpc("community.meeting", "action_schedule", [[meeting_id]])
        except Exception:
            fixture.cleanup()
            raise
        return fixture

    def prepare_minutes_draft(self) -> None:
        self.session.rpc("community.meeting", "action_mark_held", [[self.meeting_id]])
        self.session.rpc("community.meeting", "action_draft_minutes", [[self.meeting_id]])

    def cleanup(self) -> bool:
        state = self.session.record("community.meeting", self.meeting_id, ["state"])["state"]
        if state not in ("draft", "scheduled"):
            # The workflow intentionally disallows deleting held or draft-minute records.
            return False
        transfers = self.session.rpc(
            "community.meeting.carryover",
            "search",
            [
                [
                    "|",
                    ("origin_meeting_id", "=", self.meeting_id),
                    ("destination_meeting_id", "=", self.meeting_id),
                ]
            ],
        )
        if transfers:
            return False
        self.session.rpc("community.meeting", "action_cancel", [[self.meeting_id]])
        resolutions = self.session.rpc(
            "community.meeting.resolution",
            "search",
            [[("meeting_id", "=", self.meeting_id)]],
        )
        if resolutions:
            self.session.rpc("community.meeting.resolution", "unlink", [resolutions])
        self.session.rpc("community.meeting", "unlink", [[self.meeting_id]])
        return True


def open_live_meeting(
    session: OdooBrowserSession,
    meeting_id: int,
    *,
    page: Page | None = None,
    timeout: int = 30000,
    expand_all: bool = True,
) -> Page:
    page = page or session.page
    page.goto(
        urljoin(
            session.base_url + "/",
            f"web#model=community.meeting&id={meeting_id}&view_type=form",
        )
    )
    page.get_by_role("button", name=re.compile(r"^(Open Meeting|Abrir reunión)$", re.IGNORECASE)).click(
        timeout=timeout
    )
    try:
        page.locator(".o_live_agenda_card").first.wait_for(timeout=timeout)
    except Exception as error:
        raise AssertionError(
            f"Live meeting did not render agenda cards; browser errors: {session.console_errors!r}; URL: {page.url}"
        ) from error
    if expand_all:
        page.get_by_role(
            "button",
            name=re.compile(
                r"^(Expand \/ Collapse all|Desplegar \/ plegar todo)$",
                re.IGNORECASE,
            ),
        ).click()
    return page


def assert_meeting_form(page: Page, meeting_name: str) -> None:
    expect(page.locator(".o_form_view")).to_be_visible(timeout=30000)
    expect(page.locator(".o_form_view")).to_contain_text(meeting_name)
