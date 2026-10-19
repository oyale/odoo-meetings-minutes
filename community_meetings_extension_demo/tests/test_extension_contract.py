import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestExtensionContract(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Extension Demo Editor",
                "login": "extension-demo-editor-test",
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
                "name": "Extension Demo Approver",
                "login": "extension-demo-approver-test",
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

    def test_kind_and_deterministic_snapshot_payload(self):
        demo_kind = self.env.ref("community_meetings_extension_demo.kind_demonstration")
        meeting = self.env["community.meeting"].new(
            {
                "name": "Synthetic extension",
                "meeting_kind_id": demo_kind.id,
                "demo_reference": "DEMO-1",
            }
        )
        self.assertEqual(meeting.meeting_kind_id, demo_kind)
        extension = self.env["community.meeting.revision"]._get_snapshot_extensions(
            meeting,
            self.env.user,
            "2026-01-01 00:00:00",
        )
        self.assertEqual(
            extension["community_meetings_extension_demo"],
            {
                "reference": "DEMO-1",
                "kind": "demo",
            },
        )

    def test_extension_payload_is_persisted_in_approved_revision(self):
        demo_kind = self.env.ref("community_meetings_extension_demo.kind_demonstration")
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Approved extension example",
                    "start_datetime": "2026-11-02 10:00:00",
                    "meeting_kind_id": demo_kind.id,
                    "demo_reference": "DEMO-APPROVED-1",
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {"meeting_id": meeting.id, "name": "Review extension data"}
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()

        report_model = self.env["ir.actions.report"]
        pdf_fixture = b"%PDF-1.4\n% Extension snapshot contract test.\n"
        with patch.object(type(report_model), "_render_qweb_pdf", return_value=(pdf_fixture, "pdf")):
            revision = meeting.with_user(self.approver).action_approve_minutes()

        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(
            snapshot["extensions"]["community_meetings_extension_demo"],
            {"reference": "DEMO-APPROVED-1", "kind": "demo"},
        )

    def test_core_hooks_work_without_extension_data(self):
        partner = self.env["res.partner"].create({"name": "Manual invitee"})
        resolved = self.env["community.meeting"]._resolve_invitees([partner.id])
        self.assertEqual(resolved, partner)
