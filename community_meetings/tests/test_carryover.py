from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAgendaCarryover(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Carryover Coordinator",
            "login": "carryover-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create({
            "name": "Carryover Series",
        })
        cls.source = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Source Meeting", "series_id": cls.series.id,
            "start_datetime": "2026-11-01 10:00:00",
        })
        cls.destination = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Destination Meeting", "series_id": cls.series.id,
            "start_datetime": "2026-11-08 10:00:00",
        })

    def _request(self, item, reason="Continue next time"):
        wizard = self.env["community.meeting.carryover.wizard"].with_user(self.editor).create({
            "origin_model": "agenda_item",
            "origin_record_id": item.id,
            "origin_meeting_id": self.source.id,
            "destination_meeting_id": self.destination.id,
            "reason": reason,
        })
        wizard.action_request()
        return self.env["community.meeting.carryover"].with_user(self.editor).search([
            ("origin_agenda_item_id", "=", item.id),
        ], limit=1)

    def test_review_accept_creates_a_linked_copy_once(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id, "name": "Review the budget", "description": "Public agenda summary",
        })
        transfer = self._request(item)
        self.assertEqual(transfer.status, "proposed")
        self.assertEqual(item.disposition, "deferred")
        self.assertFalse(transfer.destination_item_id)
        transfer.action_accept()
        created_item = transfer.destination_item_id
        self.assertTrue(created_item)
        self.assertEqual(created_item.carryover_id, transfer)
        self.assertNotEqual(created_item, item)
        self.assertEqual(item.meeting_id, self.source)
        self.assertEqual(len(self.destination.agenda_item_ids.filtered(lambda row: row.carryover_id == transfer)), 1)
        transfer.action_accept()
        self.assertEqual(len(self.destination.agenda_item_ids.filtered(lambda row: row.carryover_id == transfer)), 1)

    def test_creation_wizard_does_not_offer_an_already_carried_point_again(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id,
            "name": "Continue the roadmap",
            "review_next_meeting": True,
        })
        self.env["community.meeting.action"].with_user(self.editor).create({
            "meeting_id": self.source.id,
            "agenda_item_id": item.id,
            "name": "Continue the active work",
        })
        # Simulate the series automation having already accepted and placed the
        # source in an earlier future meeting. Its active follow-up would
        # otherwise make the old participation look eligible again.
        transfer = self.env["community.meeting.carryover"].with_user(self.editor).create({
            "origin_model": "agenda_item",
            "origin_record_id": item.id,
            "destination_meeting_id": self.destination.id,
        })
        transfer.action_accept()
        self.assertEqual(transfer.status, "accepted")
        wizard = self.env["community.meeting.create.wizard"].with_user(self.editor).create({
            "step": "people",
            "series_id": self.series.id,
            "name": "Later destination",
            "start_datetime": "2026-11-15 10:00:00",
            "duration_hours": 1,
        })

        wizard.action_next()

        self.assertFalse(wizard.carry_line_ids.filtered(lambda line: line.source_id == item))

    def test_dismissed_source_cannot_be_queued_again(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id, "name": "Do not carry forward",
        })
        transfer = self._request(item)
        transfer.action_dismiss("Not needed")
        duplicate = self._request(item)
        self.assertEqual(duplicate, transfer)
        self.assertEqual(duplicate.status, "dismissed")
        self.assertFalse(duplicate.destination_item_id)

    def test_completed_action_can_be_selected_explicitly(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id, "name": "Completed work",
        })
        action = self.env["community.meeting.action"].with_user(self.editor).create({
            "meeting_id": self.source.id, "agenda_item_id": item.id,
            "name": "Previously completed action", "state": "done",
        })
        wizard = self.env["community.meeting.carryover.wizard"].with_user(self.editor).create({
            "origin_model": "action", "origin_record_id": action.id,
            "origin_meeting_id": self.source.id, "destination_meeting_id": self.destination.id,
        })
        wizard.action_request()
        transfer = self.env["community.meeting.carryover"].with_user(self.editor).search([
            ("origin_action_id", "=", action.id),
        ], limit=1)
        transfer.action_accept()
        self.assertEqual(transfer.destination_item_id.meeting_id, self.destination)
        self.assertEqual(action.state, "done")

    def test_resolution_can_be_requested_as_followup(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id, "name": "Decision point", "kind": "decision",
        })
        resolution = self.env["community.meeting.resolution"].with_user(self.editor).create({
            "meeting_id": self.source.id, "agenda_item_id": item.id,
            "title": "Agreement title", "body": "Agreement body",
        })
        wizard = self.env["community.meeting.carryover.wizard"].with_user(self.editor).create({
            "origin_model": "resolution", "origin_record_id": resolution.id,
            "origin_meeting_id": self.source.id, "destination_meeting_id": self.destination.id,
        })
        wizard.action_request()
        transfer = self.env["community.meeting.carryover"].with_user(self.editor).search([
            ("origin_resolution_id", "=", resolution.id),
        ], limit=1)
        self.assertEqual(transfer.origin_name, "Agreement title")

    def test_direct_status_write_is_rejected(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id, "name": "Workflow guard",
        })
        transfer = self._request(item)
        with self.assertRaises(UserError):
            transfer.write({"status": "accepted"})

    def test_resolution_followup_waits_for_destination_series_meeting(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.source.id, "name": "Agreement source",
        })
        resolution = self.env["community.meeting.resolution"].with_user(self.editor).create({
            "meeting_id": self.source.id, "agenda_item_id": item.id, "title": "Review delivery",
        })
        series = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Destination assembly", "carryover_policy": "review",
        })
        action = resolution.action_request_followup()
        self.assertEqual(action["context"]["default_destination_series_id"], self.series.id)
        wizard = self.env["community.meeting.carryover.wizard"].with_user(self.editor).create({
            "origin_model": "resolution", "origin_record_id": resolution.id,
            "origin_meeting_id": self.source.id, "destination_series_id": series.id,
        })
        wizard.action_request()
        transfer = self.env["community.meeting.carryover"].search([("origin_resolution_id", "=", resolution.id)])
        self.assertEqual(transfer.destination_series_id, series)
        self.assertFalse(transfer.destination_meeting_id)
        destination = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Destination assembly meeting", "series_id": series.id,
            "start_datetime": "2026-11-10 10:00:00",
        })
        self.assertEqual(transfer.destination_meeting_id, destination)
        self.assertEqual(transfer.status, "proposed")
        transfer.with_user(self.editor).action_accept()
        self.assertEqual(transfer.destination_item_id.meeting_id, destination)
        self.assertEqual(transfer.destination_item_id.carryover_id.origin_resolution_id, resolution)
        self.assertEqual(transfer.destination_item_id.topic_id.series_id, series)

    def test_spanish_carryover_errors_are_translated(self):
        spanish = self.env["res.lang"].search(
            [("code", "=", "es_ES"), ("active", "=", True)], limit=1
        )
        if not spanish:
            self.skipTest("Spanish translations are not installed in this database.")

        spanish_items = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .with_context(lang="es_ES")
        )
        source_item = spanish_items.create(
            {"meeting_id": self.source.id, "name": "Accepted source"}
        )
        cancelled_source_item = spanish_items.create(
            {"meeting_id": self.source.id, "name": "Cancelled source"}
        )
        transfer = self._request(source_item)
        transfer.action_accept()

        with self.assertRaises(UserError) as deletion_error:
            transfer.destination_item_id.with_context(lang="es_ES").unlink()
        self.assertEqual(
            str(deletion_error.exception),
            "No se puede eliminar un punto del orden del día procedente de un traspaso aceptado.",
        )

        with self.assertRaises(UserError) as link_error:
            transfer.destination_item_id.with_context(lang="es_ES").write(
                {"carryover_id": False}
            )
        self.assertEqual(
            str(link_error.exception),
            "El vínculo de traspaso de un punto del orden del día no se puede cambiar.",
        )

        self.source.action_cancel()
        with self.assertRaises(UserError) as cancelled_error:
            self.env["community.meeting.carryover"].with_user(self.editor).with_context(
                lang="es_ES"
            ).create(
                {
                    "origin_model": "agenda_item",
                    "origin_record_id": cancelled_source_item.id,
                    "destination_meeting_id": self.destination.id,
                }
            )
        self.assertEqual(
            str(cancelled_error.exception),
            "Las reuniones canceladas no pueden iniciar traspasos del orden del día.",
        )
