from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAgendaReordering(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Agenda reorder editor",
                "login": "agenda-reorder-editor-test",
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
        cls.reader = cls.env["res.users"].create(
            {
                "name": "Agenda reorder reader",
                "login": "agenda-reorder-reader-test",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def setUp(self):
        super().setUp()
        self.env.company.meeting_reorder_point_policy = "ongoing"
        self.editor_env = self.env(user=self.editor)

    def _meeting_with_points(self, names=("First", "Second", "Third")):
        meeting = self.editor_env["community.meeting"].create(
            {"name": "Agenda order", "start_datetime": "2026-11-02 10:00:00"}
        )
        items = self.editor_env["community.meeting.agenda.item"].create(
            [{"meeting_id": meeting.id, "name": name} for name in names]
        )
        return meeting, items

    def test_meeting_form_onchange_handles_virtual_agenda_items(self):
        meeting, _items = self._meeting_with_points()

        with Form(meeting) as form:
            form.start_datetime = "2026-11-02 11:00:00"

    def test_fixed_point_keeps_its_slot_and_is_not_movable(self):
        meeting, items = self._meeting_with_points()
        first, fixed, third = items
        fixed.reorderable = False

        self.assertFalse(fixed.can_move_up)
        self.assertFalse(fixed.can_move_down)
        self.assertFalse(first.can_move_down)
        self.assertFalse(third.can_move_up)

        meeting.action_reorder_agenda_items([third.id, fixed.id, first.id])
        self.assertEqual(meeting.agenda_item_ids.sorted("sequence").ids, [third.id, fixed.id, first.id])

        with self.assertRaises(ValidationError), self.cr.savepoint():
            meeting.action_reorder_agenda_items([fixed.id, third.id, first.id])

    def test_policy_stops_reordering_after_the_meeting_starts(self):
        meeting, items = self._meeting_with_points(("First", "Second"))
        self.env.company.meeting_reorder_point_policy = "draft"
        meeting.action_schedule()

        with self.assertRaises(UserError), self.cr.savepoint():
            meeting.action_reorder_agenda_items(list(reversed(items.ids)))

    def test_non_editor_cannot_reorder_through_rpc_or_sequence_write(self):
        meeting, items = self._meeting_with_points(("First", "Second"))
        reader_meeting = meeting.with_user(self.reader)
        reader_items = items.with_user(self.reader)

        with self.assertRaises(AccessError), self.cr.savepoint():
            reader_meeting.action_reorder_agenda_items(list(reversed(items.ids)))
        with self.assertRaises(AccessError), self.cr.savepoint():
            reader_items[0].write({"sequence": 40})
