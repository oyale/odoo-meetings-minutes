# Agenda proposals as proposed points — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a proposal a persistent point (`community.meeting.topic`, state `proposed`) that is reviewed (include/postpone/discard) when preparing the next meeting, removing the separate `agenda.proposal` model.

**Architecture:** Proposal metadata moves onto `topic`; eligibility (`proposal.grant`, `proposal.group.policy`) is kept. The point wizard gains a propose mode. Candidate discovery and the new-meeting wizard's review step gain proposed points and a per-line decision.

**Tech Stack:** Odoo 18 (Python models, XML views, OWL not needed), Odoo `TransactionCase` tests.

**Spec:** `docs/superpowers/specs/2026-10-16-agenda-proposals-convergence-design.md`

## Global Constraints

- Module `community_meetings` only. No new dependencies. No migration (development DB).
- Keep eligibility: `community.meeting.proposal.grant`, `community.meeting.proposal.group.policy`, `group_agenda_proposer`, `submit_on_behalf`.
- Never forge the proposer/attribution; `proposal_status` and the review fields are set only through workflow actions.
- Proposals target the series only (no destination meeting field).

### Container test command (used by every task)

```bash
ssh meeting-minutes.local 'sudo -n systemctl stop odoo; sudo -n -u odoo /home/odoo/pyenv/versions/odoo/bin/python /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d meeting_minutes -u community_meetings --test-enable --stop-after-init --no-http --test-tags "/community_meetings:<Tag>" --logfile=/tmp/plan.log --log-level=test; sudo -n systemctl start odoo; grep -Ei "tests when loading|ERROR:|FAIL:" /tmp/plan.log | tail'
```

Expected tail: `0 failed, 0 error(s) of N tests`.

---

### Task 1: Proposal fields and workflow on the point

**Files:**
- Modify: `community_meetings/models/topic.py` (class `MeetingTopic`)
- Test: `community_meetings/tests/test_proposals_convergence.py` (create)
- Modify: `community_meetings/tests/__init__.py`

**Interfaces:**
- Produces (later tasks rely on these): fields `proposal_status`, `proposer_partner_id`,
  `submitted_by_user_id`, `submitted_at`, `proposal_response`, `responded_by_id`,
  `responded_at`; methods `action_accept_proposal()`, `action_reject_proposal(response=False)`,
  `action_withdraw_proposal()`.

- [ ] **Step 1: Write the failing test**

Create `community_meetings/tests/test_proposals_convergence.py`:

```python
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProposalConvergence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Proposal Editor", "login": "proposal-editor-conv-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
                cls.env.ref("community_meetings.group_agenda_proposer").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create(
            {"name": "Proposal series"}
        )

    def test_review_actions_drive_the_status(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).create({
            "name": "Proposed point", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            "state": "proposed", "proposal_status": "submitted",
            "proposer_partner_id": self.editor.partner_id.id,
            "submitted_by_user_id": self.editor.id,
        })
        self.assertEqual(topic.state, "proposed")
        topic.action_accept_proposal()
        self.assertEqual(topic.state, "open")
        self.assertEqual(topic.proposal_status, "accepted")
        self.assertTrue(topic.responded_at)

    def test_withdraw_only_by_proposer_while_submitted(self):
        other = self.env["res.users"].create({
            "name": "Other", "login": "proposal-other-conv-test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        topic = self.env["community.meeting.topic"].with_user(self.editor).create({
            "name": "P", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            "state": "proposed", "proposal_status": "submitted",
            "proposer_partner_id": self.editor.partner_id.id,
            "submitted_by_user_id": self.editor.id,
        })
        with self.assertRaises(AccessError), self.cr.savepoint():
            topic.with_user(other).action_withdraw_proposal()
        topic.action_withdraw_proposal()
        self.assertEqual(topic.proposal_status, "withdrawn")

    def test_status_cannot_be_written_directly(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).create({
            "name": "P2", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        with self.assertRaises(UserError), self.cr.savepoint():
            topic.write({"proposal_status": "accepted"})
```

Register in `community_meetings/tests/__init__.py`:

```python
from . import test_proposals_convergence
```

- [ ] **Step 2: Run the test to verify it fails**

Run the container command with `<Tag>` = `TestProposalConvergence`.
Expected: FAIL — unknown field `proposal_status`.

- [ ] **Step 3: Add the fields**

