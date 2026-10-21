"""Browser UI steps for requesting and accepting an agenda carryover."""

from __future__ import annotations

from datetime import datetime, timedelta

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("an unfinished agenda point and an eligible destination meeting exist")
def unfinished_point_and_destination_exist(context):
    source = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "carryover source")
    destination = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "carryover destination")
    source_start = context.browser_session.record("community.meeting", source.meeting_id, ["start_datetime"])[
        "start_datetime"
    ]
    later_start = (datetime.strptime(source_start, "%Y-%m-%d %H:%M:%S") + timedelta(days=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    context.browser_session.rpc(
        "community.meeting", "write", [[destination.meeting_id], {"start_datetime": later_start}]
    )
    context.live_meeting_fixture = source
    context.source_fixture = source
    context.destination_fixture = destination
    context.source_item_id = source.item_ids["discussion"]
    context.source_meeting_id = source.meeting_id
    context.destination_meeting_id = destination.meeting_id
    context.destination_name = context.browser_session.record("community.meeting", destination.meeting_id, ["name"])[
        "name"
    ]
    context.requires_database_drop = True
    open_live_meeting(context.browser_session, source.meeting_id)


@when("I request to move the point to that meeting")
def request_point_carryover(context):
    card = context.page.locator(f"#agenda-card-{context.source_item_id}")
    start_meeting = context.page.get_by_role("button", name="Start Meeting", exact=True)
    if start_meeting.count():
        start_meeting.click()
    expect(context.page.get_by_role("button", name="Finish Meeting", exact=True)).to_be_visible()
    begin_point = card.get_by_role("button", name="Begin point", exact=True)
    if begin_point.count():
        begin_point.click()
    expect(card.get_by_role("button", name="Pause point", exact=True)).to_be_visible()
    card.get_by_role("button", name="Postpone agenda point", exact=True).click()
    card.get_by_label("Reason for postponing", exact=True).fill("Continue in the destination meeting")
    card.get_by_role("button", name="Move to another meeting", exact=True).click()

    dialog = context.page.get_by_role("dialog").last
    destination = dialog.locator('.o_field_widget[name="destination_meeting_id"] input')
    destination.fill(context.destination_name)
    dialog.get_by_role("option", name=context.destination_name, exact=True).click()
    with context.page.expect_response(
        lambda response: "/call_button/community.meeting.carryover.wizard/action_request" in response.url
    ):
        dialog.get_by_role("button", name="Request Move", exact=True).click()
    expect(dialog).not_to_be_visible()

    transfers = context.browser_session.rpc(
        "community.meeting.carryover",
        "search_read",
        [[("origin_record_id", "=", context.source_item_id), ("origin_model", "=", "agenda_item")]],
        {"fields": ["id", "status", "destination_meeting_id", "origin_agenda_item_id"]},
    )
    assert len(transfers) == 1, {"source_item_id": context.source_item_id, "transfers": transfers}
    transfer = transfers[0]
    assert transfer["destination_meeting_id"][0] == context.destination_meeting_id, transfer
    assert transfer["origin_agenda_item_id"][0] == context.source_item_id, transfer
    assert transfer["status"] in ("pending", "proposed"), transfer
    context.carryover_id = transfer["id"]


@then("I accept it there and the linked point appears in that meeting")
def destination_editor_accepts_point(context):
    open_live_meeting(context.browser_session, context.destination_meeting_id)
    incoming = context.page.get_by_role("region", name="Points to continue")
    with context.page.expect_response(lambda response: "/community.meeting.carryover/action_accept" in response.url):
        incoming.get_by_role("button", name="Accept").click()

    destination_item = context.browser_session.rpc(
        "community.meeting.carryover", "read", [[context.carryover_id], ["status", "destination_item_id"]]
    )[0]
    assert destination_item["status"] == "accepted", destination_item
    destination_item_id = destination_item["destination_item_id"][0]
    item = context.browser_session.record(
        "community.meeting.agenda.item", destination_item_id, ["meeting_id", "carryover_id", "name"]
    )
    assert item["meeting_id"][0] == context.destination_meeting_id, item
    assert item["carryover_id"][0] == context.carryover_id, item
    expect(context.page.locator(f"#agenda-card-{destination_item_id}")).to_contain_text(item["name"])


@then("I dismiss the carryover from the destination meeting")
def editor_dismisses_carryover(context):
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.destination_meeting_id}&view_type=form"
    )
    row = context.page.locator('.o_field_widget[name="pending_carryover_ids"] tr.o_data_row').filter(
        has_text=context.browser_session.record(
            "community.meeting.agenda.item", context.source_item_id, ["name"]
        )["name"]
    )
    expect(row).to_be_visible()
    with context.page.expect_response(
        lambda response: "/community.meeting.carryover/action_dismiss" in response.url
    ):
        row.get_by_role("button", name="Dismiss", exact=True).click()
    status = context.browser_session.record("community.meeting.carryover", context.carryover_id, ["status"])[
        "status"
    ]
    assert status == "dismissed", status
