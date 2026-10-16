from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSeriesWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Series Wizard Editor",
            "login": "series-wizard-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })

    def _wizard(self, **values):
        return self.env["community.meeting.series.wizard"].with_user(self.editor).create(values)

    def test_wizard_creates_a_series_with_its_values(self):
        wizard = self._wizard(
            name="Board", duration_hours=1.5, carryover_policy="automatic",
            has_next_meeting_point=True, next_meeting_rule="interval_days",
            next_meeting_interval_days=7,
        )
        self.assertEqual(wizard.step, "basics")
        wizard.action_next()
        self.assertEqual(wizard.step, "schedule")
        wizard.action_next()
        self.assertEqual(wizard.step, "structure")
        wizard.action_next()
        self.assertEqual(wizard.step, "review")
        wizard.action_finish()
        series = wizard.created_series_id
        self.assertTrue(series)
        self.assertEqual(series.duration_hours, 1.5)
        self.assertEqual(series.carryover_policy, "automatic")
        self.assertTrue(series.has_next_meeting_point)
        self.assertEqual(series.next_meeting_interval_days, 7)

    def test_finish_is_idempotent(self):
        wizard = self._wizard(name="Repeat", duration_hours=1.0)
        wizard.action_finish()
        series = wizard.created_series_id
        wizard.action_finish()
        self.assertEqual(wizard.created_series_id, series)
        self.assertEqual(
            self.env["community.meeting.series"].search_count([("name", "=", "Repeat")]), 1
        )

    def test_name_is_required_before_advancing(self):
        wizard = self._wizard(name="   ")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_next()
        self.assertEqual(wizard.step, "basics")
