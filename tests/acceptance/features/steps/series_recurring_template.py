"""Browser UI steps for recurring agenda templates."""

from uuid import uuid4

from behave import given, then, when
from playwright.sync_api import expect


@given("an editable meeting series is open")
def editable_meeting_series_open(context):
    suffix = uuid4().hex[:8]
    context.recurring_series_name = f"Acceptance recurring series {suffix}"
    context.recurring_template_name = f"Acceptance recurring discussion {suffix}"
    context.recurring_series_fixture_id = context.browser_session.rpc(
        "community.meeting.series", "create", [{"name": context.recurring_series_name}]
    )
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting.series&id="
        f"{context.recurring_series_fixture_id}&view_type=form"
    )
    expect(context.page.locator(".o_form_view")).to_contain_text(context.recurring_series_name)


@when("I add a recurring discussion point and prepare a meeting")
def add_recurring_point_and_prepare(context):
    context.page.get_by_role("tab", name="Recurring agenda").click()
    template_list = context.page.locator('.o_field_widget[name="recurring_point_ids"]')
    template_list.get_by_text("Add a line", exact=True).click()
    new_row = template_list.locator("tr.o_data_row").last
    name_cell = new_row.locator('td[name="name"]')
    name_cell.click()
    name_input = name_cell.locator("input")
    name_input.fill(context.recurring_template_name)
    name_input.press("Tab")
    context.page.locator(".o_form_button_save").click()
    template_row = template_list.locator("tr.o_data_row").filter(has_text=context.recurring_template_name)
    expect(template_row).to_be_visible()

    context.page.locator('button[name="action_new_meeting"]').click()
    wizard = context.page.get_by_role("dialog").last
    wizard.locator('button[name="action_next"]').click()
    wizard.locator('.o_field_widget[name="name"] input').fill("Acceptance recurring point meeting")
    wizard.locator('.o_field_widget[name="start_datetime"] input').fill("2030-04-02 10:00:00")
    for _ in range(3):
        wizard.locator('button[name="action_next"]').click()
    context.recurring_point_row = wizard.locator('.o_field_widget[name="recurring_line_ids"] tr.o_data_row').filter(
        has_text=context.recurring_template_name
    )


@then("the recurring point is available for this meeting and remains active on the series")
def recurring_point_available_and_active(context):
    expect(context.recurring_point_row).to_be_visible()
    toggle = context.recurring_point_row.locator('input[type="checkbox"]')
    expect(toggle).to_be_checked()
    templates = context.browser_session.rpc(
        "community.meeting.series.agenda.template",
        "search_read",
        [[("series_id", "=", context.recurring_series_fixture_id), ("name", "=", context.recurring_template_name)]],
        {"fields": ["id", "active", "agenda_type_id"]},
    )
    assert len(templates) == 1 and templates[0]["active"], templates
