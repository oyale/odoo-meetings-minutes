"""Browser UI steps for the meeting and Calendar cancellation workflow."""

from __future__ import annotations

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


@given("a scheduled meeting has a linked Calendar event")
def scheduled_meeting_has_calendar_event(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "calendar cancellation")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    event_ids = context.browser_session.record("community.meeting", fixture.meeting_id, ["calendar_event_ids"])[
        "calendar_event_ids"
    ]
    assert len(event_ids) == 1, "Scheduled meeting should have one linked Calendar event"
    context.calendar_event_id = event_ids[0]
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)


@when("I cancel the meeting from its form")
def cancel_meeting_from_form(context):
    with context.page.expect_response(lambda response: "/web/dataset/call_button" in response.url) as action_response:
        context.page.locator('button[name="action_cancel"]').click()
    response = action_response.value
    assert response.ok, f"Cancel action failed with HTTP {response.status}"


@then("the meeting is cancelled and the Calendar event is removed")
def cancelled_meeting_has_no_calendar_event(context):
    expect(context.page.locator(".o_form_view")).to_be_visible()
    meeting = context.browser_session.record("community.meeting", context.meeting_id, ["state", "calendar_event_ids"])
    assert meeting["state"] == "cancelled", meeting
    assert not meeting["calendar_event_ids"], "Cancelled meeting still links a Calendar event"
    assert context.browser_session.rpc("calendar.event", "search", [[("id", "=", context.calendar_event_id)]]) == [], (
        "Cancelled meeting's Calendar event still exists"
    )
