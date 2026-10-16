# New Point Wizard UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the "new point" wizard so the title/body lead, metadata is grouped, advanced controls (existing point, related points, follow-up policy) sit behind More options, and the live context closes after a single add.

**Architecture:** Core-only changes to `community_meetings`. Add a persistent `related_topic_ids` on `community.meeting.topic` and a transient mirror on the point wizard; persist it when the wizard saves. Add `action_add_point_live` and point the live JS at it. Redesign `view_point_wizard` into sections and add a scoped SCSS rule.

**Tech Stack:** Odoo 18 (Python models, XML views/actions, OWL JS, SCSS), Odoo `TransactionCase` tests.

**Spec:** `docs/superpowers/specs/2026-10-16-point-wizard-ux-design.md`

## Global Constraints

- Module: `community_meetings` only. No new dependencies.
- Do not widen access: never use `sudo` to expose points; rely on topic record rules.
- No `related_topic_ids` value may link a point to itself.
- Keep all existing wizard/live ORM flows green.
- Commit once per task with a conventional message.

### Container test command (used by every task)

The dev DB runs in the `meeting-minutes.local` container. Replace `<Tag>` with the task's test class:

```bash
ssh meeting-minutes.local 'sudo -n systemctl stop odoo; sudo -n -u odoo /home/odoo/pyenv/versions/odoo/bin/python /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d meeting_minutes -u community_meetings --test-enable --stop-after-init --no-http --test-tags "/community_meetings:<Tag>" --logfile=/tmp/plan-test.log --log-level=test; sudo -n systemctl start odoo; grep -Ei "tests when loading|ERROR:|FAIL:" /tmp/plan-test.log | tail'
```

Expected tail: `0 failed, 0 error(s) of N tests`.

---

### Task 1: Related points on the point wizard and the point

**Files:**
- Modify: `community_meetings/models/topic.py` (class `MeetingTopic`)
- Modify: `community_meetings/models/creation_wizard.py` (class `PointWizard`)
- Test: `community_meetings/tests/test_point_wizard.py` (create)
- Modify: `community_meetings/tests/__init__.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `community.meeting.topic.related_topic_ids` → `Many2many("community.meeting.topic")`.
  - `community.meeting.point.wizard.related_topic_ids` → `Many2many("community.meeting.topic")`.
  - `community.meeting.point.wizard.origin_topic_id` → related read-only to `topic_id.origin_topic_id`.
  - `PointWizard._write_related_points(topic)` → writes the wizard's related points onto `topic`, excluding the topic itself.

- [ ] **Step 1: Write the failing test**

Create `community_meetings/tests/test_point_wizard.py`:

```python
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPointWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Point Wizard Editor",
            "login": "point-wizard-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.meeting = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Point wizard meeting",
        })

    def _item(self, name):
        return self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "name": name, "kind": "discussion",
        })

    def test_related_points_persist_on_a_new_point(self):
        related = self._item("Related point")
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "name": "New point",
            "related_topic_ids": [(6, 0, [related.topic_id.id])],
        })
        wizard.action_save()
        self.assertEqual(wizard.created_item_id.topic_id.related_topic_ids, related.topic_id)

    def test_related_points_update_when_reusing_a_point(self):
        existing = self._item("Existing point")
        other = self._item("Other point")
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "topic_id": existing.topic_id.id,
            "related_topic_ids": [(6, 0, [other.topic_id.id])],
        })
        wizard.action_save()
        self.assertEqual(existing.topic_id.related_topic_ids, other.topic_id)

    def test_a_point_never_relates_to_itself(self):
        existing = self._item("Self point")
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "topic_id": existing.topic_id.id,
            "related_topic_ids": [(6, 0, [existing.topic_id.id])],
        })
        wizard.action_save()
        self.assertFalse(existing.topic_id.related_topic_ids)
```

Register it in `community_meetings/tests/__init__.py` (append):

```python
from . import test_point_wizard
```

- [ ] **Step 2: Run the test to verify it fails**

Run the container command with `<Tag>` = `TestPointWizard`.
Expected: FAIL — unknown field `related_topic_ids`.

- [ ] **Step 3: Add the topic field**

In `community_meetings/models/topic.py`, inside `MeetingTopic`, after `estimated_minutes`:

```python
    related_topic_ids = fields.Many2many(
        "community.meeting.topic",
        "community_meeting_topic_related_rel",
        "topic_id",
        "related_topic_id",
        string="Related points",
    )
