"""Browser UI steps for discussion history across point continuations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import assert_meeting_form, open_live_meeting
from playwright.sync_api import expect

SOURCE_NOTES = "Debate context that should be hidden from later meetings"


def _meeting(session, name: str, start: datetime) -> int:
    return session.rpc(
        "community.meeting",
        "create",
        [{"name": name, "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S")}],
    )


def _discussion_item(session, meeting_id: int, name: str) -> int:
    type_ids = session.rpc(
        "community.meeting.agenda.type",
        "search",
        [[("behavior", "=", "discussion"), ("active", "=", True)]],
        {"limit": 1},
    )
    if not type_ids:
        raise AssertionError("No active discussion agenda type is configured")
    return session.rpc(
        "community.meeting.agenda.item",
        "create",
        [
            {
                "meeting_id": meeting_id,
                "name": name,
                "kind": "discussion",
                "agenda_type_id": type_ids[0],
            }
        ],
    )


def _carryover(session, source_item_id: int, destination_meeting_id: int) -> int:
    return session.rpc(
        "community.meeting.carryover",
        "create",
        [
            {
                "origin_model": "agenda_item",
                "origin_record_id": source_item_id,
                "destination_meeting_id": destination_meeting_id,
            }
        ],
    )


def _open_agenda_card(context, meeting_id: int, item_id: int):
    open_live_meeting(
        context.browser_session,
        meeting_id,
        page=context.page,
        expand_all=False,
    )
    card = context.page.locator(f"#agenda-card-{item_id}")
    expect(card).to_be_visible(timeout=20000)
    body = card.locator(".o_live_card_body")
    expand_button = card.locator(".o_live_expand")
    if expand_button.get_attribute("aria-expanded") != "true":
        expand_button.click()
    expect(body).to_be_visible()
    return card


def _accept_pending_point(context) -> None:
    page = context.page
    base_url = context.acceptance_config.base_url
    page.goto(f"{base_url}/web#model=community.meeting&id={context.later_meeting_id}&view_type=form")
    assert_meeting_form(page, context.later_meeting_name)
    page.get_by_role("tab", name=context.browser_session.ui_text("community_meetings", "Incoming Carryovers")).click()
    incoming = page.locator('.o_field_widget[name="incoming_carryover_ids"]')
    row = incoming.locator("tr.o_data_row").filter(has_text=context.point_name)
    expect(row).to_be_visible()
    row.locator('button[name="action_accept"]').click()
    expect(row).to_contain_text(context.browser_session.ui_text("community_meetings", "Accepted"))


@given("an accepted point has earlier debate notes and a destination meeting")
def accepted_point_has_earlier_debate_notes(context):
    session = context.browser_session
    context.discussion_history_fixture = True
    label = uuid4().hex[:8]
    base = datetime.now(timezone.utc).replace(microsecond=0)
    source_name = f"Browser discussion source {label}"
    current_name = f"Browser discussion continuation {label}"
    later_name = f"Browser later discussion {label}"
    context.point_name = f"Browser discussion point {label}"
    context.source_meeting_id = _meeting(session, source_name, base + timedelta(days=1))
    context.current_meeting_id = _meeting(session, current_name, base + timedelta(days=2))
    context.later_meeting_id = _meeting(session, later_name, base + timedelta(days=3))
    context.source_meeting_name = source_name
    context.current_meeting_name = current_name
    context.later_meeting_name = later_name

    context.source_item_id = _discussion_item(session, context.source_meeting_id, context.point_name)
    session.rpc(
        "community.meeting.agenda.item",
        "write",
        [[context.source_item_id], {"discussion_notes": f"<p>{SOURCE_NOTES}</p>"}],
    )
    session.rpc(
        "community.meeting",
        "action_schedule",
        [[context.source_meeting_id, context.current_meeting_id, context.later_meeting_id]],
    )
    first_transfer = _carryover(session, context.source_item_id, context.current_meeting_id)
    session.rpc("community.meeting.carryover", "action_accept", [[first_transfer]])
    context.current_item_id = session.record("community.meeting.carryover", first_transfer, ["destination_item_id"])[
        "destination_item_id"
    ][0]
    later_transfer = _carryover(session, context.current_item_id, context.later_meeting_id)
    context.later_transfer_id = later_transfer
    context.current_source_notes = session.record(
        "community.meeting.agenda.item", context.source_item_id, ["discussion_notes"]
    )["discussion_notes"]

    card = _open_agenda_card(context, context.current_meeting_id, context.current_item_id)
    history = card.locator(".o_live_previous_discussion")
    expect(history).to_be_visible()
    expect(history).to_contain_text(SOURCE_NOTES)


@then("its earlier notes are read-only context")
def earlier_notes_are_read_only(context):
    card = context.page.locator(f"#agenda-card-{context.current_item_id}")
    history = card.locator(".o_live_previous_discussion")
    expect(history).to_be_visible()
    source_context = history.locator(".o_live_previous_discussion_content").filter(has_text=SOURCE_NOTES)
    expect(source_context).to_be_visible()
    expect(source_context.locator('[contenteditable="true"]')).to_have_count(0)
    expect(source_context.get_by_role("textbox")).to_have_count(0)


@when("I hide the previous discussion")
def hide_previous_discussion(context):
    history = context.page.locator(f"#agenda-card-{context.current_item_id} .o_live_previous_discussion")
    history.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Start without previous notes")
    ).click()
    dialog = context.page.locator(".modal").last
    expect(dialog).to_contain_text("The original notes and this meeting’s notes are preserved.")
    dialog.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Start without previous notes")
    ).click()
    expect(history).to_contain_text("This point starts without earlier discussion.")


@when("I start the current meeting and point")
def start_current_meeting_and_point(context):
    start_meeting = context.page.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Start Meeting")
    )
    expect(start_meeting).to_be_visible()
    start_meeting.click()
    card = context.page.locator(f"#agenda-card-{context.current_item_id}")
    begin_point = card.get_by_role("button", name=context.browser_session.ui_text("community_meetings", "Begin point"))
    expect(begin_point).to_be_visible()
    begin_point.click()
    expect(
        card.get_by_role("button", name=context.browser_session.ui_text("community_meetings", "Pause point"))
    ).to_be_visible()


@then("the source notes are preserved and hidden on the current point")
def source_notes_are_preserved(context):
    history = context.page.locator(f"#agenda-card-{context.current_item_id} .o_live_previous_discussion")
    expect(history.get_by_text(SOURCE_NOTES)).to_have_count(0)
    source_item = context.browser_session.record(
        "community.meeting.agenda.item",
        context.source_item_id,
        ["discussion_notes"],
    )
    assert source_item["discussion_notes"] == context.current_source_notes
    current_item = context.browser_session.record(
        "community.meeting.agenda.item",
        context.current_item_id,
        ["discard_previous_discussion"],
    )
    assert current_item["discard_previous_discussion"] is True


@when("I accept the point in the later meeting")
def accept_point_in_later_meeting(context):
    _accept_pending_point(context)
    context.later_item_id = context.browser_session.record(
        "community.meeting.carryover",
        context.later_transfer_id,
        ["destination_item_id"],
    )["destination_item_id"][0]


@then("its previous discussion does not include the hidden source notes")
def later_point_hides_source_notes(context):
    card = _open_agenda_card(context, context.later_meeting_id, context.later_item_id)
    history = card.locator(".o_live_previous_discussion")
    expect(history).to_be_visible()
    expect(history.get_by_text(SOURCE_NOTES)).to_have_count(0)


@when("I restore the previous discussion on the current point")
def restore_previous_discussion(context):
    card = _open_agenda_card(context, context.current_meeting_id, context.current_item_id)
    history = card.locator(".o_live_previous_discussion")
    expect(history).to_be_visible()
    expect(history).to_contain_text("This point starts without earlier discussion.")
    history.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Show previous notes")
    ).click()
    expect(history).to_be_visible()
    expect(history).to_contain_text(SOURCE_NOTES)
    source_item = context.browser_session.record(
        "community.meeting.agenda.item",
        context.current_item_id,
        ["discard_previous_discussion"],
    )
    assert source_item["discard_previous_discussion"] is False


@then("the later continuation shows the restored source notes")
def later_continuation_shows_restored_notes(context):
    card = _open_agenda_card(context, context.later_meeting_id, context.later_item_id)
    history = card.locator(".o_live_previous_discussion")
    expect(history).to_be_visible()
    expect(history).to_contain_text(SOURCE_NOTES)
