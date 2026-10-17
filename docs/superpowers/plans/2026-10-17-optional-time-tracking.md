# Optional Time Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make meeting start/stop and point timers optional via a company setting with per-series override.

**Architecture:** One selection field on series + one boolean on company; `community.meeting.time_tracking_enabled` is a live-read computed boolean (series override → company default). Server actions guard on it; live view reads it from `get_live_capabilities` and hides timing UI / relaxes edit gating.

**Tech Stack:** Odoo 18, OWL live-meeting client, unittest via `odoo-bin --test-tags`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-17-optional-timing-design.md` (decisions Q1-A, Q2-A, Q3-A).
- Default behavior unchanged: company `meeting_time_tracking = True`, series `time_tracking = 'inherit'`.
- `actual_*` fields are never cleared or migrated; only hidden/guarded.
- Tests run inside the dev container (SSH pattern from `tests/browser/run_development_suite.py`):
  `ssh -F /dev/null -o BatchMode=yes pelayo@meeting-minutes.local "sudo -n -u odoo /home/odoo/pyenv/versions/odoo/bin/python /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d meeting_minutes --test-enable --stop-after-init -u community_meetings --http-port=8071 --test-tags=/community_meetings:<CLASS>.<method>"`
  → then check `sudo -n grep 'tests when loading' /var/log/odoo/odoo.log | tail -1`. Exit 0 + `0 failed, 0 error(s)` = pass.
- Test results go to `/var/log/odoo/odoo.log` (config `logfile`), not stdout. Stdout shows only docutils warnings — ignore them.
- No git commits: repo has no commit history; do not run git commands.
- Language: all user-facing strings wrapped in `_t()` / `_()`.

---

### Task 1: Company field, series field, meeting compute, settings + series + wizard UI

**Files:**
- Modify: `community_meetings/models/preparation.py` (Company block L7-19, Settings block L22-33, MeetingSeries L36-56)
- Modify: `community_meetings/models/meeting.py` (add compute near L57-66 `state` field)
- Modify: `community_meetings/views/preparation_views.xml` (settings view L75, series form inherit L28-31)
- Modify: `community_meetings/views/series_views.xml` (series form L43, wizard L83-118)
- Modify: `community_meetings/models/series_wizard.py` (field L36-51, values dict L105-120)
- Test: `community_meetings/tests/test_optional_timing.py` (new)

**Interfaces:**
- Produces: `res.company.meeting_time_tracking` (Boolean), `community.meeting.series.time_tracking` (Selection `inherit/on/off`), `community.meeting.time_tracking_enabled` (computed Boolean). Task 2 guards and Task 3 capabilities consume `time_tracking_enabled`; Task 3 JS consumes capabilities key `time_tracking`.

- [ ] **Step 1: Write failing tests**

```python
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOptionalTiming(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Timing Editor", "login": "timing-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create(
            {"name": "Timing series"})

    def test_company_default_on(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "M"})
        self.assertTrue(meeting.time_tracking_enabled)

    def test_series_off_overrides_company(self):
        self.series.time_tracking = "off"
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "M", "series_id": self.series.id})
        self.assertFalse(meeting.time_tracking_enabled)

    def test_series_on_overrides_company_off(self):
        self.env.company.meeting_time_tracking = False
        self.series.time_tracking = "on"
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "M", "series_id": self.series.id})
        self.assertTrue(meeting.time_tracking_enabled)

    def test_series_inherit_follows_company(self):
        self.series.time_tracking = "inherit"
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "M", "series_id": self.series.id})
        self.assertTrue(meeting.time_tracking_enabled)
        self.env.company.meeting_time_tracking = False
        meeting.invalidate_recordset(["time_tracking_enabled"])
        self.assertFalse(meeting.time_tracking_enabled)
```

- [ ] **Step 2: Run tests, expect failures**

Command from Global Constraints with `--test-tags=/community_meetings:TestOptionalTiming`.
Expected: 4 errors — `time_tracking_enabled` is not a field yet.

- [ ] **Step 3: Implement fields and compute**

In `preparation.py`, extend the Company class:

```python
    meeting_time_tracking = fields.Boolean(
        string="Track meeting and point time", default=True,
        help="Show start/pause controls and point timers in the live meeting; "
             "records actual durations. A series can override it.",
    )
```

Extend `Settings`:

```python
    meeting_time_tracking = fields.Boolean(
        related="company_id.meeting_time_tracking", readonly=False
    )
