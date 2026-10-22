"""Browser UI steps for marking postponed points for next-meeting review."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("a running meeting contains a discussion point that can be postponed")
def running_meeting_with_postponable_point(context):
    session = context.browser_session
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(session, f"next review {uuid4().hex[:8]}")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.agenda_item_id = fixture.item_ids["discussion"]
    open_live_meeting(session, fixture.meeting_id)


def _start_meeting_and_point(context):
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    start_meeting = context.page.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Start Meeting'), exact=True)
    if start_meeting.count():
        start_meeting.click()
    expect(context.page.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Finish Meeting'), exact=True)).to_be_visible()
    begin_point = card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Begin point'), exact=True)
    if begin_point.count():
        begin_point.click()
    expect(card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Pause point'), exact=True)).to_be_visible()
    return card


@when("I postpone the point with a reason")
def postpone_point_with_reason(context):
    card = _start_meeting_and_point(context)
    postpone = card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Postpone agenda point'), exact=True)
    expect(postpone).to_be_visible()
    postpone.click()
    reason = card.get_by_label(context.browser_session.ui_text('community_meetings', 'Reason for postponing'), exact=True)
    expect(reason).to_be_visible()
    context.postponement_reason = f"Acceptance reason {uuid4().hex[:8]}"
    reason.fill(context.postponement_reason)
    card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Leave postponed'), exact=True).click()


@then("the point is postponed and marked for review at the next meeting")
def point_is_marked_for_next_meeting_review(context):
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    expect(card.get_by_text(context.browser_session.ui_text('community_meetings', 'Will be reviewed at the next meeting'), exact=True)).to_be_visible()
    item = context.browser_session.rpc(
        "community.meeting.agenda.item",
        "read",
        [[context.agenda_item_id], ["disposition", "deferral_reason", "review_next_meeting"]],
    )[0]
    assert item["disposition"] == "deferred", item
    assert item["deferral_reason"] == context.postponement_reason, item
    assert item["review_next_meeting"] is True, item


@when("I mark the point for review at the next meeting")
def mark_point_for_next_meeting_review(context):
    card = _start_meeting_and_point(context)
    checkbox = card.get_by_role("checkbox", name=context.browser_session.ui_text('community_meetings', 'Review at next meeting'), exact=True)
    checkbox.check()
    expect(checkbox).to_be_checked()


@then("the choice remains checked after reopening the meeting")
def review_choice_remains_checked_after_reopening(context):
    open_live_meeting(context.browser_session, context.meeting_id)
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    checkbox = card.get_by_role("checkbox", name=context.browser_session.ui_text('community_meetings', 'Review at next meeting'), exact=True)
    expect(checkbox).to_be_checked()
    item = context.browser_session.rpc(
        "community.meeting.agenda.item",
        "read",
        [[context.agenda_item_id], ["review_next_meeting"]],
    )[0]
    assert item["review_next_meeting"] is True, item


@when("I clear the review choice")
def clear_next_meeting_review(context):
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    checkbox = card.get_by_role("checkbox", name=context.browser_session.ui_text('community_meetings', 'Review at next meeting'), exact=True)
    checkbox.uncheck()
    expect(checkbox).not_to_be_checked()


@then("the choice remains clear after reopening the meeting")
def review_choice_remains_clear_after_reopening(context):
    open_live_meeting(context.browser_session, context.meeting_id)
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    checkbox = card.get_by_role("checkbox", name=context.browser_session.ui_text('community_meetings', 'Review at next meeting'), exact=True)
    expect(checkbox).not_to_be_checked()
    item = context.browser_session.rpc(
        "community.meeting.agenda.item",
        "read",
        [[context.agenda_item_id], ["review_next_meeting"]],
    )[0]
    assert item["review_next_meeting"] is False, item
