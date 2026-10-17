#!/usr/bin/env python3
"""Provision a disposable test user in the existing development DB, run, clean up.

Requires the explicit --development flag. Never use against production.
No new database, service or listening port is created.
"""

import argparse
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys


def main(script_path=None, project=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true", required=True)
    parser.add_argument("--host", default="pelayo@meeting-minutes.local")
    parser.add_argument("--base-url", default="http://meeting-minutes.local:8069")
    parser.add_argument("--database", default="meeting_minutes")
    parser.add_argument("tests", nargs="*", help="Optional test-name substrings")
    args = parser.parse_args()
    login = "playwright-full-" + secrets.token_hex(8)
    password = secrets.token_urlsafe(32)
    proposer_login = login + "-proposer"
    reviewer_login = login + "-reviewer"
    remote_command = shlex.join(
        [
            "sudo",
            "-n",
            "-u",
            "odoo",
            "/home/odoo/pyenv/versions/odoo/bin/python",
            "/opt/odoo/odoo-bin",
            "shell",
            "-c",
            "/etc/odoo/odoo.conf",
            "-d",
            args.database,
        ]
    )
    ssh = [
        "ssh",
        "-F",
        "/dev/null",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        args.host,
        remote_command,
    ]

    def remote(code):
        result = subprocess.run(
            ssh, input=code, text=True, capture_output=True, timeout=120
        )
        if result.returncode:
            # Odoo can echo input on errors; do not print code containing credentials.
            raise RuntimeError(
                "Development fixture operation failed; inspect the container Odoo log."
            )

    setup = f"""
groups = [env.ref('base.group_user').id, env.ref('community_meetings.group_meeting_editor').id, env.ref('community_meetings.group_meeting_approver').id]
if {project!r}:
    assert 'community.meeting.project.task.wizard' in env.registry.models, 'Project extension must be installed before its browser suite'
    groups.append(env.ref('project.group_project_manager').id)
user = env['res.users'].create({{'name': {login!r}, 'login': {login!r}, 'email': 'browser-editor@example.test', 'password': {password!r}, 'lang': 'en_US', 'groups_id': [(6, 0, groups)]}})
env['res.users'].create({{'name': {reviewer_login!r}, 'login': {reviewer_login!r}, 'email': 'browser-reviewer@example.test', 'password': {password!r}, 'lang': 'en_US', 'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('community_meetings.group_meeting_approver').id])]}})
env['res.users'].create({{'name': {proposer_login!r}, 'login': {proposer_login!r}, 'password': {password!r}, 'lang': 'en_US', 'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('community_meetings.group_agenda_proposer').id])]}})
env.cr.commit()
"""
    cleanup = f"""
user = env['res.users'].search([('login', '=', {login!r})])
if user:
    assert len(user) == 1 and user.login.startswith('playwright-full-')
    meetings = env['community.meeting'].search([('create_uid', '=', user.id)])
    # Test-only reset: normal APIs correctly forbid deleting held meetings.
    # Restrict to records created by this unique disposable user, never name matching.
    if meetings:
        env.cr.execute('UPDATE community_meeting SET state=%s, approved_revision_id=NULL WHERE id IN %s', ['cancelled', tuple(meetings.ids)])
        revisions = env['community.meeting.revision'].search([('meeting_id', 'in', meetings.ids)])
        attachments = revisions.pdf_attachment_id
        env.cr.execute('DELETE FROM community_meeting_revision WHERE meeting_id IN %s', [tuple(meetings.ids)])
        attachments.unlink()
        meetings.invalidate_recordset(['state'])
        transfers = env['community.meeting.carryover'].search([('origin_meeting_id', 'in', meetings.ids)])
        env.cr.execute('UPDATE community_meeting_agenda_item SET carryover_id=NULL WHERE meeting_id IN %s', [tuple(meetings.ids)])
        env['community.meeting.agenda.item'].invalidate_model(['carryover_id'])
        transfers.unlink()
        env['community.meeting.resolution'].search([('meeting_id', 'in', meetings.ids)]).unlink()
        meetings.unlink()
    proposer = env['res.users'].search([('login', '=', {proposer_login!r})])
    if proposer:
        proposer_partner = proposer.partner_id
        proposer.unlink()
        proposer_partner.unlink()
    env['community.meeting.topic'].search([('create_uid', '=', user.id)]).unlink()
    env['community.meeting.series'].search([('create_uid', '=', user.id)]).unlink()
    partner = user.partner_id
    user.unlink()
    partner.unlink()
    reviewer = env['res.users'].search([('login', '=', {reviewer_login!r})])
    reviewer_partner = reviewer.partner_id
    reviewer.unlink()
    reviewer_partner.unlink()
    env.cr.commit()
"""
    try:
        remote(setup)
        env = dict(
            os.environ,
            ODOO_BASE_URL=args.base_url,
            ODOO_DB=args.database,
            ODOO_LOGIN=login,
            ODOO_PASSWORD=password,
            ODOO_PROPOSER_LOGIN=proposer_login,
            ODOO_PROPOSER_PASSWORD=password,
            ODOO_REVIEWER_LOGIN=reviewer_login,
        )
        script = script_path or Path(__file__).with_name("full_meeting_playwright.py")
        return subprocess.run(
            [sys.executable, str(script), *args.tests], env=env
        ).returncode
    finally:
        remote(cleanup)
        print("Disposable development fixtures removed.")


if __name__ == "__main__":
    raise SystemExit(main())
