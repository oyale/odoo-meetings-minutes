"""Browser UI steps for submitting and accepting an agenda proposal."""

from uuid import uuid4

from behave import given, then, when
from playwright.sync_api import expect


@given("a meeting series allows a new point proposal")
def proposal_series_available(context):
    suffix = uuid4().hex[:8]
    context.series_id = context.browser_session.rpc(
        "community.meeting.series", "create", [{"name": f"Acceptance proposal series {suffix}"}]
    )
    context.proposal_name = f"Acceptance proposed point {suffix}"
    context.requires_database_drop = True
    menu = context.browser_session.rpc(
        "ir.ui.menu", "search_read", [[("name", "=", "Propose a point")]], {"fields": ["id"], "limit": 1}
    )
    assert len(menu) == 1, menu
    context.page.goto(f"{context.acceptance_config.base_url}/web#menu_id={menu[0]['id']}")
    context.proposal_dialog = context.page.get_by_role("dialog")
    expect(context.proposal_dialog).to_be_visible()


@when("I submit a titled discussion point")
def submit_titled_proposal(context):
    dialog = context.proposal_dialog
    dialog.locator('.o_field_widget[name="proposal_series_id"] input').click()
    context.page.get_by_role(
        "option",
        name=context.browser_session.record("community.meeting.series", context.series_id, ["name"])["name"],
        exact=True,
    ).click()
    dialog.locator('.o_field_widget[name="name"] input').fill(context.proposal_name)
    dialog.get_by_role("radio", name="Discussion", exact=True).click()
    dialog.get_by_role("button", name="Add point", exact=True).click()
    expect(dialog).not_to_be_visible()


@then("the proposal is visible for review and can be accepted")
def proposal_visible_and_accepted(context):
    proposals = context.browser_session.rpc(
        "community.meeting.topic",
        "search_read",
        [[("series_id", "=", context.series_id), ("name", "=", context.proposal_name)]],
        {"fields": ["id", "state", "proposal_status"]},
    )
    assert len(proposals) == 1, proposals
    assert proposals[0]["state"] == "proposed" and proposals[0]["proposal_status"] == "submitted", proposals
    context.topic_id = proposals[0]["id"]
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting.series&id={context.series_id}&view_type=form"
    )
    proposal_row = context.page.locator('.o_field_widget[name="pending_proposal_ids"] tr.o_data_row').filter(
        has_text=context.proposal_name
    )
    expect(proposal_row).to_be_visible()
    proposal_row.get_by_role("button", name="Accept", exact=True).click()
    expect(proposal_row).to_have_count(0)


@then("the point is admitted to the series agenda")
def proposal_accepted_state(context):
    topic = context.browser_session.record(
        "community.meeting.topic", context.topic_id, ["state", "proposal_status", "series_id"]
    )
    assert topic["state"] == "open" and topic["proposal_status"] == "accepted", topic
    assert topic["series_id"] == [
        context.series_id,
        context.browser_session.record("community.meeting.series", context.series_id, ["name"])["name"],
    ], topic
