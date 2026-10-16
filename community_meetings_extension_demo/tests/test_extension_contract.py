from odoo.tests.common import TransactionCase


class TestExtensionContract(TransactionCase):
    def test_kind_and_deterministic_snapshot_payload(self):
        meeting = self.env["community.meeting"].new({
            "name": "Synthetic extension",
            "meeting_kind": "demo",
            "demo_reference": "DEMO-1",
        })
        self.assertEqual(meeting.meeting_kind, "demo")
        extension = self.env["community.meeting.revision"]._get_snapshot_extensions(
            meeting, self.env.user, "2026-01-01 00:00:00",
        )
        self.assertEqual(extension["community_meetings_extension_demo"], {
            "reference": "DEMO-1", "kind": "demo",
        })

    def test_core_hooks_work_without_extension_data(self):
        partner = self.env["res.partner"].create({"name": "Manual invitee"})
        resolved = self.env["community.meeting"]._resolve_invitees([partner.id])
        self.assertEqual(resolved, partner)
