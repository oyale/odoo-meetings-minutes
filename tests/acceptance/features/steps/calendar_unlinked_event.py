"""Browser UI steps for unlinked Calendar event behavior."""

from uuid import uuid4

from behave import given, then, when
from playwright.sync_api import expect


@given("an unlinked Calendar event is open")
def unlinked_calendar_event_open(context):
    session = context.browser_session
    suffix = uuid4().hex[:8]
    context.calendar_event_id = session.rpc(
        "calendar.event",
        "create",
        [
            {
                "name": f"Acceptance unlinked event {suffix}",
                "start": "2030-04-01 10:00:00",
                "stop": "2030-04-01 11:00:00",
            }
        ],
    )
    context.unlinked_calendar_event_fixture_id = context.calendar_event_id
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=calendar.event&id={context.calendar_event_id}&view_type=form"
    )
    expect(context.page.locator(".o_form_view")).to_contain_text(f"Acceptance unlinked event {suffix}")


@when("I check whether the event offers Open Meeting")
def check_open_meeting_availability(context):
    context.open_meeting_button_count = context.page.locator('button[name="action_open_community_meeting"]').count()


@then("the action is unavailable and the event remains unlinked")
def unlinked_event_has_no_open_meeting_action(context):
    expect(context.page.locator('button[name="action_open_community_meeting"]')).to_have_count(0)
    event = context.browser_session.record("calendar.event", context.calendar_event_id, ["community_meeting_id"])
    assert not event["community_meeting_id"], event
    assert context.open_meeting_button_count == 0