In `community_meetings/models/topic.py`, inside `MeetingTopic` after `related_topic_ids`:

```python
    proposer_partner_id = fields.Many2one("res.partner", ondelete="restrict", index=True)
    submitted_by_user_id = fields.Many2one("res.users", readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    proposal_status = fields.Selection(
        [("submitted", "Submitted"), ("accepted", "Accepted"),
         ("rejected", "Rejected"), ("withdrawn", "Withdrawn")],
        copy=False,
    )
    proposal_response = fields.Text()
    responded_by_id = fields.Many2one("res.users", readonly=True)
    responded_at = fields.Datetime(readonly=True)
```

- [ ] **Step 4: Guard and add the actions**

In `MeetingTopic.write`, add at the top of the existing method (before the existing guards):

```python
        if {
            "proposal_status", "responded_by_id", "responded_at",
            "submitted_by_user_id", "submitted_at",
        }.intersection(vals):
            raise UserError(_("Use a proposal workflow action to change its status."))
```

Add these methods to `MeetingTopic` (after `action_admit`):

```python
    def action_accept_proposal(self):
        self.check_access("write")
        if any(t.state != "proposed" or t.proposal_status != "submitted" for t in self):
            raise UserError(_("Only submitted proposals can be accepted."))
        for topic in self:
            super(MeetingTopic, topic.sudo()).write({
                "state": "open", "proposal_status": "accepted",
                "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
            })
        return True

    def action_reject_proposal(self, response=False):
        self.check_access("write")
        if any(t.proposal_status != "submitted" for t in self):
            raise UserError(_("Only submitted proposals can be rejected."))
        for topic in self:
            super(MeetingTopic, topic.sudo()).write({
                "proposal_status": "rejected", "proposal_response": response,
                "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
            })
        return True

    def action_withdraw_proposal(self):
        self.check_access("write")
        for topic in self:
            if topic.proposal_status != "submitted" or topic.submitted_by_user_id != self.env.user:
                raise AccessError(_("You can withdraw only your own submitted proposal."))
            super(MeetingTopic, topic.sudo()).write({
                "proposal_status": "withdrawn",
                "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
            })
        return True
```

- [ ] **Step 5: Run the test to verify it passes**

Run the container command with `<Tag>` = `TestProposalConvergence`.
Expected: `0 failed, 0 error(s) of 3 tests`.

- [ ] **Step 6: Commit**

```bash
git add community_meetings/models/topic.py community_meetings/tests/test_proposals_convergence.py community_meetings/tests/__init__.py
git commit -m "feat(points): add proposal fields and review actions to points"
```

---

### Task 2: Create a proposal (reuse the point wizard)

**Files:**
- Modify: `community_meetings/models/topic.py` (capability + `_create_proposal` + `submit_on_behalf`)
- Modify: `community_meetings/models/creation_wizard.py` (`PointWizard` propose mode)
- Test: `community_meetings/tests/test_proposals_convergence.py`

**Interfaces:**
- Consumes: Task 1 fields/methods.
- Produces: `MeetingTopic._has_proposal_capability()`; `MeetingTopic._validate_proposal_target(series_id)`;
  `MeetingTopic.propose(values)` → a proposed topic; `MeetingTopic.submit_on_behalf(partner_id, values)`;
  `PointWizard.propose` (Boolean) and `PointWizard.proposal_series_id` (Many2one).

- [ ] **Step 1: Write the failing test**

Append to `TestProposalConvergence`:

```python
    def test_propose_creates_a_proposed_topic(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "New idea", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            "description": "<p>Explain</p>", "priority": "2",
        })
        self.assertEqual(topic.state, "proposed")
        self.assertEqual(topic.proposal_status, "submitted")
        self.assertEqual(topic.proposer_partner_id, self.editor.partner_id)
        self.assertEqual(topic.submitted_by_user_id, self.editor)
        self.assertEqual(topic.priority, "2")

    def test_ineligible_user_cannot_propose(self):
        outsider = self.env["res.users"].create({
            "name": "Out", "login": "proposal-outsider-conv-test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["community.meeting.topic"].with_user(outsider).propose({
                "name": "Nope", "series_id": self.series.id,
                "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            })
```

- [ ] **Step 2: Run the test to verify it fails**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: FAIL — `propose` not defined.

- [ ] **Step 3: Add capability + creation to the topic**

