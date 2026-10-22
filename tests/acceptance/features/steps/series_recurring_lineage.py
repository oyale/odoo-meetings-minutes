"""Browser UI steps for recurring point inclusion and occurrence lineage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from behave import given, then, when
from playwright.sync_api import expect


def _prepare_meeting(context, name, start, include):
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting.series&id={context.series_id}&view_type=form"
    )
    context.page.locator('button[name="action_new_meeting"]').click()
    wizard = context.page.get_by_role("dialog").last
    wizard.locator('button[name="action_next"]').click()
    wizard.locator('.o_field_widget[name="name"] input').fill(name)
    wizard.locator('.o_field_widget[name="start_datetime"] input').fill(start)
    for _ in range(3):
        wizard.locator('button[name="action_next"]').click()
    row = wizard.locator('.o_field_widget[name="recurring_line_ids"] tr.o_data_row').filter(
        has_text=context.template_name
    )
    expect(row).to_be_visible()
    toggle = row.locator('input[type="checkbox"]')
    expect(toggle).to_be_checked()
    if not include:
        toggle.uncheck()
        expect(toggle).not_to_be_checked()
    wizard.locator('button[name="action_next"]').click()
    summary = wizard.locator('.o_field_widget[name="review_summary"]')
    if include:
        expect(summary).to_contain_text(context.template_name)
    else:
        expect(summary).not_to_contain_text(context.template_name)
    wizard.locator('button[name="action_finish"]').click()
    expect(wizard).not_to_be_visible(timeout=30000)
    meeting_ids = context.browser_session.rpc(
        "community.meeting", "search", [[("series_id", "=", context.series_id), ("name", "=", name)]]
    )
    assert len(meeting_ids) == 1, meeting_ids
    return meeting_ids[0]


@given("a recurring template is active on a meeting series")
def active_recurring_template_for_lineage(context):
    suffix = uuid4().hex[:8]
    context.series_name = f"Acceptance lineage series {suffix}"
    context.template_name = f"Acceptance recurring point {suffix}"
    context.series_id = context.browser_session.rpc(
        "community.meeting.series", "create", [{"name": context.series_name}]
    )
    context.series_fixture_id = context.series_id
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting.series&id={context.series_id}&view_type=form"
    )
    context.page.get_by_role("tab", name=context.browser_session.ui_text('community_meetings', 'Recurring agenda')).click()
    template_list = context.page.locator('.o_field_widget[name="recurring_point_ids"]')
    template_list.get_by_text("Add a line", exact=True).click()
    row = template_list.locator("tr.o_data_row").last
    cell = row.locator('td[name="name"]')
    cell.click()
    cell.locator("input").fill(context.template_name)
    cell.locator("input").press("Tab")
    context.page.locator(".o_form_button_save").click()
    expect(template_list.locator("tr.o_data_row").filter(has_text=context.template_name)).to_be_visible()
    template_ids = context.browser_session.rpc(
        "community.meeting.series.agenda.template",
        "search",
        [[("series_id", "=", context.series_id), ("name", "=", context.template_name)]],
    )
    assert len(template_ids) == 1, template_ids
    context.template_id = template_ids[0]
    context.requires_database_drop = True
    context.meeting_start_base = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=15)


@when("I omit it from one meeting and include it in a later meeting")
def skip_and_reinclude_template(context):
    start = context.meeting_start_base
    context.first_meeting_id = _prepare_meeting(
        context,
        f"{context.series_name} first",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        True,
    )
    context.skipped_meeting_id = _prepare_meeting(
        context,
        f"{context.series_name} skipped",
        (start + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
        False,
    )
    context.later_meeting_id = _prepare_meeting(
        context,
        f"{context.series_name} later",
        (start + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"),
        True,
    )


@then("the skipped meeting has no occurrence and the later occurrence links to the first")
def verify_recurring_occurrence_lineage(context):
    def occurrence(meeting_id):
        item_rows = context.browser_session.rpc(
            "community.meeting.agenda.item",
            "search_read",
            [[("meeting_id", "=", meeting_id)]],
            {"fields": ["topic_id"]},
        )
        topic_ids = [row["topic_id"][0] for row in item_rows if row["topic_id"]]
        rows = context.browser_session.rpc(
            "community.meeting.topic",
            "search_read",
            [[("id", "in", topic_ids), ("recurring_template_id", "=", context.template_id)]],
            {"fields": ["id", "previous_occurrence_id"]},
        )
        return rows[0] if rows else None

    first = occurrence(context.first_meeting_id)
    skipped = occurrence(context.skipped_meeting_id)
    later = occurrence(context.later_meeting_id)
    assert first, "The included first meeting has no recurring occurrence"
    assert skipped is None, skipped
    assert later, "The later included meeting has no recurring occurrence"
    assert later["previous_occurrence_id"][0] == first["id"], later
