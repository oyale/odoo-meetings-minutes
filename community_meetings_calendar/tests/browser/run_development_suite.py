#!/usr/bin/env python3
"""Run core and Calendar browser checks in the isolated Calendar test database."""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

CORE_BROWSER = Path(__file__).resolve().parents[3] / "community_meetings" / "tests" / "browser"
sys.path.insert(0, str(CORE_BROWSER))
from run_development_suite import main  # noqa: E402


def block_calendar_mail(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default="pelayo@meeting-minutes.local")
    parser.add_argument("--database", required=True)
    options, _ = parser.parse_known_args(argv)
    if options.database == "meeting_minutes":
        raise ValueError("Use a dedicated Calendar test database, not meeting_minutes.")
    shell = shlex.join([
        "sudo", "-n", "-u", "odoo", "/home/odoo/pyenv/versions/odoo/bin/python",
        "/opt/odoo/odoo-bin", "shell", "-c", "/etc/odoo/odoo.conf",
        "-d", options.database,
    ])
    subprocess.run([
        "ssh", "-F", "/dev/null", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        options.host, shell,
    ], input="env['ir.config_parameter'].sudo().set_param('calendar.block_mail', '1')\nenv.cr.commit()\n",
        text=True, check=True, capture_output=True, timeout=120)


if __name__ == "__main__":
    block_calendar_mail(sys.argv[1:])
    raise SystemExit(main(script_path=Path(__file__).with_name("full_calendar_playwright.py")))
