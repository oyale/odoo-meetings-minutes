from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAgendaProposals(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Series Coordinator",
            "login": "proposal-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.proposer = cls.env["res.users"].create({
            "name": "Internal Proposer",
            "login": "agenda-proposer-test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create({
            "name": "Operations Team",
        })
        cls.meeting = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Next Operations Meeting",
            "series_id": cls.series.id,
        })

    def test_proposer_can_submit_without_reading_the_meeting(self):
        proposal = self.env["community.meeting.agenda.proposal"].with_user(self.proposer).create({
            "name": "Review support coverage",
            "series_id": self.series.id,
        })
        self.assertEqual(proposal.submitted_by_user_id, self.proposer)
        self.assertEqual(proposal.proposer_partner_id, self.proposer.partner_id)
        self.assertTrue(proposal.with_user(self.proposer).exists())
        with self.assertRaises(AccessError):
            self.env["community.meeting"].with_user(self.proposer).browse(self.meeting.id).read(["name"])

    def test_proposer_identity_cannot_be_forged(self):
        other_partner = self.env["res.partner"].create({"name": "Different Contact"})
        with self.assertRaises(AccessError):
            self.env["community.meeting.agenda.proposal"].with_user(self.proposer).create({
                "name": "Forged identity",
                "series_id": self.series.id,
                "proposer_partner_id": other_partner.id,
            })

    def test_coordinator_acceptance_is_idempotent(self):
        proposal = self.env["community.meeting.agenda.proposal"].with_user(self.proposer).create({
            "name": "Review support coverage",
            "series_id": self.series.id,
        })
        proposal = proposal.with_user(self.editor)
        proposal.action_accept(self.meeting.id)
        item_id = proposal.destination_item_id.id
        proposal.action_accept(self.meeting.id)
        self.assertEqual(proposal.status, "accepted")
        self.assertEqual(proposal.destination_item_id.id, item_id)
        self.assertEqual(len(self.meeting.agenda_item_ids.filtered(lambda item: item.name == proposal.name)), 1)

    def test_contact_grant_records_mediator_and_proposer(self):
        contact = self.env["res.partner"].create({"name": "External Cooperative Member"})
        self.env["community.meeting.proposal.grant"].with_user(self.editor).create({
            "partner_id": contact.id,
            "company_id": self.series.company_id.id,
            "series_id": self.series.id,
        })
        proposal = self.env["community.meeting.agenda.proposal"].with_user(self.editor).submit_on_behalf(
            contact.id, "Review cooperative workspace", series_id=self.series.id,
        )
        self.assertEqual(proposal.proposer_partner_id, contact)
        self.assertEqual(proposal.submitted_by_user_id, self.editor)
