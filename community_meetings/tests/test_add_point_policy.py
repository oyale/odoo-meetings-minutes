from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAddPointPolicy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Policy Editor",
                "login": "add-point-policy-editor-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                        ],
                    )
                ],
            }
        )
        cls.series = (
            cls.env["community.meeting.series"].with_user(cls.editor).create({"name": "Add point policy series"})
        )

    def _meeting(self, **vals):
        return (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(dict({"name": "Policy meeting", "series_id": self.series.id}, **vals))
        )

    def _scheduled(self, meeting):
        meeting.start_datetime = "2026-11-02 10:00:00"
        meeting.action_schedule()
        return meeting

    # --- effective-mode resolution ---

    def test_company_default_is_ongoing(self):
        meeting = self._meeting()
        self.assertEqual(meeting.add_point_policy, "ongoing")

    def test_series_overrides_company(self):
        self.series.add_point_policy = "draft"
        meeting = self._meeting()
        self.assertEqual(meeting.add_point_policy, "draft")

    def test_standalone_meeting_follows_company(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Solo"})
        self.env.company.meeting_add_point_policy = "draft"
        meeting.invalidate_recordset(["add_point_policy"])
        self.assertEqual(meeting.add_point_policy, "draft")

    # --- computed allowance ---

    def test_draft_only_blocks_scheduled(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        self.assertFalse(meeting.add_point_allowed)

    def test_before_start_allows_scheduled_not_started(self):
        self.series.add_point_policy = "scheduled"
        meeting = self._scheduled(self._meeting())
        self.assertTrue(meeting.add_point_allowed)
        meeting.action_start_meeting()
        self.assertFalse(meeting.add_point_allowed)

    def test_ongoing_allows_started_meeting(self):
        meeting = self._scheduled(self._meeting())
        meeting.action_start_meeting()
        self.assertTrue(meeting.add_point_allowed)
        meeting.action_mark_held()
        self.assertFalse(meeting.add_point_allowed)

    def test_never_allowed_after_held(self):
        for policy in ("draft", "scheduled", "ongoing"):
            self.series.add_point_policy = policy
            meeting = self._scheduled(self._meeting())
            meeting.action_mark_held()
            self.assertFalse(meeting.add_point_allowed)

    # --- server guards ---

    def test_action_add_point_raises_when_blocked(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).action_add_point()
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).action_add_point_live()

    def test_action_add_point_opens_when_allowed(self):
        meeting = self._scheduled(self._meeting())
        self.assertTrue(meeting.with_user(self.editor).action_add_point()["context"]["default_meeting_id"])

    def test_wizard_save_guarded(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        wizard = (
            self.env["community.meeting.point.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Blocked point",
                }
            )
        )
        with self.assertRaises(UserError):
            wizard.action_save()

    def test_capabilities_include_can_add_point(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        self.assertFalse(meeting.get_live_capabilities()["can_add_point"])
        self.series.add_point_policy = "ongoing"
        meeting.invalidate_recordset(["add_point_allowed"])
        self.assertTrue(meeting.get_live_capabilities()["can_add_point"])

    def test_direct_creation_obeys_policy_in_every_meeting_phase(self):
        self.editor.groups_id = [(4, self.env.ref("community_meetings.group_meeting_approver").id)]
        items = self.env["community.meeting.agenda.item"].with_user(self.editor)
        for policy in ("draft", "scheduled", "ongoing"):
            self.series.add_point_policy = policy
            for phase in ("draft", "scheduled", "running", "held", "minutes_draft", "approved", "cancelled"):
                with self.subTest(policy=policy, phase=phase):
                    meeting = self._meeting(name=f"{policy} {phase}")
                    items.create({"meeting_id": meeting.id, "name": "Initial agenda"})
                    if phase != "draft":
                        self._scheduled(meeting)
                    if phase == "running":
                        meeting.action_start_meeting()
                    elif phase in ("held", "minutes_draft", "approved"):
                        meeting.action_mark_held()
                        if phase in ("minutes_draft", "approved"):
                            meeting.action_draft_minutes()
                        if phase == "approved":
                            with patch.object(
                                type(self.env["ir.actions.report"]),
                                "_render_qweb_pdf",
                                return_value=(b"%PDF-1.4 fixture", "pdf"),
                            ):
                                meeting.action_approve_minutes()
                    elif phase == "cancelled":
                        meeting.action_cancel()
                    allowed = (
                        phase == "draft"
                        or (phase == "scheduled" and policy != "draft")
                        or (phase == "running" and policy == "ongoing")
                    )
                    values = {"meeting_id": meeting.id, "name": "Additional point"}
                    if allowed:
                        self.assertTrue(items.create(values))
                    else:
                        with self.assertRaises(UserError), self.cr.savepoint():
                            items.create(values)

    def test_one2many_defaults_and_mixed_batch_cannot_bypass_policy(self):
        self.series.add_point_policy = "draft"
        allowed = self._meeting(name="Allowed")
        blocked = self._scheduled(self._meeting(name="Blocked"))
        items = self.env["community.meeting.agenda.item"].with_user(self.editor)
        with self.assertRaises(UserError), self.cr.savepoint():
            blocked.write({"agenda_item_ids": [(0, 0, {"name": "One2many bypass"})]})
        with self.assertRaises(UserError), self.cr.savepoint():
            items.with_context(default_meeting_id=blocked.id).create({"name": "Default bypass"})
        before = items.search_count([])
        with self.assertRaises(UserError), self.cr.savepoint():
            items.create(
                [
                    {"meeting_id": allowed.id, "name": "Allowed part"},
                    {"meeting_id": blocked.id, "name": "Blocked part"},
                ]
            )
        self.assertEqual(items.search_count([]), before)
        self.assertTrue(items.with_context(default_meeting_id=allowed.id).create({"name": "Default allowed"}))

    def test_required_approval_adaptation_is_not_a_public_creation_bypass(self):
        self.series.add_point_policy = "draft"
        meetings = self.env["community.meeting"]
        for phase in ("scheduled", "held", "minutes_draft"):
            meeting = self._scheduled(self._meeting(name=f"Required approval {phase}"))
            if phase in ("held", "minutes_draft"):
                meeting.action_mark_held()
            if phase == "minutes_draft":
                meeting.action_draft_minutes()
            meetings |= meeting
        self.series.write({"has_minutes_approval_point": True})
        for meeting in meetings:
            self.assertEqual(len(meeting.agenda_item_ids.filtered(lambda row: row.kind == "minutes_approval")), 1)
            for kind in ("discussion", "minutes_approval"):
                with self.subTest(phase=meeting.state, kind=kind), self.assertRaises(UserError), self.cr.savepoint():
                    self.env["community.meeting.agenda.item"].with_user(self.editor).with_context(
                        _meeting_required_minutes_approval=True,
                    ).create({"meeting_id": meeting.id, "name": "Forged structural point", "kind": kind})

    def test_carryover_acceptance_obeys_destination_policy(self):
        self.series.add_point_policy = "draft"
        source = self._meeting(name="Carry source", start_datetime="2026-11-01 10:00:00")
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": source.id,
                    "name": "Source point",
                }
            )
        )
        destination = self._scheduled(self._meeting(name="Carry destination"))
        transfer = (
            self.env["community.meeting.carryover"]
            .with_user(self.editor)
            .create(
                {
                    "origin_model": "agenda_item",
                    "origin_record_id": item.id,
                    "destination_meeting_id": destination.id,
                }
            )
        )
        with self.assertRaises(UserError), self.cr.savepoint():
            transfer.action_accept(destination.id)
        self.assertFalse(transfer.destination_item_id)
        self.assertNotEqual(transfer.status, "accepted")

    def test_creation_requires_write_access_to_the_target_meeting(self):
        other = self.env["res.users"].create(
            {
                "name": "Other policy editor",
                "login": "other-policy-editor",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_editor").id,
                        ],
                    )
                ],
            }
        )
        private = self.env["community.meeting"].with_user(other).create({"name": "Another organizer"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["community.meeting.agenda.item"].with_user(self.editor).create(
                {
                    "meeting_id": private.id,
                    "name": "Unauthorized point",
                }
            )

    def test_creation_preserves_company_and_editor_boundaries(self):
        company = self.env["res.company"].create({"name": "Other policy company"})
        other_editor = self.env["res.users"].create(
            {
                "name": "Other company editor",
                "login": "other-company-policy-editor",
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_editor").id,
                        ],
                    )
                ],
            }
        )
        foreign = (
            self.env["community.meeting"]
            .with_user(other_editor)
            .with_company(company)
            .create(
                {
                    "name": "Foreign meeting",
                    "company_id": company.id,
                }
            )
        )
        plain = self.env["res.users"].create(
            {
                "name": "Plain proposer",
                "login": "plain-policy-proposer",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        for user, meeting, error in (
            (self.editor, foreign, AccessError),
            (plain, self._meeting(), UserError),
        ):
            with self.subTest(user=user.login), self.assertRaises(error), self.cr.savepoint():
                self.env["community.meeting.agenda.item"].with_user(user).create(
                    {
                        "meeting_id": meeting.id,
                        "name": "Forbidden agenda entry",
                    }
                )