```

Extend `MeetingSeries`:

```python
    time_tracking = fields.Selection(
        [("inherit", "Company default"), ("on", "On"), ("off", "Off")],
        default="inherit", required=True,
        help="Overrides the company time-tracking setting for meetings of this series.",
    )
```

In `meeting.py`, after the `state` field block (L66):

```python
    time_tracking_enabled = fields.Boolean(
        string="Time tracking", compute="_compute_time_tracking_enabled",
        help="Series override of the company setting; standalone meetings follow the company.",
    )

    @api.depends("series_id.time_tracking", "company_id.meeting_time_tracking")
    def _compute_time_tracking_enabled(self):
        for meeting in self:
            series_mode = meeting.series_id.time_tracking or "inherit"
            meeting.time_tracking_enabled = (
                meeting.company_id.meeting_time_tracking
                if series_mode == "inherit"
                else series_mode == "on"
            )
```

- [ ] **Step 4: Run tests, expect pass**

Same command. Expected: `0 failed, 0 error(s) of 4 tests`.

- [ ] **Step 5: Settings + series form + wizard UI**

`preparation_views.xml` — in `view_meeting_settings_followups` add a block after the "Role names" block:

```xml
<block title="Time tracking"><setting string="Track meeting and point time"><field name="meeting_time_tracking"/></setting></block>
```

In `view_series_preparation` (series form inherit), after `<field name="carryover_policy"/>` add:

```xml
<field name="time_tracking"/>
```

`series_views.xml` — series form, `<field name="carryover_policy"/>` (L43) gets `<field name="time_tracking"/>` after it.

Wizard: `series_wizard.py` — add `time_tracking = fields.Selection([("inherit", "Company default"), ("on", "On"), ("off", "Off")], default="inherit", required=True)` near L36, and `"time_tracking": self.time_tracking,` in the values dict (L105-120). `series_views.xml` wizard — `structure` step (L98-105) gets `<field name="time_tracking"/>`; `review` step (L106-118) gets `<field name="time_tracking" readonly="1"/>`.

- [ ] **Step 6: Boot test (view validation) + full module run**

Run full `--test-tags=/community_meetings` (Global Constraints command, without class/method).
Expected: views load, `0 failed, 0 error(s)`.

---

### Task 2: Server guards

**Files:**
- Modify: `community_meetings/models/meeting.py` (`action_start_meeting` L377, `action_pause_meeting` L393, `action_resume_meeting` L409)
- Modify: `community_meetings/models/topic.py` (`action_start_timing` L546, `action_pause_timing` L576)
- Test: `community_meetings/tests/test_optional_timing.py`

**Interfaces:**
- Consumes: `community.meeting.time_tracking_enabled` (Task 1).
- Produces: guards raise `UserError` when tracking off; `action_mark_held` untouched.

- [ ] **Step 1: Write failing tests** (append to `test_optional_timing.py`)

```python
    def _scheduled_meeting(self, tracking="off"):
        if tracking:
            self.series.time_tracking = tracking
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "Guarded", "series_id": self.series.id,
             "start_datetime": "2026-11-02 10:00:00"})
        meeting.action_schedule()
        return meeting

    def test_start_meeting_raises_when_tracking_off(self):
        meeting = self._scheduled_meeting(tracking="off")
        with self.assertRaises(Exception):
            meeting.with_user(self.editor).action_start_meeting()

    def test_point_timing_raises_when_tracking_off(self):
        meeting = self._scheduled_meeting(tracking="off")
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {"meeting_id": meeting.id, "name": "P", "kind": "discussion"})
        with self.assertRaises(Exception):
            item.action_start_timing()

    def test_mark_held_without_start_when_off(self):
        meeting = self._scheduled_meeting(tracking="off")
        meeting.with_user(self.editor).action_mark_held()
        self.assertEqual(meeting.state, "held")
        self.assertFalse(meeting.actual_start_datetime)

    def test_start_meeting_still_works_when_on(self):
        meeting = self._scheduled_meeting(tracking="on")
        meeting.with_user(self.editor).action_start_meeting()
        self.assertTrue(meeting.actual_start_datetime)
```

- [ ] **Step 2: Run, expect failures** (`test_mark_held_without_start_when_off` and `test_start_meeting_still_works_when_on` should already pass; the two raise-tests fail because no guard exists)

- [ ] **Step 3: Implement guards**

`meeting.py` — first line inside the `for meeting in self:` loop of each of the three actions:

```python
            if not meeting.time_tracking_enabled:
                raise UserError(_("Time tracking is disabled for this meeting."))
