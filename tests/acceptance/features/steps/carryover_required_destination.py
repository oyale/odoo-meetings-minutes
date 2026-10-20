"""Browser UI steps for requiring a carryover destination."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("an unfinished agenda point is in a meeting outside a series")
def unfinished_point_without_series(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(
        context.browser_session, f"carryover without destination {uuid4().hex[:8]}"
    )
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.agenda_item_id = fixture.item_ids["discussion"]
    open_live_meeting(context.browser_session, fixture.meeting_id)


@when("I request to move the point without choosing a destination")
def request_carryover_without_destination(context):
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    start_meeting = context.page.get_by_role("button", name="Start Meeting", exact=True)
    if start_meeting.count():
        start_meeting.click()
    expect(context.page.get_by_role("button", name="Finish Meeting", exact=True)).to_be_visible()
    begin_point = card.get_by_role("button", name="Begin point", exact=True)
    if begin_point.count():
        begin_point.click()
    expect(card.get_by_role("button", name="Pause point", exact=True)).to_be_visible()

    card.get_by_role("button", name="Postpone agenda point", exact=True).click()
    card.get_by_label("Reason for postponing", exact=True).fill("Continue in a suitable meeting")
    card.get_by_role("button", name="Move to another meeting", exact=True).click()
    dialog = context.page.get_by_role("dialog").last
    expect(dialog.get_by_role("button", name="Request Move", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Request Move", exact=True).click()


@then("the destination error appears and no carryover is created")
def destination_error_without_carryover(context):
    expect(
        context.page.get_by_text("Choose an explicit destination for meetings outside a series.", exact=True)
    ).to_be_visible()
    transfers = context.browser_session.rpc(
        "community.meeting.carryover",
        "search",
        [[("origin_model", "=", "agenda_item"), ("origin_record_id", "=", context.agenda_item_id)]],
    )
    assert transfers == [], transfers
    item = context.browser_session.rpc(
        "community.meeting.agenda.item",
        "read",
        [[context.agenda_item_id], ["disposition", "deferral_reason"]],
    )[0]
    assert item["disposition"] == "open", item
    assert not item["deferral_reason"], item
