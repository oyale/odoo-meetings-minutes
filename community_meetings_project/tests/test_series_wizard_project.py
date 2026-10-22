from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSeriesWizardProject(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Series Wizard Project Editor",
                "login": "series-wizard-project-editor-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                            cls.env.ref("project.group_project_manager").id,
                        ],
                    )
                ],
            }
        )

    def _wizard(self, **values):
        return self.env["community.meeting.series.wizard"].with_user(self.editor).create(values)

    def test_select_an_existing_project(self):
        project = self.env["project.project"].create({"name": "Existing series project"})
        wizard = self._wizard(name="Select project series", link_project=True, project_id=project.id)
        wizard.action_finish()
        series = wizard.created_series_id
        self.assertEqual(series.meeting_project_id, project)
        self.assertEqual(series.meeting_project_mode, "series")

    def test_create_a_new_project(self):
        wizard = self._wizard(
            name="New project series",
            link_project=True,
            new_project=True,
            new_project_name="Fresh project",
        )
        wizard.action_finish()
        series = wizard.created_series_id
        self.assertEqual(series.meeting_project_id.name, "Fresh project")
        self.assertEqual(series.meeting_project_id.company_id, series.company_id)
        created_project = series.meeting_project_id
        project_count = self.env["project.project"].search_count([("name", "=", "Fresh project")])
        wizard.action_finish()
        self.assertEqual(wizard.created_series_id, series)
        self.assertEqual(series.meeting_project_id, created_project)
        self.assertEqual(self.env["project.project"].search_count([("name", "=", "Fresh project")]), project_count)

    def test_no_project_is_allowed(self):
        wizard = self._wizard(name="No project series")
        wizard.action_finish()
        self.assertFalse(wizard.created_series_id.meeting_project_id)
        self.assertEqual(wizard.created_series_id.meeting_project_mode, "inherit")

    def test_project_creation_failure_rolls_back_the_series(self):
        wizard = self._wizard(
            name="Atomic project series",
            link_project=True,
            new_project=True,
            new_project_name="   ",
        )
        series_count = self.env["community.meeting.series"].search_count([("name", "=", "Atomic project series")])
        project_count = self.env["project.project"].search_count([("name", "=", "Atomic project series")])

        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_finish()

        wizard.invalidate_recordset(["created_series_id", "created_project_id"])
        self.assertFalse(wizard.created_series_id)
        self.assertFalse(wizard.created_project_id)
        self.assertEqual(
            self.env["community.meeting.series"].search_count([("name", "=", "Atomic project series")]),
            series_count,
        )
        self.assertEqual(
            self.env["project.project"].search_count([("name", "=", "Atomic project series")]),
            project_count,
        )

    def test_link_requires_a_project_or_creation(self):
        wizard = self._wizard(name="Missing project series", link_project=True)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_finish()
