"""Browser UI steps for required agenda proposal fields."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from playwright.sync_api import expect


@given("an agenda proposal can be submitted for a series")
def proposal_series_exists(context):
    context.proposal_series_name = f"Browser proposal {uuid4().hex[:8]}"
    context.proposal_series_id = context.browser_session.rpc(
        "community.meeting.series",
        "create",
        [{"name": context.proposal_series_name}],
    )
    menu = context.browser_session.rpc(
        "ir.ui.menu",
        "search_read",
        [[("name", "=", "Propose a point")]],
        {"fields": ["id", "action"], "limit": 1},
    )
    assert len(menu) == 1 and menu[0]["action"], menu
    context.page.goto(f"{context.browser_session.base_url}/web#menu_id={menu[0]['id']}")
    context.page.get_by_role("dialog").wait_for()


@when("I submit the proposal without a title")
def submit_proposal_without_title(context):
    dialog = context.page.get_by_role("dialog")
    dialog.locator('.o_field_widget[name="proposal_series_id"] input').click()
    context.page.get_by_role("option", name=context.proposal_series_name, exact=True).click()
    dialog.get_by_role(
        "button", name=context.browser_session.ui_text("community_meetings", "Add point"), exact=True
    ).click()


@then("the title validation is shown and no proposal is saved")
def proposal_title_validation_and_no_write(context):
    expect(
        context.page.get_by_text(
            context.browser_session.ui_text("community_meetings", "Enter a title and select a point type."), exact=True
        )
    ).to_be_visible()
    proposals = context.browser_session.rpc(
        "community.meeting.topic",
        "search_read",
        [[("series_id", "=", context.proposal_series_id), ("state", "=", "proposed")]],
        {"fields": ["id", "name", "proposal_status"]},
    )
    assert proposals == [], proposals
