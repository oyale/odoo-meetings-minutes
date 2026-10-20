"""Multi-actor UI steps for preview access boundaries."""

from acceptance_actors import login_as_configured_actor
from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


@given("draft minutes exist and a reader account is configured")
def draft_minutes_and_reader(context):
    if not context.acceptance_config.reader_login:
        raise AssertionError("Configure ODOO_READER_LOGIN and ODOO_READER_PASSWORD for this scenario")
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "reader preview access")
    fixture.prepare_minutes_draft()
    context.live_meeting_fixture = fixture
    context.requires_database_drop = True
    context.meeting_id = fixture.meeting_id
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    reader_user = context.browser_session.rpc(
        "res.users",
        "search_read",
        [[("login", "=", context.acceptance_config.reader_login)]],
        {"fields": ["id"]},
    )[0]
    context.browser_session.rpc(
        "community.meeting",
        "write",
        [[context.meeting_id], {"reader_user_ids": [(4, reader_user["id"])]}],
    )
    context.reader_session = login_as_configured_actor(context, "reader")


@when("I attempt to preview them as that reader")
def reader_attempts_minutes_preview(context):
    context.reader_session.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={context.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.reader_session.page, context.meeting_name)
    context.reader_page = context.reader_session.page


@then("the reader sees no preview action or content and the endpoint denies access")
def reader_preview_is_denied(context):
    page = context.reader_page
    expect(page.get_by_role("button", name="Preview Minutes", exact=True)).to_have_count(0)
    try:
        context.reader_session.rpc("community.meeting", "get_minutes_preview_html", [[context.meeting_id]])
    except AssertionError as error:
        assert "Only meeting editors and approvers can preview draft minutes." in str(error), error
    else:
        raise AssertionError("Reader unexpectedly received draft minutes preview content")
    expect(page.locator(".o_community_minutes_preview")).to_have_count(0)
