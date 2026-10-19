from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor_group = cls.env.ref("community_meetings.group_meeting_editor")
        cls.reader_group = cls.env.ref("community_meetings.group_meeting_reader")
        cls.editor = cls.env["res.users"].create({
            "name": "Assigned Editor",
            "login": "assigned-editor-test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.editor_group.id])],
        })
        cls.reader = cls.env["res.users"].create({
            "name": "Assigned Reader",
            "login": "assigned-reader-test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.reader_group.id])],
        })
        cls.reader_editor = cls.env["res.users"].create({
            "name": "Reader and Editor",
            "login": "reader-editor-test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.editor_group.id])],
        })
        cls.outsider = cls.env["res.users"].create({
            "name": "No Meeting Role",
            "login": "no-meeting-role-test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def test_unassigned_editor_cannot_read_meeting(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Private meeting"})
        with self.assertRaises(AccessError):
            self.env["community.meeting"].with_user(self.reader).browse(meeting.id).read(["name"])

    def test_reader_cannot_create_meeting(self):
        with self.assertRaises(AccessError):
            self.env["community.meeting"].with_user(self.reader).create({"name": "Denied"})

    def test_approver_can_review_live_without_editorial_access(self):
        approver = self.reader
        approver.write({"groups_id": [(4, self.env.ref("community_meetings.group_meeting_approver").id)]})
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Read-only minutes review", "start_datetime": "2026-12-01 10:00:00",
            "reader_user_ids": [(4, approver.id)],
        })
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({"meeting_id": meeting.id, "name": "Review"})
        self.env["community.meeting.dissent"].with_user(self.editor).create([
            {"meeting_id": meeting.id, "agenda_item_id": item.id, "body": "Public dissent", "include_in_minutes": True},
            {"meeting_id": meeting.id, "agenda_item_id": item.id, "body": "Private dissent", "include_in_minutes": False},
        ])
        meeting.action_schedule()
        reviewed = meeting.with_user(approver)
        self.assertEqual(reviewed.action_open_live_meeting()["tag"], "community_meetings.live_meeting")
        self.assertFalse(reviewed.get_live_capabilities()["can_edit"])
        self.assertFalse(reviewed.get_live_capabilities()["can_view_editorial"])
        published = reviewed.get_live_published_dissents()
        self.assertEqual(len(published), 1)
        self.assertIn("Public dissent", published[0]["body"])
        with self.assertRaises(AccessError):
            reviewed.write({"minutes_notes": "Forbidden"})
        with self.assertRaises(AccessError):
            meeting.with_user(self.outsider).get_live_capabilities()

    def test_minutes_preview_requires_role_record_access_and_allowed_state(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Minutes preview access",
            "start_datetime": "2026-12-01 10:00:00",
            "reader_user_ids": [(4, self.reader.id), (4, self.outsider.id)],
        })
        self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Preview access point",
        })
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).get_minutes_preview_html()
        with self.assertRaises(AccessError):
            meeting.with_user(self.reader).get_minutes_preview_html()
        with self.assertRaises(AccessError):
            meeting.with_user(self.outsider).get_minutes_preview_html()

        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        self.reader.write({
            "groups_id": [(4, self.env.ref("community_meetings.group_meeting_approver").id)],
        })
        self.assertIn(
            "Draft — not approved.",
            meeting.with_user(self.reader).get_minutes_preview_html(),
        )

    def test_internal_user_gets_proposal_capability_only(self):
        self.assertTrue(self.outsider.has_group("community_meetings.group_agenda_proposer"))
        self.assertFalse(self.outsider.has_group("community_meetings.group_meeting_reader"))
        self.assertFalse(self.outsider.has_group("community_meetings.group_meeting_editor"))

    def test_meeting_roles_use_one_multiselect_in_user_access_rights(self):
        view = self.env.ref("community_meetings.view_users_form_meeting_roles")
        self.assertIn("community_meeting_role_ids", view.arch)
        self.assertIn("many2many_checkboxes", view.arch)
        roles = self.env["res.groups"].browse([
            self.env.ref(f"community_meetings.group_meeting_{role}").id
            for role in ("reader", "editor", "approver", "manager")
        ])
        generated_groups = self.env["res.groups"].get_groups_by_application()
        self.assertFalse(any(group in roles for _category, _kind, groups, _label in generated_groups for group in groups))
        role_labels = self.env["res.groups"].name_search(
            args=[("id", "in", roles.ids)], limit=None
        )
        self.assertEqual(
            [group_id for group_id, _label in role_labels],
            [self.env.ref(f"community_meetings.group_meeting_{role}").id
             for role in ("reader", "editor", "approver", "manager")],
        )
        self.assertEqual(
            self.env.ref("community_meetings.group_meeting_approver").display_name,
            "Meetings / Meeting Approver",
        )

    def test_agenda_menus_are_nested_under_meetings_app(self):
        root = self.env.ref("community_meetings.menu_community_meetings_root")
        self.assertEqual(
            root.action,
            self.env.ref("community_meetings.action_community_meetings"),
            "Clicking Meetings should open the meeting list, not its first child action.",
        )
        self.assertFalse(
            root.child_id.filtered(lambda menu: menu.name == "Meetings"),
            "The root menu already opens the meeting list; do not duplicate it as a child.",
        )
        self.assertIn(self.env.ref("base.group_user"), root.groups_id)
        for menu_xmlid in (
            "community_meetings.menu_propose_point",
            "community_meetings.menu_community_meeting_carryovers",
        ):
            with self.subTest(menu=menu_xmlid):
                self.assertEqual(self.env.ref(menu_xmlid).parent_id, root)

    def test_meeting_series_has_a_dedicated_editor_menu_and_configuration_form(self):
        menu = self.env.ref("community_meetings.menu_community_meeting_series")
        root = self.env.ref("community_meetings.menu_community_meetings_root")
        self.assertEqual(menu.parent_id, root)
        self.assertIn(self.env.ref("community_meetings.group_meeting_editor"), menu.groups_id)
        view = self.env.ref("community_meetings.view_community_meeting_series_form")
        for field_name in ("name", "company_id", "coordinator_user_ids", "carryover_policy", "active"):
            self.assertIn(field_name, view.arch)

    def test_meeting_form_exposes_incoming_carryover_review_actions_to_editors(self):
        view = self.env.ref("community_meetings.view_community_meeting_form")
        self.assertIn("incoming_carryover_ids", view.arch)
        self.assertIn('name="action_accept"', view.arch)
        self.assertIn('name="action_dismiss"', view.arch)

    def test_meeting_role_picker_preserves_independent_capabilities(self):
        user = self.env["res.users"].create({
            "name": "Combined Meeting Roles",
            "login": "combined-meeting-roles-test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        reader = self.env.ref("community_meetings.group_meeting_reader")
        editor = self.env.ref("community_meetings.group_meeting_editor")
        approver = self.env.ref("community_meetings.group_meeting_approver")
        manager = self.env.ref("community_meetings.group_meeting_manager")
        user.write({"community_meeting_role_ids": [(6, 0, [reader.id, editor.id, approver.id])]})
        self.assertTrue(user.has_group("community_meetings.group_meeting_reader"))
        self.assertTrue(user.has_group("community_meetings.group_meeting_editor"))
        self.assertTrue(user.has_group("community_meetings.group_meeting_approver"))
        self.assertFalse(user.has_group("community_meetings.group_meeting_manager"))
        self.assertNotIn(self.env.ref("community_meetings.group_agenda_proposer"), user.community_meeting_role_ids)

    def test_manager_role_picker_includes_implied_roles(self):
        user = self.env["res.users"].create({
            "name": "Meeting Manager Role",
            "login": "meeting-manager-role-test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        manager = self.env.ref("community_meetings.group_meeting_manager")
        user.write({"community_meeting_role_ids": [(6, 0, [manager.id])]})
        self.assertTrue(user.has_group("community_meetings.group_meeting_reader"))
        self.assertTrue(user.has_group("community_meetings.group_meeting_editor"))
        self.assertTrue(user.has_group("community_meetings.group_meeting_approver"))
        self.assertTrue(user.has_group("community_meetings.group_meeting_manager"))

    def test_reader_cannot_read_editorial_notes_or_dissent(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Restricted content"})
        note = self.env["community.meeting.editor.note"].with_user(self.editor).create({
            "meeting_id": meeting.id, "content": "Private editorial text",
        })
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Restricted point",
        })
        dissent = self.env["community.meeting.dissent"].with_user(self.editor).create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "body": "Restricted until approved", "include_in_minutes": False,
        })
        meeting.reader_user_ids = [(4, self.reader.id)]
        with self.assertRaises(AccessError):
            self.env["community.meeting.editor.note"].with_user(self.reader).browse(note.id).read(["content"])
        with self.assertRaises(AccessError):
            self.env["community.meeting.dissent"].with_user(self.reader).browse(dissent.id).read(["body"])

    def test_editor_who_is_only_a_reader_cannot_write_meeting(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Read-only share"})
        meeting.reader_user_ids = [(4, self.reader_editor.id)]
        self.assertEqual(
            self.env["community.meeting"].with_user(self.reader_editor).browse(meeting.id).name,
            "Read-only share",
        )
        with self.assertRaises(AccessError):
            self.env["community.meeting"].with_user(self.reader_editor).browse(meeting.id).write({"name": "Escalated"})

    def test_direct_transition_is_rejected_for_reader(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Private meeting"})
        meeting.reader_user_ids = [(4, self.reader.id)]
        with self.assertRaises(UserError):
            meeting.with_user(self.reader).action_schedule()