In `community_meetings/models/topic.py`, add to `MeetingTopic`:

```python
    @api.model
    def _has_proposal_capability(self):
        user = self.env.user
        if user.has_group("community_meetings.group_agenda_proposer"):
            return True
        policy_groups = self.env["community.meeting.proposal.group.policy"].sudo().search(
            [("active", "=", True)]
        ).group_id
        return bool(user.groups_id & policy_groups)

    @api.model
    def _validate_proposal_target(self, company_id, series_id):
        if company_id not in self.env.user.company_ids.ids:
            raise AccessError(_("You cannot submit proposals for this company."))
        series = self.env["community.meeting.series"].sudo().browse(series_id).exists()
        if not series or series.company_id.id != company_id or not series.active:
            raise ValidationError(_("The selected proposal scope is unavailable."))
        return series

    @api.model
    def propose(self, values):
        values = dict(values)
        company_id = values.get("company_id", self.env.company.id)
        series = self._validate_proposal_target(company_id, values.get("series_id"))
        values["company_id"] = company_id
        values["series_id"] = series.id
        return self._create_proposal(values, self.env.user.partner_id, self.env.uid)

    @api.model
    def _create_proposal(self, values, proposer_partner, submitted_by):
        if not self._has_proposal_capability():
            raise AccessError(_("You are not authorized to submit agenda proposals."))
        values = dict(values)
        for guarded in ("proposal_status", "submitted_by_user_id", "submitted_at"):
            values.pop(guarded, None)
        values.update({
            "state": "proposed",
            "proposal_status": "submitted",
            "proposer_partner_id": proposer_partner.id,
            "submitted_by_user_id": submitted_by.id if hasattr(submitted_by, "id") else submitted_by,
            "submitted_at": fields.Datetime.now(),
        })
        return self.sudo().create(values)

    @api.model
    def submit_on_behalf(self, partner_id, values):
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_manager")
        ):
            raise AccessError(_("Only a meeting editor can record a proposal on behalf of a contact."))
        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            raise ValidationError(_("The proposed contact is unavailable."))
        company_id = values.get("company_id", self.env.company.id)
        series = self._validate_proposal_target(company_id, values.get("series_id"))
        today = fields.Date.context_today(self)
        grant = self.env["community.meeting.proposal.grant"].sudo().search([
            ("partner_id", "=", partner.id), ("company_id", "=", company_id), ("active", "=", True),
            "|", ("active_from", "=", False), ("active_from", "<=", today),
            "|", ("active_until", "=", False), ("active_until", ">=", today),
            "|", ("series_id", "=", False), ("series_id", "=", series.id),
        ], limit=1)
        if not grant:
            raise AccessError(_("This contact is not eligible to propose topics in the selected scope."))
        values = dict(values, company_id=company_id, series_id=series.id)
        return self._create_proposal(values, partner, self.env.uid)
```

`_create_proposal` uses `sudo().create` on purpose: it has already enforced the proposer and attribution rules; it must bypass the `create` guard that forbids `state`/`proposal_status` in ordinary writes. Also note `sudo()` avoids the ACL that hides the series from a plain proposer.

- [ ] **Step 4: Add propose mode to the point wizard**

In `community_meetings/models/creation_wizard.py`, in `PointWizard`:

```python
    propose = fields.Boolean()
    proposal_series_id = fields.Many2one("community.meeting.series")
```

Change `_compute_scope` to include `proposal_series_id`:

```python
    @api.depends("meeting_id", "creation_wizard_id.series_id", "creation_wizard_id.company_id", "proposal_series_id")
    def _compute_scope(self):
        for w in self:
            parent = w.meeting_id or w.creation_wizard_id or w.proposal_series_id
            w.series_id = parent.series_id if parent else False
            w.company_id = parent.company_id if parent else self.env.company
```

Change `action_save` to branch to proposal creation:

