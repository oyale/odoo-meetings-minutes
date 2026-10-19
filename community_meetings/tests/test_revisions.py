import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingRevisions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Minutes Editor",
                "login": "minutes-editor-revision-test",
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
        cls.approver = cls.env["res.users"].create(
            {
                "name": "Minutes Approver",
                "login": "minutes-approver-revision-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_approver").id,
                        ],
                    )
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Minutes Manager",
                "login": "minutes-manager-revision-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_manager").id,
                        ],
                    )
                ],
            }
        )

    def _approved_meeting(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Revision stability test",
                    "start_datetime": "2026-11-01 10:00:00",
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        review = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Review open actions",
                    "discussion_notes": "<p>Initial discussion</p>",
                }
            )
        )
        decision = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Approve the budget",
                    "kind": "decision",
                    "sequence": 20,
                }
            )
        )
        self.env["community.meeting.resolution"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": decision.id,
                "title": "Budget approved",
                "decision_outcome": "approved",
            }
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": review.id,
                    "name": "Prepare follow-up",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        approved = meeting.with_user(self.approver)
        revision = self._approve_without_rendering_pdf(approved)
        return meeting, action, revision

    def _drafted_meeting(self, name):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": name,
                    "start_datetime": "2026-11-01 10:00:00",
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "name": "Review open actions",
                "discussion_notes": "<p>Initial discussion</p>",
            }
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        return meeting

    def _approve_without_rendering_pdf(self, meeting):
        report_model = self.env["ir.actions.report"]
        pdf_fixture = b"%PDF-1.4\n% wkhtmltopdf is smoke-tested separately in CI.\n"
        with patch.object(type(report_model), "_render_qweb_pdf", return_value=(pdf_fixture, "pdf")):
            return meeting.action_approve_minutes()

    def test_approve_minutes_recordset_approves_all(self):
        first = self._drafted_meeting("First recordset approval")
        second = self._drafted_meeting("Second recordset approval")
        revisions = self._approve_without_rendering_pdf((first | second).with_user(self.approver))
        # F1: the loop must not return early; both meetings get approved.
        self.assertEqual(len(revisions), 2)
        self.assertEqual(first.state, "approved")
        self.assertEqual(second.state, "approved")

    def test_snapshot_records_pending_destination_series(self):
        meeting = self._drafted_meeting("Pending follow-up destination")
        destination = self.env["community.meeting.series"].with_user(self.editor).create({"name": "Future assembly"})
        resolution = (
            self.env["community.meeting.resolution"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": meeting.agenda_item_ids[0].id,
                    "title": "Review later",
                }
            )
        )
        self.env["community.meeting.carryover"].with_user(self.editor).create(
            {
                "origin_model": "resolution",
                "origin_record_id": resolution.id,
                "destination_series_id": destination.id,
            }
        )
        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(
            snapshot["carryovers"][0]["destination_series"],
            {"id": destination.id, "name": destination.name},
        )

    def test_report_html_and_snapshot_are_stable_after_action_changes(self):
        _, action, revision = self._approved_meeting()
        before_json = revision.snapshot_json
        before_pdf = revision.pdf_attachment_id.raw
        rendered_html, report_type = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        snapshot = json.loads(before_json)
        self.assertEqual(report_type, "html")
        self.assertIn(b"Review open actions", rendered_html)
        self.assertEqual(snapshot["agenda"][0]["discussion"], "<p>Initial discussion</p>")
        self.assertEqual(snapshot["agenda"][1]["decision_result"], "approved")
        self.assertEqual(snapshot["agenda"][1]["resolutions"][0]["decision_outcome"], "approved")
        self.assertEqual(snapshot["agenda"][1]["decision_result_label"], "Approved")
        self.assertTrue(before_pdf.startswith(b"%PDF"))
        self.assertEqual(len(revision.snapshot_sha256), 64)
        self.assertEqual(len(revision.pdf_sha256), 64)

        action.with_user(self.editor).write({"state": "done"})
        self.assertEqual(revision.snapshot_json, before_json)
        self.assertEqual(revision.pdf_attachment_id.raw, before_pdf)

    def test_amendment_creates_a_new_revision_and_keeps_the_old_pdf(self):
        meeting, _action, first = self._approved_meeting()
        first_pdf = first.pdf_attachment_id.raw
        manager_meeting = meeting.with_user(self.manager)
        manager_meeting.action_start_amendment()
        manager_meeting.write({"minutes_notes": "Corrected wording"})
        second = self._approve_without_rendering_pdf(manager_meeting)

        self.assertEqual(second.revision_number, 2)
        self.assertEqual(second.previous_revision_id, first)
        self.assertEqual(first.status, "superseded")
        self.assertEqual(first.pdf_attachment_id.raw, first_pdf)
        self.assertEqual(meeting.approved_revision_id, second)

    def test_agenda_type_can_be_changed_only_through_an_immutable_revision_amendment(
        self,
    ):
        meeting, _action, first = self._approved_meeting()
        decision = meeting.agenda_item_ids.filtered(lambda item: item.kind == "decision")
        with self.assertRaises(UserError):
            decision.with_user(self.manager).write({"kind": "information"})

        manager_meeting = meeting.with_user(self.manager)
        manager_meeting.action_start_amendment()
        meeting.resolution_ids.with_user(self.manager).write({"status": "withdrawn"})
        decision.with_user(self.manager).write({"kind": "information"})
        second = self._approve_without_rendering_pdf(manager_meeting)

        self.assertEqual(first.status, "superseded")
        self.assertEqual(second.revision_number, 2)
        self.assertEqual(json.loads(first.snapshot_json)["agenda"][1]["decision_result"], "approved")
        self.assertEqual(json.loads(second.snapshot_json)["agenda"][1]["kind"], "information")
