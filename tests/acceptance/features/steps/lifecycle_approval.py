"""Browser UI steps for approval prerequisites on meeting minutes."""

from __future__ import annotations

from acceptance.features.steps.acceptance_actors import login_as_configured_actor
from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


@given("a draft of minutes has no agenda points")
def minutes_draft_has_no_agenda(context):
    # This workflow reaches a terminal, non-deletable state. If setup fails
    # after creating the meeting, the caller must drop the disposable database.
    if not context.acceptance_config.reviewer_login:
        raise AssertionError("Configure ODOO_REVIEWER_LOGIN for this approval scenario")
    context.requires_database_drop = True
    fixture = LiveMeetingFixture.create_minutes_draft_without_agenda(context.browser_session, "empty agenda approval")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    reviewer = context.browser_session.rpc(
        "res.users",
        "search_read",
        [[("login", "=", context.acceptance_config.reviewer_login)]],
        {"fields": ["id"], "limit": 1},
    )
    if not reviewer:
        raise AssertionError(f"Configured reviewer {context.acceptance_config.reviewer_login!r} was not found")
    context.browser_session.rpc(
        "community.meeting",
        "write",
        [[fixture.meeting_id], {"reader_user_ids": [(4, reviewer[0]["id"])]}],
    )
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    context.meeting_before_approval = context.browser_session.record(
        "community.meeting",
        fixture.meeting_id,
        ["state", "approved_revision_id", "revision_ids", "write_date"],
    )
    assert context.meeting_before_approval["state"] == "minutes_draft"
    assert not context.meeting_before_approval["revision_ids"]
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)


@when("I choose Approve Minutes from its meeting form")
def approve_empty_minutes_from_form(context):
    login_as_configured_actor(context, "reviewer")
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)
    context.page.locator('button[name="action_approve_minutes"]').click()


@then("the form explains that an agenda point is required")
def agenda_requirement_is_visible(context):
    expect(context.page.get_by_role("dialog")).to_contain_text(
        "Add at least one agenda item before approving the minutes."
    )


@then("the draft remains unapproved without a new revision")
def minutes_draft_remains_unapproved(context):
    meeting_after = context.browser_session.record(
        "community.meeting",
        context.meeting_id,
        ["state", "approved_revision_id", "revision_ids", "write_date"],
    )
    assert meeting_after == context.meeting_before_approval, (
        context.meeting_before_approval,
        meeting_after,
    )