```

`topic.py` — in `action_start_timing` (before the state check, after `meeting._lock_live_workflow()`):

```python
            if not meeting.time_tracking_enabled:
                raise UserError(_("Time tracking is disabled for this meeting."))
```

In `action_pause_timing`, after the group check loop:

```python
        if any(not item.meeting_id.time_tracking_enabled for item in self):
            raise UserError(_("Time tracking is disabled for this meeting."))
```

- [ ] **Step 4: Run tests, expect pass.** Full class: `--test-tags=/community_meetings:TestOptionalTiming` → 8 tests, `0 failed, 0 error(s)`.

---

### Task 3: Capabilities flag + live view + form view rendering

**Files:**
- Modify: `community_meetings/models/meeting.py` (`get_live_capabilities` L442-451)
- Modify: `community_meetings/static/src/live_meeting/live_meeting.js` (`canEditDiscussion` L282, `navigateItem` L463, `pointOutcome` none)
- Modify: `community_meetings/static/src/live_meeting/live_meeting.xml` (topbar L9-13, header details L32-37, point timer L107-112)
- Modify: `community_meetings/views/meeting_views.xml` (header buttons L38-41, actual fields L58-61)
- Test: `community_meetings/tests/test_optional_timing.py`

**Interfaces:**
- Consumes: `time_tracking_enabled` (Task 1).
- Produces: capabilities key `time_tracking` (Boolean) consumed by JS.

- [ ] **Step 1: Failing test** (append)

```python
    def test_capabilities_include_time_tracking(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "Cap", "series_id": self.series.id})
        self.series.time_tracking = "off"
        self.assertFalse(meeting.get_live_capabilities()["time_tracking"])
        meeting.invalidate_recordset(["time_tracking_enabled"])
        self.series.time_tracking = "on"
        meeting.invalidate_recordset(["time_tracking_enabled"])
        self.assertTrue(meeting.get_live_capabilities()["time_tracking"])
```

- [ ] **Step 2: Run, expect failure** (KeyError `time_tracking`).

- [ ] **Step 3: Implement capabilities**

In `get_live_capabilities` return dict add:

```python
            "time_tracking": self.time_tracking_enabled,
```

- [ ] **Step 4: Run test, expect pass.**

- [ ] **Step 5: Live view JS**

In `live_meeting.js`:

```javascript
    get timingEnabled() { return Boolean(this.state.capabilities?.time_tracking); }
```

Change `canEditDiscussion` (L282-284) to:

```javascript
    canEditDiscussion(item) {
        if (this.locked) return false;
        if (!this.timingEnabled) return !this.meetingPaused;
        return this.draftingMinutes || (!this.meetingPaused && Boolean(item.actual_started_at));
    }
```

In `navigateItem` (L463-481), wrap the pause sweep in `if (this.timingEnabled) { ... }`.

- [ ] **Step 6: Live view XML**

Topbar (L9-13): wrap the three buttons Start/Pause/Resume with `t-if="... and this.timingEnabled"` (each existing `t-if` gets ` and timingEnabled` appended); the `markHeld` "Finish Meeting" button keeps its condition; "Record as Already Held" becomes `t-if="state.meeting.state === 'scheduled' and !state.meeting.actual_start_datetime and !timingEnabled"`.
Header details (L35-37): add `t-if="timingEnabled"` to Actual start / Actual end / Actual duration divs.
Point timer block (L107-112): outer div condition gains `and timingEnabled`.

- [ ] **Step 7: Form view**

`meeting_views.xml` header: `action_start_meeting` (L38), `action_pause_meeting` (L39), `action_resume_meeting` (L40) each get `or not time_tracking_enabled` appended to their `invisible` expressions; "Record as Already Held" (L42) gains `and time_tracking_enabled`. Sheet (L58-61): `actual_start_datetime` gets `and time_tracking_enabled` in its `invisible`; same for `actual_end_datetime` and `actual_duration_minutes`.

- [ ] **Step 8: Full module test run + JS syntax check**

`node --check community_meetings/static/src/live_meeting/live_meeting.js` locally; full `--test-tags=/community_meetings` in container. Expected: `0 failed, 0 error(s)` (now 165 tests).

- [ ] **Step 9: Manual smoke (dev server)**

Open Live Meeting on a series with tracking off: no Start button, notes editable without "Begin point", Finish works. Toggle company setting off → standalone meeting shows same. Verify Start works on a tracking-on series.
