"""Browser UI steps for adding a point during a live meeting."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("a running meeting accepts new agenda points")
def running_meeting_accepts_new_points(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "live agenda addition")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.point_name = f"Live discussion {uuid4().hex[:8]}"
    context.browser_session.rpc("community.meeting", "action_start_meeting", [[fixture.meeting_id]])
    context.requires_database_drop = True
    open_live_meeting(context.browser_session, fixture.meeting_id)


@when("I add a discussion point from the live agenda")
def add_discussion_point_from_live_agenda(context):
    page = context.page
    page.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Add Point'), exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    dialog.locator('.o_field_widget[name="name"] input').fill(context.point_name)
    dialog.get_by_role("radio", name=context.browser_session.ui_text('community_meetings', 'Discussion'), exact=True).click()
    dialog.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Add point'), exact=True).click()
    expect(dialog).to_have_count(0)


@then("the new point appears in the live agenda and is saved on the meeting")
def new_point_is_visible_and_persisted(context):
    open_live_meeting(context.browser_session, context.meeting_id)
    card = context.page.locator(".o_live_agenda_card").filter(has_text=context.point_name)
    expect(card).to_be_visible()
    records = context.browser_session.rpc(
        "community.meeting.agenda.item",
        "search_read",
        [[("meeting_id", "=", context.meeting_id), ("name", "=", context.point_name)]],
        {"fields": ["meeting_id", "name", "kind", "agenda_type_id"]},
    )
    assert len(records) == 1, records
    assert records[0]["meeting_id"] == [
        context.meeting_id,
        context.browser_session.record("community.meeting", context.meeting_id, ["name"])["name"],
    ]
    assert records[0]["kind"] == "discussion", records[0]
    assert records[0]["agenda_type_id"], records[0]
