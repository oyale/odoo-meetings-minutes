"""Browser UI steps for navigation across the meeting/Calendar relationship."""

from __future__ import annotations

from behave import then, when
from playwright.sync_api import expect


def _open_form(page, expected_text: str):
    form = page.locator(".o_form_view").filter(has_text=expected_text).last
    expect(form).to_be_visible(timeout=30000)
    return form


@when("I open the Calendar event from the meeting form")
def open_calendar_event_from_meeting(context):
    with context.page.expect_response(lambda response: "/web/dataset/call_button" in response.url) as action_response:
        context.page.locator('button[name="action_open_calendar_event"]').click()
    response = action_response.value
    assert response.ok, f"Open Calendar action failed with HTTP {response.status}"
    _open_form(context.page, context.meeting_name)
    expect(context.page.locator('button[name="action_open_community_meeting"]')).to_be_visible()


@then("the Calendar event is linked to this meeting")
def calendar_event_links_to_meeting(context):
    event = context.browser_session.record(
        "calendar.event", context.calendar_event_id, ["community_meeting_id", "name"]
    )
    assert event["community_meeting_id"] == [context.meeting_id, context.meeting_name]
    expect(context.page.locator(".o_form_view").last).to_contain_text(context.meeting_name)


@when("I open the meeting from the Calendar event")
def open_meeting_from_calendar_event(context):
    with context.page.expect_response(lambda response: "/web/dataset/call_button" in response.url) as action_response:
        context.page.locator('button[name="action_open_community_meeting"]').click()
    response = action_response.value
    assert response.ok, f"Open Meeting action failed with HTTP {response.status}"
    _open_form(context.page, context.meeting_name)


@then("the same meeting form is open")
def same_meeting_form_is_open(context):
    form = _open_form(context.page, context.meeting_name)
    expect(form).to_contain_text(context.meeting_name)
    expect(context.page.locator('button[name="action_open_calendar_event"]').last).to_be_visible()


@when("I reopen its Calendar event from the meeting form")
def reopen_calendar_event_from_meeting(context):
    with context.page.expect_response(lambda response: "/web/dataset/call_button" in response.url) as action_response:
        context.page.locator('button[name="action_open_calendar_event"]').last.click()
    response = action_response.value
    assert response.ok, f"Reopen Calendar action failed with HTTP {response.status}"
    _open_form(context.page, context.meeting_name)
    expect(context.page.locator('button[name="action_open_community_meeting"]')).to_be_visible()


@then("the same Calendar event form is open")
def same_calendar_event_form_is_open(context):
    event = context.browser_session.record("community.meeting", context.meeting_id, ["calendar_event_ids"])[
        "calendar_event_ids"
    ]
    assert event == [context.calendar_event_id]
    _open_form(context.page, context.meeting_name)
    expect(context.page.locator('button[name="action_open_community_meeting"]')).to_be_visible()
