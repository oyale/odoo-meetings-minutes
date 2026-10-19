from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCarryoverDiscovery(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Bug Carryover Editor",
                "login": "bug-carryover-editor-test",
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
            cls.env["community.meeting.series"]
            .with_user(cls.editor)
            .create(
                {
                    "name": "Bug Series",
                    "carryover_policy": "review",
                }
            )
        )
        cls.source = (
            cls.env["community.meeting"]
            .with_user(cls.editor)
            .create(
                {
                    "name": "Bug Source",
                    "series_id": cls.series.id,
                    "start_datetime": "2026-11-01 10:00:00",
                }
            )
        )
        cls.between = (
            cls.env["community.meeting"]
            .with_user(cls.editor)
            .create(
                {
                    "name": "Bug Between",
                    "series_id": cls.series.id,
                    "start_datetime": "2026-11-08 10:00:00",
                }
            )
        )

    def test_new_meeting_review_projects_carryover_and_escapes_names(self):
        source = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.source.id,
                    "name": '<img src=x onerror="alert(1)">',
                    "review_next_meeting": True,
                }
            )
        )
        wizard = (
            self.env["community.meeting.create.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "step": "people",
                    "series_id": self.series.id,
                    "name": "Next review",
                    "start_datetime": "2026-11-15 10:00:00",
                    "duration_hours": 1,
                }
            )
        )
        wizard.action_next()
        line = wizard.carry_line_ids.filtered(lambda row: row.source_id == source)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.agenda_type_id, source.agenda_type_id)
        self.assertEqual(line.priority, "1")
        self.assertEqual(
            line.estimated_minutes,
            self.series._point_estimated_minutes_default(),
        )
        summary = str(wizard.review_summary)
        self.assertIn("&lt;img", summary)
        self.assertNotIn("<img", summary)

    def test_review_duration_warning_updates_with_agenda_and_duration(self):
        wizard = self.env["community.meeting.create.wizard"].create(
            {
                "name": "Duration warning",
                "duration_hours": 1,
            }
        )
        point = self.env["community.meeting.point.wizard"].create(
            {
                "creation_wizard_id": wizard.id,
                "name": "Long point",
                "agenda_type_id": self.env.ref(
                    "community_meetings.agenda_type_discussion"
                ).id,
                "estimated_minutes": 75,
                "included": True,
            }
        )
        marker = "o_meeting_review_over_budget"
        self.assertIn(marker, str(wizard.review_summary))
        self.assertIn("by 15 min.", str(wizard.review_summary))
        wizard.duration_hours = 1.25
        self.assertNotIn(marker, str(wizard.review_summary))
        wizard.duration_hours = 1
        point.included = False
        self.assertNotIn(marker, str(wizard.review_summary))
        point.included = True
        self.assertIn(marker, str(wizard.review_summary))
        point.estimated_minutes = 60
        self.assertNotIn(marker, str(wizard.review_summary))
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Automatic point warning",
                    "has_next_meeting_point": True,
                    "has_minutes_approval_point": False,
                }
            )
        )
        wizard.series_id = series
        self.assertIn("by 5 min.", str(wizard.review_summary))

    def test_dismissed_source_with_followup_is_not_offered_and_finish_succeeds(self):
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.source.id,
                    "name": "Ongoing work",
                    "review_next_meeting": True,
                }
            )
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": self.source.id,
                "agenda_item_id": item.id,
                "name": "Still running",
            }
        )
        wizard = (
            self.env["community.meeting.carryover.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "origin_model": "agenda_item",
                    "origin_record_id": item.id,
                    "origin_meeting_id": self.source.id,
                    "destination_meeting_id": self.between.id,
                }
            )
        )
        wizard.action_request()
        transfer = (
            self.env["community.meeting.carryover"]
            .with_user(self.editor)
            .search(
                [
                    ("origin_agenda_item_id", "=", item.id),
                ],
                limit=1,
            )
        )
        self.assertEqual(transfer.status, "proposed")
        transfer.action_dismiss("Not needed now")
        self.assertEqual(transfer.status, "dismissed")

        wizard = (
            self.env["community.meeting.create.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "step": "people",
                    "series_id": self.series.id,
                    "name": "Later meeting",
                    "start_datetime": "2026-11-15 10:00:00",
                    "duration_hours": 1,
                }
            )
        )
        wizard.action_next()
        offered = wizard.carry_line_ids.filtered(lambda line: line.source_id == item)
        self.assertFalse(
            offered, "A dismissed source must not be offered again in the wizard."
        )

    def test_finish_does_not_reuse_a_closed_transfer(self):
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.source.id,
                    "name": "Ongoing work 2",
                    "review_next_meeting": True,
                }
            )
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": self.source.id,
                "agenda_item_id": item.id,
                "name": "Still running",
            }
        )
        wizard = (
            self.env["community.meeting.carryover.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "origin_model": "agenda_item",
                    "origin_record_id": item.id,
                    "origin_meeting_id": self.source.id,
                    "destination_meeting_id": self.between.id,
                }
            )
        )
        wizard.action_request()
        transfer = (
            self.env["community.meeting.carryover"]
            .with_user(self.editor)
            .search(
                [
                    ("origin_agenda_item_id", "=", item.id),
                ],
                limit=1,
            )
        )
        transfer.action_dismiss("Not needed now")

        # A stale line referencing the closed transfer (e.g. a race) must fail
        # with an understandable "no longer eligible" error, never reuse it.
        wizard = (
            self.env["community.meeting.create.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "step": "carryover",
                    "series_id": self.series.id,
                    "name": "Later meeting 2",
                    "start_datetime": "2026-11-22 10:00:00",
                    "duration_hours": 1,
                    "carry_line_ids": [
                        (
                            0,
                            0,
                            {
                                "candidate_key": f"source:{item.id}",
                                "source_id": item.id,
                                "name": item.name,
                                "decision": "include",
                            },
                        )
                    ],
                }
            )
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_finish()
