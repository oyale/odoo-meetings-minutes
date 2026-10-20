"""Browser UI steps for creating and validating a meeting series."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from playwright.sync_api import expect


def _open_series_wizard(context):
    context.page.goto(
        f"{context.acceptance_config.base_url}/odoo/action-community_meetings.action_community_meeting_series"
    )
    context.page.locator(".o_list_button_add").click()
    context.series_wizard = context.page.get_by_role("dialog").last
    expect(context.series_wizard).to_be_visible()


@given("the meeting series wizard is open")
def meeting_series_wizard_open(context):
    _open_series_wizard(context)
    context.series_name = f"Acceptance series {uuid4().hex[:8]}"
    context.series_count_before = context.browser_session.rpc("community.meeting.series", "search_count", [[]])


@when("I complete the series details and choose Create Series")
def create_series_from_wizard(context):
    wizard = context.series_wizard
    wizard.locator('.o_field_widget[name="name"] input').fill(context.series_name)
    for _ in range(3):
        wizard.locator('button[name="action_next"]').click()
    with context.page.expect_response(
        lambda response: "/call_button/community.meeting.series.wizard/action_finish" in response.url
    ):
        wizard.locator('button[name="action_finish"]').click()
    context.page.locator(".o_form_view").filter(has_text=context.series_name).wait_for()
    ids = context.browser_session.rpc("community.meeting.series", "search", [[("name", "=", context.series_name)]])
    assert len(ids) == 1, ids
    context.series_fixture_id = ids[0]


@then("the series appears in Meeting Series with its saved defaults")
def series_created_with_defaults(context):
    record = context.browser_session.record(
        "community.meeting.series",
        context.series_fixture_id,
        ["name", "duration_hours", "carryover_policy", "active"],
    )
    assert record["name"] == context.series_name, record
    assert record["active"] and record["duration_hours"] > 0, record
    assert record["carryover_policy"] == "review", record


@given("the meeting series wizard is open with no name")
def meeting_series_wizard_open_without_name(context):
    _open_series_wizard(context)
    context.series_count_before = context.browser_session.rpc("community.meeting.series", "search_count", [[]])


@when("I try to continue without a series name")
def continue_series_wizard_without_name(context):
    name_input = context.series_wizard.locator('.o_field_widget[name="name"] input')
    name_input.fill("")
    context.series_wizard.locator('button[name="action_next"]').click()


@then("the required-name validation remains active and no series is persisted")
def series_name_is_required(context):
    name_field = context.series_wizard.locator('.o_field_widget[name="name"]')
    name_input = name_field.locator("input")
    assert "o_required_modifier" in (name_field.get_attribute("class") or "")
    assert not name_input.input_value()
    expect(context.series_wizard.locator('button[name="action_next"]')).to_be_visible()
    count_after = context.browser_session.rpc("community.meeting.series", "search_count", [[]])
    assert count_after == context.series_count_before, (context.series_count_before, count_after)
