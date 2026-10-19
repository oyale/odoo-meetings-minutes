from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSeriesRecurringPoints(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Recurring Point Editor",
                "login": "recurring-point-editor-test",
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
            cls.env["community.meeting.series"].with_user(cls.editor).create({"name": "Recurring points series"})
        )
        cls.template = (
            cls.env["community.meeting.series.agenda.template"]
            .with_user(cls.editor)
            .create(
                {
                    "series_id": cls.series.id,
                    "name": "Review metrics",
                    "agenda_type_id": cls.env.ref("community_meetings.agenda_type_discussion").id,
                    "estimated_minutes": 15,
                }
            )
        )

    def _prepare_meeting(self, start_datetime, include_template=True):
        wizard = (
            self.env["community.meeting.create.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "series_id": self.series.id,
                    "name": "Recurring points meeting",
                    "start_datetime": start_datetime,
                    "duration_hours": 1.0,
                }
            )
        )
        for _ in range(4):
            wizard.action_next()
        line = wizard.recurring_line_ids.filtered(lambda row: row.template_id == self.template)
        self.assertEqual(len(line), 1)
        line.included = include_template
        wizard.action_next()
        wizard.action_finish()
        return wizard.created_meeting_id

    def test_creation_wizard_proposes_series_templates_by_default(self):
        wizard = (
            self.env["community.meeting.create.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "series_id": self.series.id,
                    "name": "Proposed recurring points",
                    "start_datetime": "2026-11-02 10:00:00",
                    "duration_hours": 1.0,
                }
            )
        )
        for _ in range(4):
            wizard.action_next()
        line = wizard.recurring_line_ids.filtered(lambda row: row.template_id == self.template)
        self.assertEqual(len(line), 1)
        self.assertTrue(line.included)

    def test_deselecting_a_template_only_skips_this_meeting(self):
        meeting = self._prepare_meeting("2026-11-02 10:00:00", include_template=False)

        self.assertFalse(meeting.agenda_item_ids.topic_id.filtered("recurring_template_id"))
        self.assertTrue(self.template.exists())
        next_meeting = self._prepare_meeting("2026-11-09 10:00:00")
        self.assertEqual(next_meeting.agenda_item_ids.topic_id.recurring_template_id, self.template)

    def test_occurrences_are_independent_and_link_to_previous_occurrence(self):
        first_meeting = self._prepare_meeting("2026-11-02 10:00:00")
        first_topic = first_meeting.agenda_item_ids.topic_id.filtered("recurring_template_id")
        second_meeting = self._prepare_meeting("2026-11-09 10:00:00")
        second_topic = second_meeting.agenda_item_ids.topic_id.filtered("recurring_template_id")
        self._prepare_meeting("2026-11-16 10:00:00", include_template=False)
        fourth_meeting = self._prepare_meeting("2026-11-23 10:00:00")
        fourth_topic = fourth_meeting.agenda_item_ids.topic_id.filtered("recurring_template_id")

        self.assertNotEqual(first_topic, second_topic)
        self.assertFalse(first_topic.previous_occurrence_id)
        self.assertEqual(second_topic.previous_occurrence_id, first_topic)
        self.assertEqual(fourth_topic.previous_occurrence_id, second_topic)

        self.template.name = "Updated future title"
        self.assertEqual(first_topic.name, "Review metrics")
        self.assertEqual(second_topic.name, "Review metrics")

    def test_occurrence_copies_history_preference_at_creation(self):
        self.template.show_previous_discussion = False
        first = self._prepare_meeting("2026-11-02 10:00:00")
        first_item = first.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        self.assertTrue(first_item.discard_previous_discussion)

        self.template.show_previous_discussion = True
        second = self._prepare_meeting("2026-11-09 10:00:00")
        second_item = second.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        self.assertFalse(second_item.discard_previous_discussion)

    def test_previous_discussion_is_read_only_context_and_cutoff_stops_chain(self):
        first = self._prepare_meeting("2026-11-02 10:00:00")
        first_item = first.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        first_item.discussion_notes = "<p>Earlier discussion</p>"

        second = self._prepare_meeting("2026-11-09 10:00:00")
        second_item = second.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        self.assertIn("Earlier discussion", second_item.previous_discussion_html)
        self.assertFalse(second_item.discussion_notes)
        second_item.discussion_notes = "<p>Current discussion</p>"
        second_item.discard_previous_discussion = True
        self.assertFalse(second_item.previous_discussion_html)

        third = self._prepare_meeting("2026-11-16 10:00:00")
        third_item = third.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        self.assertIn("Current discussion", third_item.previous_discussion_html)
        self.assertNotIn("Earlier discussion", third_item.previous_discussion_html)

    def test_automatic_recurring_points_never_show_previous_discussion(self):
        self.template.agenda_type_id = self.env.ref("community_meetings.agenda_type_next_meeting")
        first = self._prepare_meeting("2026-11-02 10:00:00")
        first_item = first.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        first_item.discussion_notes = "<p>Automatic point note</p>"
        second = self._prepare_meeting("2026-11-09 10:00:00")
        second_item = second.agenda_item_ids.filtered(lambda row: row.topic_id.recurring_template_id)
        self.assertFalse(second_item.previous_discussion_html)
