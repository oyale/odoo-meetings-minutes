"""Browser UI steps for meeting-to-Calendar event synchronization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


def expect_location(page, value):
    field = page.locator('.o_field_widget[name="location"]')
    input_field = field.locator("input")
    if input_field.count():
        expect(input_field).to_have_value(value)
    else:
        expect(field).to_contain_text(value)


@given("a scheduled meeting has an eligible linked Calendar event")
def scheduled_meeting_has_calendar_event(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "calendar sync")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    user_ids = context.browser_session.rpc(
        "res.users",
        "search",
        [[("login", "=", context.acceptance_config.login)]],
        {"limit": 1},
    )
    if not user_ids:
        raise AssertionError("The acceptance user could not be resolved")
    user = context.browser_session.record("res.users", user_ids[0], ["partner_id", "tz"])
    organizer_partner_id = user["partner_id"][0]
    attendee_users = context.browser_session.rpc(
        "res.users",
        "search",
        [[("share", "=", False), ("id", "!=", user_ids[0])]],
        {"limit": 1},
    )
    if not attendee_users:
        raise AssertionError("No second internal user is available as a Calendar attendee")
    context.calendar_attendee_id = context.browser_session.record("res.users", attendee_users[0], ["partner_id"])[
        "partner_id"
    ][0]
    context.browser_session.rpc(
        "community.meeting", "write", [[fixture.meeting_id], {"attendee_partner_ids": [(4, organizer_partner_id)]}]
    )
    context.calendar_location = f"Acceptance room {uuid4().hex[:6]}"
    # Stay away from a daylight-saving transition so the browser's local-time
    # editor and Odoo's UTC datetime representation agree on the exact instant.
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    context.calendar_expected_start = start.strftime("%Y-%m-%d %H:%M:%S")
    context.calendar_start = (
        start.astimezone(ZoneInfo(user["tz"] or "UTC")).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    )
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    assert_meeting_form(context.page, context.meeting_name)
    event_ids = context.browser_session.rpc(
        "calendar.event", "search", [[("community_meeting_id", "=", fixture.meeting_id)]]
    )
    assert len(event_ids) == 1, event_ids
    context.calendar_event_id = event_ids[0]


@when("I change the meeting time, location and attendees in its form")
def change_meeting_calendar_fields(context):
    edit_button = context.page.locator(".o_form_button_edit")
    if edit_button.count():
        edit_button.click()
    form = context.page.locator(".o_form_view")
    form.locator('.o_field_widget[name="start_datetime"] input').fill(context.calendar_start)
    attendees = form.locator('.o_field_widget[name="attendee_partner_ids"]')
    attendees.locator("input").last.fill(
        context.browser_session.record("res.partner", context.calendar_attendee_id, ["name"])["name"]
    )
    context.page.get_by_role("option").filter(
        has_text=context.browser_session.record("res.partner", context.calendar_attendee_id, ["name"])["name"]
    ).click()
    location = form.locator('.o_field_widget[name="location"] input')
    location.fill(context.calendar_location)
    location.press("Tab")
    expect(location).to_have_value(context.calendar_location)
    with (
        context.page.expect_request(lambda request: "/community.meeting/web_save" in request.url) as save_request,
        context.page.expect_response(lambda response: "/community.meeting/web_save" in response.url) as save_response,
    ):
        context.page.locator(".o_form_button_save").click()
    payload = save_request.value.post_data_json
    saved = save_response.value.json()["result"][0]
    assert context.calendar_location in str(payload), payload
    assert saved["location"] == context.calendar_location, saved


@then("the linked Calendar event shows the updated details")
def linked_calendar_event_has_updated_fields(context):
    with context.page.expect_response(lambda response: "/community.meeting/web_read" in response.url):
        context.page.reload(wait_until="domcontentloaded")
    expect_location(context.page, context.calendar_location)
    with context.page.expect_response(lambda response: "/calendar.event/web_read" in response.url):
        context.page.goto(
            f"{context.acceptance_config.base_url}/web#model=calendar.event&id={context.calendar_event_id}&view_type=form"
        )
    expect_location(context.page, context.calendar_location)
    meeting = context.browser_session.record(
        "community.meeting", context.meeting_id, ["start_datetime", "location", "attendee_partner_ids"]
    )
    event = context.browser_session.record(
        "calendar.event", context.calendar_event_id, ["start", "location", "partner_ids", "community_meeting_id"]
    )
    assert meeting["start_datetime"] == context.calendar_expected_start, meeting
    assert meeting["location"] == context.calendar_location, meeting
    assert context.calendar_attendee_id in meeting["attendee_partner_ids"], meeting
    assert event["start"] == context.calendar_expected_start, event
    assert event["location"] == context.calendar_location, event
    assert context.calendar_attendee_id in event["partner_ids"], event
    assert event["community_meeting_id"][0] == context.meeting_id, event
