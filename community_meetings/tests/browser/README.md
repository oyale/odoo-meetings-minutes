# Playwright browser checks

The browser checks exercise the meeting UI against an existing Odoo 18 test
instance. They are manual integration checks and are not part of OCA's unit-test
workflow. Use a disposable database and a test account with the required
meeting roles. Scenarios create and remove meeting records; do not point them at
production.

Install Playwright and Chromium in the Python environment used to run the
checks, then configure the connection with environment variables:

```console
export ODOO_BASE_URL=http://localhost:8069
export ODOO_DB=meeting_minutes_test  # optional, if the server requires a DB name
export ODOO_LOGIN=meeting-editor
export ODOO_PASSWORD='...'
python3 community_meetings/tests/browser/full_meeting_playwright.py
```

The base suite includes the core meeting workflows. The `community_meetings_project`
and `community_meetings_calendar` directories contain optional suites for their
integrations; run those against a database with the corresponding addon installed.
The integration suites import the core browser helpers from this addon.

Set `PLAYWRIGHT_HEADFUL=1` to display Chromium. Artifacts are written under
`/tmp/meeting-playwright/` by default; set `PLAYWRIGHT_ARTIFACTS` to change the
location. Never commit credentials, browser traces or test artifacts.