```python
    def action_save(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_point_wizard WHERE id=%s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["included", "created_item_id"])
        if self.propose:
            if not self.proposal_series_id:
                raise ValidationError(_("Choose a series for the proposal."))
            if not self.name or not self.agenda_type_id:
                raise ValidationError(_("Enter a title and select a point type."))
            self.env["community.meeting.topic"].propose(self._proposal_values())
            self.included = True
            return {"type": "ir.actions.act_window_close"}
        if not self.name and not self.topic_id:
            raise ValidationError(_("Enter a title or select an existing point."))
        if self.estimated_minutes < 0:
            raise ValidationError(_("Estimated minutes cannot be negative."))
        if self.meeting_id:
            if not self.created_item_id:
                self.created_item_id = self.env["community.meeting.agenda.item"].create(
                    self._item_values(self.meeting_id)
                )
            self._write_related_points(self.created_item_id.topic_id)
        elif not self.creation_wizard_id:
            raise UserError(_("Choose a meeting first."))
        self.included = True
        return (
            self.creation_wizard_id._reload()
            if self.creation_wizard_id
            else {"type": "ir.actions.act_window_close"}
        )

    def _proposal_values(self):
        return {
            "name": self.name,
            "description": self.description,
            "agenda_type_id": self.agenda_type_id.id,
            "priority": self.priority,
            "deadline": self.deadline,
            "estimated_minutes": self.estimated_minutes,
            "followup_policy": self.followup_policy,
            "default_followup_kind": self.default_followup_kind,
            "series_id": self.proposal_series_id.id,
            "company_id": self.proposal_series_id.company_id.id,
        }
```

- [ ] **Step 5: Run the test to verify it passes**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: `0 failed, 0 error(s) of 5 tests`.

- [ ] **Step 6: Commit**

```bash
git add community_meetings/models/topic.py community_meetings/models/creation_wizard.py community_meetings/tests/test_proposals_convergence.py
git commit -m "feat(points): propose a point through the point wizard"
```

---

### Task 3: Proposals as candidates and their inclusion

**Files:**
- Modify: `community_meetings/models/agenda_preparation.py` (`_agenda_candidates` and `_include_agenda_candidate`)
- Test: `community_meetings/tests/test_proposals_convergence.py`

**Interfaces:**
- Consumes: Task 2 `propose`.
- Produces: candidates with key `proposal:<topic_id>`; `_include_agenda_candidate` handling them.

- [ ] **Step 1: Write the failing test**

Append:

```python
    def test_proposed_series_point_is_a_candidate(self):
        self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Candidate proposal", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        candidates = self.env["community.meeting"]._agenda_candidates(
            self.series, "2026-11-01 10:00:00"
        )
        self.assertTrue(any(c.get("reason") == "Proposed point" for c in candidates))

    def test_including_a_proposal_opens_it_and_creates_a_participation(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Included proposal", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Next", "series_id": self.series.id,
            "start_datetime": "2026-11-01 10:00:00",
        })
        meeting._include_agenda_candidate({"key": f"proposal:{topic.id}"})
        self.assertEqual(topic.state, "open")
        self.assertEqual(topic.proposal_status, "accepted")
        self.assertTrue(meeting.agenda_item_ids.filtered(lambda i: i.topic_id == topic))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: FAIL — proposals not returned / include not handled.

- [ ] **Step 3: Add proposals to candidate discovery**

In `community_meetings/models/agenda_preparation.py`, inside `_agenda_candidates`, after the `promoted` block and before `results, represented = [], set()`, add:

```python
        proposals = self.env["community.meeting.topic"].search([
            ("series_id", "=", series.id),
            ("state", "=", "proposed"),
            ("proposal_status", "=", "submitted"),
        ])
```

Then, in the results loop (after the promoted `for topic in promoted:` loop and before `return results`), add:

```python
        for proposal in proposals:
            results.append({
                "key": f"proposal:{proposal.id}", "topic_id": proposal.id,
                "name": proposal.name, "origin_meeting_id": False,
                "reason": _("Proposed point"),
            })
```

- [ ] **Step 4: Handle inclusion**

In `_include_agenda_candidate`, add a branch before the existing `if candidate.get("transfer_id")`:

```python
        if str(candidate["key"]).startswith("proposal:"):
            topic = self.env["community.meeting.topic"].browse(candidate["topic_id"])
            topic.action_accept_proposal()
            item = self.env["community.meeting.agenda.item"].create({
                "meeting_id": self.id, "topic_id": topic.id,
            })
            return item