```

- [ ] **Step 4: Add the wizard fields and persistence**

In `community_meetings/models/creation_wizard.py`, inside `PointWizard` (near `topic_id`):

```python
    related_topic_ids = fields.Many2many(
        "community.meeting.topic",
        "community_meeting_point_wizard_related_rel",
        "wizard_id",
        "topic_id",
        string="Related points",
    )
    origin_topic_id = fields.Many2one(related="topic_id.origin_topic_id", readonly=True)
```

Add the helper and call it from `action_save` (replace the existing `action_save` body's create branch):

```python
    def _write_related_points(self, topic):
        if not topic:
            return
        related = self.related_topic_ids - topic
        topic.write({"related_topic_ids": [(6, 0, related.ids)]})

    def action_save(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_point_wizard WHERE id=%s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["included", "created_item_id"])
        if not self.name and not self.topic_id:
            raise ValidationError(_("Enter a title or select an existing point."))
        if self.estimated_minutes < 0:
            raise ValidationError(_("Estimated minutes cannot be negative."))
        if self.meeting_id and not self.created_item_id:
            self.created_item_id = self.env["community.meeting.agenda.item"].create(
                self._item_values(self.meeting_id)
            )
            self._write_related_points(self.created_item_id.topic_id)
        elif not self.meeting_id and not self.creation_wizard_id:
            raise UserError(_("Choose a meeting first."))
        self.included = True
        return (
            self.creation_wizard_id._reload()
            if self.creation_wizard_id
            else {"type": "ir.actions.act_window_close"}
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Run the container command with `<Tag>` = `TestPointWizard`.
Expected: `0 failed, 0 error(s) of 3 tests`.

- [ ] **Step 6: Run the wider regression**

Run the container command with `<Tag>` = `TestAgendaCarryover,TestMeetingDomain`.
Expected: `0 failed, 0 error(s)`.

- [ ] **Step 7: Commit**

```bash
git add community_meetings/models/topic.py community_meetings/models/creation_wizard.py community_meetings/tests/test_point_wizard.py community_meetings/tests/__init__.py
git commit -m "feat(points): add related points to the point wizard"
```

---

### Task 2: Live single-add context

**Files:**
- Modify: `community_meetings/models/preparation.py` (class `Meeting`)
- Modify: `community_meetings/static/src/live_meeting/live_meeting.js` (`addPoint`)
- Test: `community_meetings/tests/test_point_wizard.py`

**Interfaces:**
- Consumes: `PointWizard._open(context)` (existing).
- Produces: `community.meeting.action_add_point_live()` → action dict whose `context["from_live"]` is `True`.

- [ ] **Step 1: Write the failing test**

Append to `TestPointWizard` in `community_meetings/tests/test_point_wizard.py`:

```python
    def test_live_add_point_marks_the_context(self):
        action = self.env["community.meeting"].with_user(self.editor).action_add_point_live()
        self.assertTrue(action["context"]["from_live"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run the container command with `<Tag>` = `TestPointWizard`.
Expected: FAIL — `action_add_point_live` does not exist.

- [ ] **Step 3: Add the model method**

In `community_meetings/models/preparation.py`, inside `Meeting`, after `action_add_point`:

```python
    def action_add_point_live(self):
        self.ensure_one()
        return self.env["community.meeting.point.wizard"]._open(
            {"default_meeting_id": self.id, "from_live": True}
        )
```

- [ ] **Step 4: Point the live JS at it**

In `community_meetings/static/src/live_meeting/live_meeting.js`, in `addPoint`, change the RPC method:

```js
        const action = await this.orm.call("community.meeting", "action_add_point_live", [[this.meetingId]]);
```

- [ ] **Step 5: Run the test to verify it passes**

Run the container command with `<Tag>` = `TestPointWizard`.
Expected: `0 failed, 0 error(s) of 4 tests`.

- [ ] **Step 6: Commit**

```bash
git add community_meetings/models/preparation.py community_meetings/static/src/live_meeting/live_meeting.js community_meetings/tests/test_point_wizard.py
git commit -m "feat(points): close the point wizard after one add from live"
```

---

### Task 3: Redesign the wizard view and style it

**Files:**
- Modify: `community_meetings/views/preparation_views.xml` (`view_point_wizard`)
- Modify: `community_meetings/static/src/live_meeting/live_meeting.scss`
- Modify: `community_meetings/__manifest__.py` (version bump only)

**Interfaces:**
- Consumes: `related_topic_ids`, `origin_topic_id` (Task 1); `from_live` context (Task 2).
- Produces: nothing consumed later.

- [ ] **Step 1: Replace the wizard arch**

In `community_meetings/views/preparation_views.xml`, replace the whole `view_point_wizard` record with:

```xml
<record id="view_point_wizard" model="ir.ui.view"><field name="name">community.meeting.point.wizard</field><field name="model">community.meeting.point.wizard</field>
<field name="arch" type="xml"><form string="Add a point" class="o_meeting_point_wizard">
<field name="meeting_id" invisible="1"/><field name="creation_wizard_id" invisible="1"/><field name="series_id" invisible="1"/><field name="company_id" invisible="1"/>
<div class="o_meeting_point_context text-muted" invisible="not meeting_id"><i class="fa fa-calendar-o" aria-hidden="true"/> Adding to <field name="meeting_id" readonly="1" nolabel="1" options="{'no_open': True}"/></div>
<div class="oe_title" invisible="topic_id"><label for="name" string="What is this point about?"/><h1><field name="name" placeholder="A clear one-line title"/></h1></div>
<group invisible="topic_id"><field name="agenda_type_id"/></group>
<div class="o_meeting_point_help text-muted" invisible="topic_id">Explain the subject so any attendee can follow it. Add the links or documents needed to act on it.</div>
<field name="description" widget="html" invisible="topic_id"/>
<group invisible="topic_id"><group string="Planning"><field name="priority"/><field name="deadline"/><field name="estimated_minutes"/></group></group>
<group invisible="topic_id"><field name="more_options"/></group>
<group string="More options" invisible="not more_options and not topic_id">
    <field name="topic_id" options="{'no_create': True}" domain="[('company_id', '=', company_id)]"/>
    <field name="origin_topic_id" readonly="1" invisible="not origin_topic_id"/>
    <field name="related_topic_ids" widget="many2many_tags" domain="[('company_id', '=', company_id)]"/>
    <field name="followup_policy"/>
    <field name="default_followup_kind" invisible="followup_policy in ['activity', 'todo']"/>
</group>
<footer>
    <button name="action_save" type="object" string="Add point" class="btn-primary"/>
    <button name="action_save_another" type="object" string="Add and continue" invisible="context.get('from_live')"/>
    <button name="action_cancel" type="object" string="Cancel"/>
</footer>
</form></field></record>
```

- [ ] **Step 2: Add the scoped style**

Append to `community_meetings/static/src/live_meeting/live_meeting.scss`:

```scss
.o_meeting_point_wizard {
    .o_meeting_point_context { margin-bottom: 0.75rem; }
    .oe_title { margin-bottom: 0.5rem; }
    .o_meeting_point_help { margin: 0.5rem 0 0.25rem; font-size: 0.875rem; }
    .o_field_html .note-editable, .o_field_html .odoo-editor-editable { min-height: 12rem; }
}
.modal-dialog:has(.o_meeting_point_wizard) { max-width: 720px; }
@media (max-width: 480px) {
    .o_meeting_point_wizard .modal-dialog { max-width: 100%; }
}
```

- [ ] **Step 3: Bump the version**

In `community_meetings/__manifest__.py`, bump `"version": "18.0.3.0.6"` → `"18.0.3.0.7"`.

- [ ] **Step 4: Load the view to verify it parses and rebuilds**

Run the container command with `<Tag>` = `TestPointWizard`.
Expected: `0 failed, 0 error(s)`, and the log contains no `ParseError`/`Element ... cannot be located`.

- [ ] **Step 5: Static checks**

```bash
python3 -c "import xml.dom.minidom; xml.dom.minidom.parse('community_meetings/views/preparation_views.xml')"
node --check community_meetings/static/src/live_meeting/live_meeting.js
git diff --check
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add community_meetings/views/preparation_views.xml community_meetings/static/src/live_meeting/live_meeting.scss community_meetings/__manifest__.py
git commit -m "feat(points): redesign the new point wizard layout"
```

---

## Self-Review Notes

- Spec coverage: layout (Task 3), default/advanced split (Task 3), related points + origin (Task 1), live single-add (Task 2), styling (Task 3), tests (Tasks 1–3). Attachments/duration-default/cross-series are out of scope per spec.
- Type consistency: `related_topic_ids`, `origin_topic_id`, `_write_related_points`, `action_add_point_live`, `from_live` used consistently across tasks.
- Browser Playwright is not run in this environment; the view is verified by module load plus static checks.
