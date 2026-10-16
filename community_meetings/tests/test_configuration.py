from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPointConfiguration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Config Editor", "login": "config-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create(
            {"name": "Config series"}
        )

    def _meeting(self, name="Config meeting"):
        return self.env["community.meeting"].with_user(self.editor).create({
            "name": name, "series_id": self.series.id,
            "start_datetime": "2026-11-01 10:00:00",
        })

    def _point_minutes(self, meeting):
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Estimated point",
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        wizard.action_save()
        return wizard.created_item_id.topic_id.estimated_minutes

    def test_point_estimate_uses_company_then_series_default(self):
        self.env.company.meeting_estimated_minutes = 25
        self.assertEqual(self._point_minutes(self._meeting("Company default")), 25)
        self.series.default_estimated_minutes = 40
        self.assertEqual(self._point_minutes(self._meeting("Series override")), 40)

    def test_role_names_resolve_company_then_series(self):
        self.env.company.meeting_coordinator_label = "Chair"
        self.assertEqual(self.series._coordinator_label(), "Chair")
        self.series.coordinator_label = "Board chair"
        self.assertEqual(self.series._coordinator_label(), "Board chair")
        meeting = self._meeting("Roles")
        self.assertEqual(meeting.coordinator_role_label, "Board chair")

    def test_copy_point_to_another_series(self):
        topic = self.env["community.meeting.topic"].with_user(self.editor).create({
            "name": "Original point", "description": "<p>Body</p>",
            "series_id": self.series.id, "priority": "2", "estimated_minutes": 15,
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
        })
        destination = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Destination series",
        })
        wizard = self.env["community.meeting.topic.copy.wizard"].with_user(self.editor).create({
            "topic_id": topic.id, "destination_series_id": destination.id,
        })
        res = wizard.action_copy()
        copy = self.env["community.meeting.topic"].browse(res["res_id"])
        self.assertEqual(copy.origin_topic_id, topic)
        self.assertEqual(copy.series_id, destination)
        self.assertEqual(copy.name, "Original point")
        self.assertEqual(copy.priority, "2")
        self.assertEqual(copy.estimated_minutes, 15)
        self.assertNotEqual(copy, topic)

    def test_series_changes_only_before_the_meeting_starts(self):
        other = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Other series",
        })
        meeting = self._meeting("Series change")
        meeting.with_user(self.editor).write({"series_id": other.id})
        self.assertEqual(meeting.series_id, other)
        meeting.with_user(self.editor).write({"series_id": False})
        self.assertFalse(meeting.series_id)

        unassigned = self._meeting("Unassigned series")
        unassigned.write({"series_id": False})
        unassigned.action_schedule()
        unassigned.action_start_meeting()
        with self.assertRaises(UserError), self.cr.savepoint():
            unassigned.write({"series_id": other.id})

        started = self._meeting("Locked series")
        started.with_user(self.editor).action_schedule()
        started.with_user(self.editor).action_start_meeting()
        with self.assertRaises(UserError), self.cr.savepoint():
            started.with_user(self.editor).write({"series_id": other.id})

    def test_series_assignment_is_locked_after_meeting_completion(self):
        for state in ("held", "minutes_draft", "approved", "cancelled"):
            meeting = self._meeting(f"Locked {state}")
            meeting._transition(("draft",), state)
            with self.assertRaises(UserError), self.cr.savepoint():
                meeting.write({"series_id": False})

    def test_series_changes_update_private_points_but_refuse_shared_points(self):
        other = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "New series",
        })
        meeting = self._meeting()
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Private point", "kind": "discussion",
        })
        meeting.action_schedule()
        meeting.write({"series_id": other.id})
        self.assertEqual(item.topic_id.series_id, other)
        meeting.write({"series_id": False})
        self.assertFalse(item.topic_id.series_id)
        meeting.write({"series_id": self.series.id})
        sibling = self._meeting("Shared point meeting")
        self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": sibling.id, "topic_id": item.topic_id.id,
        })
        with self.assertRaises(UserError), self.cr.savepoint():
            meeting.write({"series_id": other.id})
        self.assertEqual(meeting.series_id, self.series)
        self.assertEqual(item.topic_id.series_id, self.series)

    def test_series_must_be_active_and_match_meeting_company(self):
        meeting = self._meeting()
        inactive = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Archived series", "active": False,
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            meeting.write({"series_id": inactive.id})
        company = self.env["res.company"].create({"name": "Other company"})
        foreign = self.env["community.meeting.series"].with_user(self.editor).sudo().create({
            "name": "Foreign series", "company_id": company.id,
            "coordinator_user_ids": [(5, 0, 0)],
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            meeting.sudo().write({"series_id": foreign.id})

    def test_dissent_reasons_are_configurable(self):
        reason = self.env["community.meeting.dissent.reason"].create({"name": "Budget objection"})
        meeting = self._meeting("Dissent reasons")
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "A point", "kind": "discussion",
        })
        dissent = self.env["community.meeting.dissent"].with_user(self.editor).create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "body": "<p>Not convinced</p>", "reason_id": reason.id,
        })
        self.assertEqual(dissent.reason_id, reason)
        reason.active = False
        self.assertEqual(dissent.reason_id, reason)
