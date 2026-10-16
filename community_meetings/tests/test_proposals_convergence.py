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
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("community_meetings.group_meeting_editor").id,
            ])],
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
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["community.meeting.topic"].with_user(outsider).propose({
                "name": "Nope", "series_id": self.series.id,
                "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            })

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

    def test_pending_proposals_are_listed_on_the_series(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "On the series", "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        self.assertIn(topic, self.series.pending_proposal_ids)
        topic.action_reject_proposal()
        self.assertNotIn(topic, self.series.pending_proposal_ids)

    def test_a_non_editor_proposer_can_propose_and_withdraw(self):
        proposer = self.env["res.users"].create({
            "name": "Plain proposer", "login": "proposal-plain-conv-test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        wizard = self.env["community.meeting.point.wizard"].with_user(proposer).create({
            "propose": True, "proposal_series_id": self.series.id,
            "name": "From a plain proposer",
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        wizard.action_save()
        topic = self.env["community.meeting.topic"].search([
            ("name", "=", "From a plain proposer"),
            ("submitted_by_user_id", "=", proposer.id),
        ])
        self.assertEqual(topic.proposal_status, "submitted")
        topic.with_user(proposer).action_withdraw_proposal()
        self.assertEqual(topic.proposal_status, "withdrawn")

    def test_a_coordinator_sees_another_users_proposal(self):
        coordinator = self.env["res.users"].create({
            "name": "Coordinator", "login": "proposal-coordinator-conv-test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        series = self.env["community.meeting.series"].with_user(coordinator).create({
            "name": "Coordinated series",
            "coordinator_user_ids": [(6, 0, [coordinator.id])],
        })
        topic = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Someone else's idea", "series_id": series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        self.assertIn(topic, series.with_user(coordinator).pending_proposal_ids)
        topic.with_user(coordinator).action_reject_proposal("no")
        self.assertEqual(topic.proposal_status, "rejected")