```

- [ ] **Step 5: Run the test to verify it passes**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: `0 failed, 0 error(s) of 7 tests`.

- [ ] **Step 6: Commit**

```bash
git add community_meetings/models/agenda_preparation.py community_meetings/tests/test_proposals_convergence.py
git commit -m "feat(points): offer proposed points as meeting candidates"
```

---

### Task 4: Review decisions (include / postpone / discard)

**Files:**
- Modify: `community_meetings/models/creation_wizard.py` (`CarryReviewLine`, `MeetingCreateWizard.action_finish`)
- Modify: `community_meetings/views/preparation_views.xml` (wizard carry step)
- Test: `community_meetings/tests/test_proposals_convergence.py`

**Interfaces:**
- Consumes: Task 3 candidates.
- Produces: `CarryReviewLine.decision` (Selection `include`/`postpone`/`discard`, default `include`).

- [ ] **Step 1: Write the failing test**

Append:

```python
    def test_finish_respects_the_review_decision(self):
        accepted = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Accept me", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        postponed = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Postpone me", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        discarded = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Discard me", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        wizard = self.env["community.meeting.create.wizard"].with_user(self.editor).create({
            "step": "carryover", "series_id": self.series.id, "name": "Review meeting",
            "start_datetime": "2026-11-01 10:00:00", "duration_hours": 1,
            "carry_line_ids": [
                (0, 0, {"candidate_key": f"proposal:{accepted.id}", "decision": "include"}),
                (0, 0, {"candidate_key": f"proposal:{postponed.id}", "decision": "postpone"}),
                (0, 0, {"candidate_key": f"proposal:{discarded.id}", "decision": "discard"}),
            ],
        })
        res = wizard.action_finish()
        meeting = self.env["community.meeting"].browse(res["res_id"])
        self.assertEqual(accepted.state, "open")
        self.assertEqual(accepted.proposal_status, "accepted")
        self.assertEqual(postponed.proposal_status, "submitted")
        self.assertEqual(discarded.proposal_status, "rejected")
        self.assertTrue(meeting.agenda_item_ids.filtered(lambda i: i.topic_id == accepted))
        self.assertFalse(meeting.agenda_item_ids.filtered(lambda i: i.topic_id == postponed))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: FAIL — unknown field `decision`.

- [ ] **Step 3: Add the decision field and dispatch**

In `community_meetings/models/creation_wizard.py`, replace `accept = fields.Boolean(string="Include")` in `CarryReviewLine` with:

```python
    decision = fields.Selection(
        [("include", "Include"), ("postpone", "Postpone"), ("discard", "Discard")],
        default="include", required=True,
    )
```

In `MeetingCreateWizard.action_finish`, replace the carryover include loop:

```python
            for line in self.carry_line_ids.filtered(lambda l: l.decision == "include"):
                meeting._include_agenda_candidate({"key": line.candidate_key})
            for line in self.carry_line_ids.filtered(lambda l: l.decision == "discard"):
                topic = self.env["community.meeting.topic"].browse(
                    int(line.candidate_key.split(":")[1])
                ) if line.candidate_key.startswith("proposal:") else None
                if topic:
                    topic.action_reject_proposal()
```

Postponed lines simply do nothing.

- [ ] **Step 4: Update the wizard view**

In `community_meetings/views/preparation_views.xml`, in `view_meeting_create_wizard`, replace the carryover list field:

```xml
<field name="carry_line_ids" nolabel="1" invisible="not carry_line_ids"><list editable="bottom" create="0" delete="0"><field name="decision" widget="radio" options="{'horizontal': True}"/><field name="name"/><field name="origin_meeting_id"/><field name="reason"/></list></field>
```

- [ ] **Step 5: Run the test to verify it passes**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: `0 failed, 0 error(s) of 8 tests`.

- [ ] **Step 6: Run the carryover regression**

Run: container command, `<Tag>` = `TestAgendaCarryover,TestMeetingDomain`.
Expected: `0 failed, 0 error(s)` (the `include`/`accept` rename must not break carryover inclusion).

- [ ] **Step 7: Commit**

```bash
git add community_meetings/models/creation_wizard.py community_meetings/views/preparation_views.xml community_meetings/tests/test_proposals_convergence.py
git commit -m "feat(points): include, postpone or discard candidates when creating a meeting"
```

---

### Task 5: "Propose a point" entry point

**Files:**
- Modify: `community_meetings/models/creation_wizard.py` (`PointWizard._open`)
- Modify: `community_meetings/views/preparation_views.xml` (`view_point_wizard`)
- Modify: `community_meetings/views/series_views.xml` (series form button)
- Modify: `community_meetings/views/proposal_views.xml` (replace the menu with "Propose a point")
- Test: manual (view load validated by the module update in Step 4)

