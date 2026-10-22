import importlib.util
from pathlib import Path

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProposalAdmission(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Proposal Editor",
                "login": "proposal-editor-conv-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                            cls.env.ref("community_meetings.group_agenda_proposer").id,
                        ],
                    )
                ],
            }
        )
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create({"name": "Proposal series"})

    def test_legacy_admission_requires_review_capability(self):
        proposer = self.env["res.users"].create(
            {
                "name": "Legacy admission proposer",
                "login": "legacy-admission-proposer",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        topic = (
            self.env["community.meeting.topic"]
            .with_user(proposer)
            .propose(
                {
                    "name": "Unreviewed idea",
                    "series_id": self.series.id,
                    "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
                }
            )
        )
        with self.assertRaises(AccessError), self.cr.savepoint():
            topic.action_admit()
        self.assertEqual(topic.state, "proposed")
        self.assertEqual(topic.proposal_status, "submitted")
        self.assertFalse(topic.responded_by_id)
        self.assertFalse(topic.responded_at)

    def test_legacy_admission_records_the_same_review_as_acceptance(self):
        topic = (
            self.env["community.meeting.topic"]
            .with_user(self.editor)
            .propose(
                {
                    "name": "Reviewed legacy entry",
                    "series_id": self.series.id,
                    "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
                }
            )
        )
        topic.action_admit()
        self.assertEqual(topic.state, "open")
        self.assertEqual(topic.proposal_status, "accepted")
        self.assertEqual(topic.responded_by_id, self.editor)
        self.assertTrue(topic.responded_at)

    def test_admission_rejects_unsubmitted_points_without_partial_review(self):
        values = {
            "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        }
        topics = self.env["community.meeting.topic"].with_user(self.editor)
        submitted = topics.propose(dict(values, name="Still submitted"))
        unsubmitted = topics.create(dict(values, name="Not a submitted proposal", state="proposed"))
        for method in ("action_admit", "action_accept_proposal"):
            with self.subTest(method=method), self.assertRaises(UserError), self.cr.savepoint():
                getattr(submitted | unsubmitted, method)()
            self.assertEqual(submitted.state, "proposed")
            self.assertEqual(submitted.proposal_status, "submitted")
            self.assertFalse(submitted.responded_at)

    def test_upgrade_marks_legacy_admission_without_inventing_a_review(self):
        topics = self.env["community.meeting.topic"].with_user(self.editor)
        values = {
            "series_id": self.series.id,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        }
        legacy_open = topics.propose(dict(values, name="Legacy open"))
        legacy_closed = topics.propose(dict(values, name="Legacy closed"))
        current = topics.propose(dict(values, name="Waiting for real review"))
        reviewed = topics.propose(dict(values, name="Recorded review"))
        reviewed.action_accept_proposal()
        known_review = (reviewed.responded_by_id.id, reviewed.responded_at)
        self.env.flush_all()
        self.cr.execute("UPDATE community_meeting_topic SET state='open' WHERE id=%s", [legacy_open.id])
        self.cr.execute("UPDATE community_meeting_topic SET state='closed' WHERE id=%s", [legacy_closed.id])
        records = legacy_open | legacy_closed | current | reviewed
        records.invalidate_recordset()
        script = Path(__file__).resolve().parents[1] / "migrations/18.0.6.2.8/post-migrate.py"
        spec = importlib.util.spec_from_file_location("proposal_review_migration", script)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        for _iteration in range(2):
            migration.migrate(self.cr, "18.0.6.2.7")
            records.invalidate_recordset()
            self.assertEqual(legacy_open.state, "open")
            self.assertEqual(legacy_closed.state, "closed")
            for legacy in legacy_open | legacy_closed:
                self.assertEqual(legacy.proposal_status, "legacy_admitted")
                self.assertFalse(legacy.responded_by_id)
                self.assertFalse(legacy.responded_at)
            self.assertEqual((current.state, current.proposal_status), ("proposed", "submitted"))
            self.assertEqual(reviewed.proposal_status, "accepted")
            self.assertEqual((reviewed.responded_by_id.id, reviewed.responded_at), known_review)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            topics.create(dict(values, name="Forged legacy review", proposal_status="legacy_admitted"))

    def test_both_admission_entries_preserve_scope_and_review_other_proposers(self):
        proposer = self.env["res.users"].create(
            {
                "name": "Independent proposer",
                "login": "independent-admission-proposer",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        company = self.env["res.company"].create({"name": "Foreign proposal company"})
        foreign_editor = self.env["res.users"].create(
            {
                "name": "Foreign reviewer",
                "login": "foreign-admission-reviewer",
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
        foreign_topics = self.env["community.meeting.topic"].with_user(foreign_editor).with_company(company)
        foreign_series = (
            self.env["community.meeting.series"]
            .with_user(foreign_editor)
            .with_company(company)
            .create(
                {
                    "name": "Foreign proposal series",
                    "company_id": company.id,
                }
            )
        )
        foreign = foreign_topics.propose(
            {
                "name": "Foreign proposal",
                "series_id": foreign_series.id,
                "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            }
        )
        manager = self.env["res.users"].create(
            {
                "name": "Destination manager",
                "login": "admission-destination-manager",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_manager").id,
                        ],
                    )
                ],
            }
        )
        for method in ("action_admit", "action_accept_proposal"):
            topic = (
                self.env["community.meeting.topic"]
                .with_user(proposer)
                .propose(
                    {
                        "name": "Another person's proposal",
                        "series_id": self.series.id,
                        "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
                    }
                )
            )
            with self.subTest(method=method), self.assertRaises(AccessError), self.cr.savepoint():
                getattr(topic, method)()
            with self.assertRaises(AccessError), self.cr.savepoint():
                getattr(foreign.with_user(self.editor), method)()
            self.assertEqual(foreign.proposal_status, "submitted")
            getattr(topic.with_user(self.editor), method)()
            self.assertEqual(topic.proposal_status, "accepted")
            self.assertEqual(topic.responded_by_id, self.editor)
            meeting = (
                self.env["community.meeting"]
                .with_user(manager)
                .create(
                    {
                        "name": "Private destination",
                        "series_id": self.series.id,
                    }
                )
            )
            self.env["community.meeting.agenda.item"].with_user(manager).create(
                {
                    "meeting_id": meeting.id,
                    "topic_id": topic.id,
                }
            )
            with self.assertRaises(AccessError), self.cr.savepoint():
                meeting.with_user(proposer).read(["name"])
