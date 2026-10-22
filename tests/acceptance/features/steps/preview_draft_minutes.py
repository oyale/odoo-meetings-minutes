"""Browser UI steps for saved draft-minutes preview."""

from __future__ import annotations

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


@given("I can read the meeting")
def meeting_is_readable(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "acceptance preview")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)


@given("the meeting is Held or has draft minutes")
def meeting_has_previewable_minutes(context):
    context.live_meeting_fixture.prepare_minutes_draft()
    meeting = context.browser_session.record(
        "community.meeting",
        context.meeting_id,
        ["name", "state", "write_date"],
    )
    item_id = context.live_meeting_fixture.item_ids["discussion"]
    item = context.browser_session.record(
        "community.meeting.agenda.item",
        item_id,
        ["name", "discussion_notes", "write_date"],
    )
    rendered = context.browser_session.rpc("community.meeting", "get_minutes_preview_html", [[context.meeting_id]])
    context.saved_draft_before_preview = (meeting, item, rendered)
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )


@when("I choose Preview Minutes")
def choose_preview_minutes(context):
    context.page.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Preview Minutes"), exact=True
    ).click()


@then("the saved minutes open in a read-only preview")
def preview_is_read_only(context):
    preview = context.page.locator(".o_community_minutes_preview")
    expect(preview).to_contain_text(
        context.browser_session.ui_text("community_meetings", "Draft preview · saved content")
    )
    expect(preview).to_contain_text("Browser Discussion case")
    expect(preview.locator('[contenteditable="true"]')).to_have_count(0)
    expect(preview.get_by_role("textbox")).to_have_count(0)


@then("I can choose Return to meeting to edit")
def return_action_is_available(context):
    expect(
        context.page.get_by_role(
            "button",
            name=context.browser_session.ui_text("community_meetings", "Return to meeting to edit"),
            exact=True,
        )
    ).to_be_visible()


@then("the meeting and saved draft remain unchanged")
def preview_did_not_write(context):
    meeting_before, item_before, html_before = context.saved_draft_before_preview
    meeting_after = context.browser_session.record(
        "community.meeting", context.meeting_id, ["name", "state", "write_date"]
    )
    item_id = context.live_meeting_fixture.item_ids["discussion"]
    item_after = context.browser_session.record(
        "community.meeting.agenda.item",
        item_id,
        ["name", "discussion_notes", "write_date"],
    )
    html_after = context.browser_session.rpc("community.meeting", "get_minutes_preview_html", [[context.meeting_id]])
    assert meeting_after == meeting_before, (meeting_before, meeting_after)
    assert item_after == item_before, (item_before, item_after)
    assert html_after == html_before, "Preview changed the rendered saved minutes"


@when("I choose Return to meeting to edit")
def return_to_meeting_editor(context):
    context.page.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Return to meeting to edit"), exact=True
    ).click()


@then("I return to the meeting editor")
def meeting_editor_is_open(context):
    assert_meeting_form(context.page, context.meeting_name)