**Interfaces:**
- Consumes: Task 2 propose mode.

- [ ] **Step 1: Add a proposal opener**

In `community_meetings/models/preparation.py`, inside `MeetingSeries`, add:

```python
    def action_propose_point(self):
        self.ensure_one()
        return self.env["community.meeting.point.wizard"]._open({
            "default_propose": True,
            "default_proposal_series_id": self.id,
        })
```

- [ ] **Step 2: Show the series field in propose mode**

In `community_meetings/views/preparation_views.xml`, in `view_point_wizard`, add after the `company_id` field:

```xml
<field name="propose" invisible="1"/><field name="proposal_series_id" invisible="not propose" domain="[('company_id', '=', company_id), ('active', '=', True)]"/>
```

- [ ] **Step 3: Series button + menu**

In `community_meetings/views/series_views.xml`, inside the series form `button_box`, add:

```xml
<button name="action_propose_point" type="object" class="oe_stat_button" icon="fa-lightbulb-o" groups="base.group_user">
    <span class="o_stat_text">Propose a point</span>
</button>
```

In `community_meetings/views/proposal_views.xml`, replace its content with a single menu opening the wizard:

```xml
<odoo>
    <record id="action_propose_point" model="ir.actions.act_window">
        <field name="name">Propose a Point</field>
        <field name="res_model">community.meeting.point.wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
        <field name="context">{'default_propose': True}</field>
    </record>
    <menuitem id="menu_propose_point" name="Propose a Point" parent="community_meetings.menu_community_meetings_root" action="action_propose_point" sequence="20" groups="base.group_user"/>
</odoo>
```

- [ ] **Step 4: Load the module and verify**

Run the container command with `<Tag>` = `TestProposalConvergence` (module update loads the views).
Expected: `0 failed`, no `ParseError`/`cannot be located`.

- [ ] **Step 5: Commit**

```bash
git add community_meetings/models/preparation.py community_meetings/views/preparation_views.xml community_meetings/views/series_views.xml community_meetings/views/proposal_views.xml
git commit -m "feat(points): propose a point from the menu and the series"
```

---

### Task 6: "Proposals to review" block

**Files:**
- Modify: `community_meetings/models/topic.py` (`MeetingTopic.pending_proposal_ids` compute) — or add a helper on series
- Modify: `community_meetings/views/proposal_views.xml` (block views)
- Test: `community_meetings/tests/test_proposals_convergence.py`

**Interfaces:**
- Consumes: Task 1 actions.
- Produces: series field `pending_proposal_ids` (One2many, computed) with `action_accept_proposal`/`action_reject_proposal` buttons in the view.

- [ ] **Step 1: Write the failing test**

Append:

```python
    def test_pending_proposals_are_listed_on_the_series(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "On the series", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        self.assertIn(topic, self.series.pending_proposal_ids)
        topic.action_reject_proposal()
        self.assertNotIn(topic, self.series.pending_proposal_ids)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: FAIL — `pending_proposal_ids` not defined.

- [ ] **Step 3: Add the computed field**

In `community_meetings/models/topic.py`, add a `MeetingSeries` inherit at the end of the file:

```python
class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    pending_proposal_ids = fields.One2many(
        "community.meeting.topic", compute="_compute_pending_proposals",
        groups="community_meetings.group_meeting_editor",
    )

    @api.depends("meeting_ids")
    def _compute_pending_proposals(self):
        for series in self:
            series.pending_proposal_ids = self.env["community.meeting.topic"].search([
                ("series_id", "=", series.id),
                ("state", "=", "proposed"),
                ("proposal_status", "=", "submitted"),
            ])
```

- [ ] **Step 4: Add the series block view**

In `community_meetings/views/proposal_views.xml`, add:

```xml
<record id="view_series_pending_proposals" model="ir.ui.view">
    <field name="name">community.meeting.series.pending.proposals</field>
    <field name="model">community.meeting.series</field>
    <field name="inherit_id" ref="community_meetings.view_community_meeting_series_form"/>
    <field name="arch" type="xml">
        <field name="carryover_policy" position="after">
            <div class="alert alert-info" invisible="not pending_proposal_ids">
                <strong>Proposals to review</strong>
                <field name="pending_proposal_ids" nolabel="1" readonly="1">
                    <list create="0" delete="0">
                        <field name="name"/>
                        <field name="proposer_partner_id"/>
                        <field name="priority"/>
                        <button name="action_accept_proposal" type="object" string="Accept"/>
                        <button name="action_reject_proposal" type="object" string="Reject"/>
                    </list>
                </field>
            </div>
        </field>
    </field>
