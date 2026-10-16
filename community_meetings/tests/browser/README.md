# Live meeting browser checks

Run `live_meeting_playwright.py` against a development Odoo database with a user
that can create and schedule meetings and edit agendas:

```sh
ODOO_BASE_URL=http://meeting-minutes.local:8069 \
ODOO_LOGIN=your-editor-login ODOO_PASSWORD=your-password \
python3 live_meeting_playwright.py
```

The suite creates one scheduled meeting per test with an informational,
discussion, and decision point. It checks scrolling, collapsed forms, dissent
author/type/text, done/resolved/postponed actions, and decision agreement
creation/withdrawal. Each meeting is cancelled and deleted in `tearDown`, even
when an assertion fails. Set `PLAYWRIGHT_HEADFUL=1` to watch the browser.
