# Acceptance tests

This suite uses Behave steps and Playwright browser actions. It connects
to an explicitly configured Odoo test service; it does not create or drop
databases or start services. The test service and database must be prepared before running the suite.

Install its pinned Python dependencies and Chromium:

```console
python -m pip install -r tests/acceptance/requirements.txt
python -m playwright install chromium
```

Set these variables only for an explicitly disposable Odoo test environment:

- `ODOO_ACCEPTANCE_ALLOW_DISPOSABLE=1` is an explicit opt-in guard.
- `ODOO_BASE_URL` is the full HTTP(S) URL of the selected Odoo test service.
- `ODOO_DB` is the selected database name.
- `ODOO_LOGIN` and `ODOO_PASSWORD` identify the user performing the UI actions.
- Multi-actor journeys may also set `ODOO_REVIEWER_LOGIN` (its password defaults
  to `ODOO_PASSWORD`; set `ODOO_REVIEWER_PASSWORD` only when it differs) and
  `ODOO_READER_LOGIN`/`ODOO_READER_PASSWORD`. These accounts must already
  exist in the selected database with the intended roles; the suite verifies
  required groups before acting as them. Credentials are read from the process
  environment and are not written to scenario reports.
- `ODOO_ACCEPTANCE_SCOPE` is `core`, `project`, `calendar`, or `all`.
- `PLAYWRIGHT_HEADFUL=1` opens a visible browser; headless is the default.

The suite has no default URL or database. Do not point it at a shared or
production database.

Run scenarios from the repository root:

```console
ODOO_ACCEPTANCE_ALLOW_DISPOSABLE=1 \
ODOO_BASE_URL=http://127.0.0.1:18069 \
ODOO_DB=mm_dev_acceptance \
ODOO_LOGIN='<test user>' \
ODOO_PASSWORD='<test password>' \
ODOO_ACCEPTANCE_SCOPE=core \
python -m behave tests/acceptance/features --tags='@core'
```

Add `--junit --junit-directory <temporary-directory>` when a standard
JUnit report is needed. An empty selection, undefined step, failed hook, skipped
scenario, or failed assertion must produce a failed run. Scope tags select the relevant scenarios (`@core`, `@project`, or `@calendar`).

After the first failed step, the runner saves a full-page screenshot, DOM
snapshot, and captured browser console/page errors under the system temporary
directory at `odoo-acceptance-artifacts/<database>/`. All three files have
owner-only permissions. Inspect them and the Odoo/Behave logs before repeating
a scenario, so one failure is enough to diagnose most UI and request timing
problems.

The matrix in [`SCENARIOS.md`](SCENARIOS.md) records scenario IDs, setup, user
actions, assertions, and cleanup boundaries. Each feature describes user actions and observable results for its workflow.
