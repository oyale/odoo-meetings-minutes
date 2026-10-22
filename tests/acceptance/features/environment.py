"""Fail-safe lifecycle hooks for the Behave acceptance suite."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from behave.model import Status
from playwright.sync_api import Error as PlaywrightError

TESTS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TESTS_ROOT))

from acceptance.config import AcceptanceConfig
from browser_support.odoo_browser import OdooBrowserSession


def before_all(context):
    context.acceptance_config = AcceptanceConfig.from_environment(os.environ)
    runner = context._runner
    selected_scenarios = (
        scenario
        for feature in runner.features
        for scenario in feature.walk_scenarios()
        if scenario.should_run(runner.config)
    )
    if next(selected_scenarios, None) is None:
        raise RuntimeError("Behave selected no acceptance scenarios; check the tag and name filters")


def after_step(context, _step):
    if _step.status not in (Status.failed, Status.error):
        return
    page = getattr(getattr(context, "browser_session", None), "page", None)
    if page is None:
        return
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", context.scenario.name).strip("-") or "scenario"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = Path(tempfile.gettempdir()) / "odoo-acceptance-artifacts" / context.acceptance_config.database
    stem = f"{stamp}-{name}"
    screenshot = directory / f"{stem}.png"
    html = directory / f"{stem}.html"
    console = directory / f"{stem}.console.txt"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        html.write_text(page.content(), encoding="utf-8")
        html.chmod(0o600)
        console.write_text("\n".join(context.browser_session.console_errors) + "\n", encoding="utf-8")
        console.chmod(0o600)
        context.failed_step_artifacts = [screenshot, html, console]
        print(f"Acceptance failure evidence: {screenshot}, {html}, and {console}")
    except (OSError, PlaywrightError) as error:
        print(f"Could not capture acceptance failure evidence: {error}")


def before_scenario(context, scenario):
    tags = set(scenario.effective_tags)
    selected_scopes = tags.intersection({"core", "project", "calendar"})
    config_scope = context.acceptance_config.scope
    if config_scope != "all" and config_scope not in selected_scopes:
        raise RuntimeError(f"scenario {scenario.name!r} is outside selected scope {config_scope!r}")
    context.browser_session = OdooBrowserSession.login(
        context.acceptance_config.base_url,
        context.acceptance_config.database,
        context.acceptance_config.login,
        context.acceptance_config.password,
        headless=not context.acceptance_config.headful,
    )
    context.browser_session.verify_locale(context.browser_session.effective_locale() or "")
    context.page = context.browser_session.page
    context.live_meeting_fixture = None
    context.additional_browser_sessions = []
    context.proposal_series_id = None
    context.recurring_series_fixture_id = None
    context.unlinked_calendar_event_fixture_id = None
    context.series_fixture_id = None
    context.requires_database_drop = False


def _cleanup_tracked_records(context, session):
    for attribute, model in (
        ("proposal_series_id", "community.meeting.series"),
        ("recurring_series_fixture_id", "community.meeting.series"),
        ("series_fixture_id", "community.meeting.series"),
        ("unlinked_calendar_event_fixture_id", "calendar.event"),
    ):
        record_id = getattr(context, attribute, None)
        if record_id and session is not None:
            session.rpc(model, "unlink", [[record_id]])


def after_scenario(context, scenario):
    try:
        session = getattr(context, "browser_session", None)
        if not getattr(context, "requires_database_drop", False):
            _cleanup_tracked_records(context, session)
        fixture = getattr(context, "live_meeting_fixture", None)
        if fixture is not None and not fixture.cleanup() and not getattr(context, "requires_database_drop", False):
            print(
                "Acceptance fixture could not be removed through the meeting workflow; "
                "drop the disposable database after this run."
            )
        if getattr(context, "discussion_history_fixture", False):
            print(
                "Discussion-history carryovers preserve cross-meeting lineage; "
                "drop the disposable database after this run."
            )
        if getattr(context, "requires_database_drop", False):
            print(
                "This workflow leaves records that cannot be removed individually; "
                "drop the disposable database after this scenario."
            )
    finally:
        for extra_session in getattr(context, "additional_browser_sessions", []):
            extra_session.close()
        session = getattr(context, "browser_session", None)
        if session is not None:
            session.close()
    if scenario.status == Status.skipped:
        raise AssertionError(f"selected acceptance scenario {scenario.name!r} was skipped")
