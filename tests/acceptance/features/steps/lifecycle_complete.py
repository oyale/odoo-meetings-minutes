"""Browser UI steps for the complete create-to-approval lifecycle."""

from __future__ import annotations

from uuid import uuid4

from acceptance_actors import login_as_configured_actor
from behave import given, then, when
from browser_support.meeting import assert_meeting_form
from playwright.sync_api import expect


@given("I create and schedule a meeting with an agenda point in the UI")
def create_and_schedule_meeting_with_agenda_point(context):
    context.meeting_name = f"Acceptance lifecycle {uuid4().hex[:8]}"
    context.requires_database_drop = True
    context.page.goto(
        f"{context.acceptance_config.base_url}/odoo/action-community_meetings.action_community_meetings"
    )
    context.page.locator('a[data-menu-xmlid="community_meetings.menu_prepare_meeting"]').click()
    wizard = context.page.get_by_role("dialog").last
    wizard.locator('button[name="action_next"]').click()
    wizard.locator('.o_field_widget[name="name"] input').fill(context.meeting_name)
    for _ in range(3):
        wizard.locator('button[name="action_next"]').click()
    agenda_step = wizard.locator('.o_meeting_create_step:has(button[name="action_add_point"])')
    expect(agenda_step).to_be_visible()
    agenda_step.get_by_role("button", name="Add Point", exact=True).click()
    point_dialog = context.page.get_by_role("dialog").last
    context.agenda_point_name = f"Lifecycle point {uuid4().hex[:6]}"
    point_dialog.locator('.o_field_widget[name="name"] input').fill(context.agenda_point_name)
    point_dialog.get_by_role("radio", name="Discussion", exact=True).click()
    point_dialog.get_by_role("button", name="Add point", exact=True).click()
    expect(context.page.locator(".o_meeting_point_wizard")).to_have_count(0)
    expect(wizard.locator('.o_field_widget[name="line_ids"]')).to_contain_text(context.agenda_point_name)
    wizard.locator('button[name="action_next"]').click()
    expect(wizard.locator(".o_meeting_review_summary")).to_be_visible()
    with context.page.expect_response(
        lambda response: "/call_button/community.meeting.create.wizard/action_finish" in response.url
    ) as finish_response:
        wizard.locator('button[name="action_finish"]').click()
    action = finish_response.value.json()["result"]
    context.meeting_id = action["res_id"]
    meeting = context.browser_session.record(
        "community.meeting", context.meeting_id, ["name", "state", "start_datetime"]
    )
    assert meeting["name"] == context.meeting_name and meeting["state"] == "draft", meeting
    assert meeting["start_datetime"], meeting
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)
    with context.page.expect_response(
        lambda response: "/community.meeting/action_schedule" in response.url
    ):
        context.page.locator('button[name="action_schedule"]').click()
    record = context.browser_session.record("community.meeting", context.meeting_id, ["state"])
    assert record["state"] == "scheduled", record


@when("I hold the meeting in the live agenda")
def hold_meeting_in_live_agenda(context):
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)
    context.page.get_by_role("button", name="Open Meeting", exact=True).click()
    context.page.get_by_role("button", name="Start Meeting", exact=True).click()
    expect(context.page.get_by_role("button", name="Finish Meeting", exact=True)).to_be_visible()
    card = context.page.locator(".o_live_agenda_card").filter(has_text=context.agenda_point_name)
    expect(card).to_be_visible()
    if card.get_by_role("button", name="Begin point", exact=True).count():
        card.get_by_role("button", name="Begin point", exact=True).click()
        card.get_by_role("button", name="Done", exact=True).click()
    else:
        raise AssertionError("The agenda discussion point could not be started")
    with context.page.expect_response(
        lambda response: "/community.meeting/action_mark_held" in response.url
    ):
        context.page.get_by_role("button", name="Finish Meeting", exact=True).click()
    record = context.browser_session.record("community.meeting", context.meeting_id, ["state"])
    assert record["state"] == "held", record
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)
    with context.page.expect_response(
        lambda response: "/call_button/community.meeting/action_draft_minutes" in response.url
    ):
        context.page.get_by_role("button", name="Prepare Minutes", exact=True).click()
    record = context.browser_session.record("community.meeting", context.meeting_id, ["state"])
    assert record["state"] == "minutes_draft", record


@when("I sign in as the configured approver and approve the minutes")
def approve_minutes_as_distinct_actor(context):
    approver = context.browser_session.rpc(
        "res.users",
        "search_read",
        [[("login", "=", context.acceptance_config.reviewer_login)]],
        {"fields": ["id"]},
    )[0]
    context.browser_session.rpc(
        "community.meeting",
        "write",
        [[context.meeting_id], {"reader_user_ids": [(4, approver["id"])]}],
    )
    context.approver_session = login_as_configured_actor(context, "reviewer")
    context.approver_session.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.approver_session.page, context.meeting_name)
    with context.approver_session.page.expect_response(
        lambda response: "/call_button/community.meeting/action_approve_minutes" in response.url
    ) as approval_response:
        context.approver_session.page.get_by_role("button", name="Approve Minutes", exact=True).click()
    assert approval_response.value.status == 200, approval_response.value.status


@then("the same meeting is approved and its minutes PDF opens")
def same_meeting_approved_with_pdf(context):
    record = context.browser_session.record(
        "community.meeting", context.meeting_id, ["state", "approved_revision_id", "revision_ids"]
    )
    assert record["state"] == "approved", record
    assert record["approved_revision_id"], record
    assert record["revision_ids"], record
    page = context.approver_session.page
    page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(page, context.meeting_name)
    page.get_by_role("tab", name="Approved Revisions", exact=True).click()
    download_button = page.get_by_role("button", name="PDF", exact=True)
    expect(download_button).to_be_visible()
    with page.expect_response(
        lambda response: "/web/content/" in response.url and response.request.method == "GET"
    ) as pdf_response:
        download_button.click()
    response = pdf_response.value
    assert response.status == 200, response.status
    assert response.headers.get("content-type", "").startswith("application/pdf"), response.headers
