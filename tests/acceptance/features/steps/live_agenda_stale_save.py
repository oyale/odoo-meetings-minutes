"""Browser UI steps for rejecting stale live-agenda writes."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("the Add Point form is open while a scheduled meeting accepts additions")
def add_point_form_open(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "stale add point")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.stale_point_name = f"Stale point {uuid4().hex[:8]}"
    open_live_meeting(context.browser_session, fixture.meeting_id)
    context.page.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Add Point"), exact=True
    ).click()
    dialog = context.page.get_by_role("dialog").last
    dialog.locator('.o_field_widget[name="name"] input').fill(context.stale_point_name)
    context.stale_form = dialog
    context.stale_page = context.browser_session.new_page()
    context.stale_page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    context.requires_database_drop = True


@when("another session finishes the meeting before I save the point")
def other_session_finishes_meeting(context):
    context.browser_session.rpc(
        "community.meeting", "action_mark_held", [[context.meeting_id]], page=context.stale_page
    )
    assert (
        context.browser_session.record("community.meeting", context.meeting_id, ["state"], page=context.stale_page)[
            "state"
        ]
        == "held"
    )
    context.stale_form.locator('button[name="action_save"]').click()


@then("the stale save is rejected and no new agenda point exists")
def stale_point_is_rejected(context):
    expect(
        context.page.get_by_text(
            context.browser_session.ui_text(
                "community_meetings", "New points cannot be added to this meeting anymore."
            ),
            exact=True,
        )
    ).to_be_visible()
    count = context.browser_session.rpc(
        "community.meeting.agenda.item",
        "search_count",
        [[("meeting_id", "=", context.meeting_id), ("name", "=", context.stale_point_name)]],
    )
    assert count == 0, count