</record>
```

- [ ] **Step 5: Run the test to verify it passes**

Run: container command, `<Tag>` = `TestProposalConvergence`.
Expected: `0 failed, 0 error(s) of 9 tests`.

- [ ] **Step 6: Commit**

```bash
git add community_meetings/models/topic.py community_meetings/views/proposal_views.xml community_meetings/tests/test_proposals_convergence.py
git commit -m "feat(points): review pending proposals from the series"
```

---

### Task 7: Remove the old proposal model and UI

**Files:**
- Create: `community_meetings/models/proposal_eligibility.py` (moved grants/policies)
- Delete: `community_meetings/models/proposal.py`, `community_meetings/models/proposal_wizard.py`
- Modify: `community_meetings/models/__init__.py`, `community_meetings/__manifest__.py`
- Modify: `community_meetings/security/ir.model.access.csv`, `community_meetings/security/rules.xml`
- Delete: `community_meetings/views/proposal_views.xml` old records (replaced in Tasks 5–6)
- Delete: `community_meetings/tests/test_proposals.py`

**Interfaces:**
- Consumes: Tasks 1–6.

- [ ] **Step 1: Move eligibility, delete the proposal model**

Create `community_meetings/models/proposal_eligibility.py` containing the two classes
`CommunityMeetingProposalGroupPolicy` and `CommunityMeetingProposalGrant` exactly as they
are in `models/proposal.py` today (copy them verbatim). Then:

```bash
git rm community_meetings/models/proposal.py community_meetings/models/proposal_wizard.py community_meetings/tests/test_proposals.py
```

- [ ] **Step 2: Update module wiring**

In `community_meetings/models/__init__.py`, replace `from . import proposal` and
`from . import proposal_wizard` with:

```python
from . import proposal_eligibility
```

Keep `views/proposal_views.xml` in `__manifest__.py` (it now holds the propose menu and
the pending-proposals block from Tasks 5–6).

- [ ] **Step 3: Drop the removed model's security**

In `community_meetings/security/ir.model.access.csv`, remove every row whose `model_id:id`
is `model_community_meeting_agenda_proposal` or `model_community_meeting_proposal_accept_wizard`.

In `community_meetings/security/rules.xml`, remove the record rules whose `model_id` is
`model_community_meeting_agenda_proposal` (the proposal ownership/withdraw rules,
including the `base.group_portal` ones).

- [ ] **Step 4: Update the group reference for the proposer capability**

In `community_meetings/models/topic.py`, `_has_proposal_capability` and
`submit_on_behalf` reference `community.meetings.group_agenda_proposer` — confirm the
group still exists in `security/groups.xml` (it does) and that no test references the
removed proposal model.

- [ ] **Step 5: Load the module and verify no dangling references**

Run the container command with `<Tag>` = `TestProposalConvergence`.
Expected: `0 failed`, and the log has no `Field ... does not exist`,
`Model ... not found`, or `External ID not found` for `agenda.proposal`.

- [ ] **Step 6: Full regression**

Run the container command with `<Tag>` = `/community_meetings,-/community_meetings:TestMeetingRevisions`.
Expected: `0 failed, 0 error(s)`.

- [ ] **Step 7: Commit**

```bash
git add -A community_meetings
git commit -m "refactor(points): remove the agenda proposal model, keep eligibility"
```

---

## Self-Review Notes

- Spec coverage: model fields + actions (Task 1); submit via the point wizard + eligibility (Task 2); candidates + include (Task 3); include/postpone/discard + carried postpone (Task 4); propose UI entry (Task 5); series review block (Task 6); removal/cleanup incl. portal ACL/rules (Task 7).
- Type consistency: `proposal_status` values, `decision` values, `propose`/`proposal_series_id`, `_has_proposal_capability`, `_validate_proposal_target`, `_create_proposal`, `submit_on_behalf`, `pending_proposal_ids` are used with the same names across tasks.
- No migration: the old model is deleted without moving rows (development DB), per spec.
- Playwright is not run in this environment; views are validated by the module load plus static checks.
