from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDiscussionMentions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Mention editor",
                "login": "mention-editor-82",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                        ]
                    )
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.person = self.env["res.partner"].create({"name": "Mention Person 82"})
        self.meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Mention meeting",
                    "start_datetime": "2026-11-01 10:00:00",
                    "attendee_partner_ids": [Command.link(self.editor.partner_id.id)],
                }
            )
        )
        self.point = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.meeting.id,
                    "name": "Attributed discussion",
                }
            )
        )

    def mention(self, person=None, label="forged label"):
        return (
            '<p><a class="o_meeting_person_mention" data-oe-model="res.partner" '
            f'data-oe-id="{(person or self.person).id}" '
            f'href="/web">{label}</a> speaks</p>'
        )

    def test_candidates_prioritize_invitees_without_user_duplicates(self):
        self.env["res.users"].create(
            {
                "partner_id": self.person.id,
                "login": "mentioned-user-82",
                "groups_id": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        # Keep only the target in the invited group. The editor is also an
        # attendee in the shared fixture, and collation-dependent name order
        # must not decide which of two invited contacts comes first here.
        self.meeting.attendee_partner_ids = [Command.set([self.person.id])]
        candidates = self.point.get_discussion_mention_suggestions("Mention Person 82")
        self.assertEqual(candidates, [{"id": self.person.id, "name": self.person.name}])
        self.assertEqual(self.point.get_discussion_mention_suggestions(limit=1)[0]["id"], self.person.id)
        self.assertEqual(self.point.get_discussion_mention_suggestions("no-such-name-82"), [])
        self.assertNotIn(self.person.id, [p["id"] for p in self.point.get_discussion_mention_suggestions(offset=1)])

    def test_canonical_html_is_inert_and_historical_name_survives(self):
        followers = self.meeting.message_partner_ids
        messages = self.meeting.message_ids
        self.point.discussion_notes = self.mention()
        saved = str(self.point.discussion_notes)
        self.assertIn("@Mention Person 82", saved)
        self.assertIn("data-oe-id=", saved)
        self.assertNotIn("href=", saved)
        self.assertNotIn("<a", saved)
        self.person.write({"name": "Renamed person", "active": False})
        self.point.discussion_notes = saved.replace(" speaks", " speaks again")
        self.assertIn("@Mention Person 82", self.point.discussion_notes)
        self.assertEqual(self.meeting.message_partner_ids, followers)
        self.assertEqual(self.meeting.message_ids, messages)

    def test_search_and_forged_mentions_respect_record_rules(self):
        self.point.discussion_notes = self.mention()
        historical = str(self.point.discussion_notes)
        self.env["ir.rule"].create(
            {
                "name": "Hide mentioned contact",
                "model_id": self.env.ref("base.model_res_partner").id,
                "domain_force": str([("id", "!=", self.person.id)]),
            }
        )
        self.assertFalse(self.point.get_discussion_mention_suggestions("Mention Person 82"))
        self.point.discussion_notes = historical + "<p>Continued discussion</p>"
        self.assertIn("@Mention Person 82", self.point.discussion_notes)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.point.discussion_notes = self.mention()

    def test_other_company_people_are_excluded_even_with_multicompany_access(self):
        company = self.env["res.company"].create({"name": "Other mention company"})
        self.editor.company_ids += company
        outsider = self.env["res.partner"].create({"name": "Outside Person 82", "company_id": company.id})
        point = self.point.with_context(allowed_company_ids=[self.meeting.company_id.id, company.id])
        self.assertFalse(point.get_discussion_mention_suggestions("Outside Person 82"))
        with self.assertRaises(AccessError), self.cr.savepoint():
            point.discussion_notes = self.mention(person=outsider)

    def test_readonly_meeting_reader_cannot_search_mentions(self):
        reader = self.env["res.users"].create(
            {
                "name": "Mention reader",
                "login": "mention-reader-82",
                "groups_id": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        self.meeting.reader_user_ids += reader
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.point.with_user(reader).get_discussion_mention_suggestions()

    def test_invalid_identity_and_create_payload_are_validated(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.point.discussion_notes = (
                '<span class="o_meeting_person_mention" data-oe-model="res.partner" data-oe-id="bad">@Name</span>'
            )
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["community.meeting.agenda.item"].with_user(self.editor).create(
                {
                    "meeting_id": self.meeting.id,
                    "name": "Forged person",
                    "discussion_notes": (
                        '<span class="o_meeting_person_mention" data-oe-model="res.partner" '
                        'data-oe-id="999999999">@Name</span>'
                    ),
                }
            )

    def test_escaped_leading_text_stays_text_when_a_mention_is_normalized(self):
        self.point.discussion_notes = '&lt;img src="https://invalid.example/pixel"&gt;' + self.mention()
        self.assertIn("&lt;img", self.point.discussion_notes)
        self.assertNotIn("<img src=", self.point.discussion_notes)

    def test_ordinary_contact_links_keep_their_existing_format(self):
        link = f'<a data-oe-model="res.partner" data-oe-id="{self.person.id}" href="/web">Contact link</a>'
        self.point.discussion_notes = "<p>" + link + "</p>" + self.mention()
        self.assertIn('href="/web"', self.point.discussion_notes)
        self.assertIn("Contact link</a>", self.point.discussion_notes)

    def test_identical_names_remain_available_on_later_pages(self):
        people = self.env["res.partner"].create([{"name": "Homonym 82"} for _ in range(23)])
        first = self.point.get_discussion_mention_suggestions("Homonym 82", offset=0)
        second = self.point.get_discussion_mention_suggestions("Homonym 82", offset=20)
        self.assertEqual(len(first), 20)
        self.assertEqual(len(second), 3)
        self.assertEqual({p["id"] for p in first + second}, set(people.ids))
        self.assertEqual(self.point.get_discussion_mention_suggestions("Homonym 82", offset=10001), [])

    def test_editorial_policy_applies_to_search_and_writes(self):
        self.meeting.action_schedule()
        self.meeting.action_start_meeting()
        with self.assertRaises(UserError), self.cr.savepoint():
            self.point.get_discussion_mention_suggestions()
        self.point.action_start_timing()
        self.assertTrue(self.point.get_discussion_mention_suggestions())
        self.meeting.action_pause_meeting()
        with self.assertRaises(UserError), self.cr.savepoint():
            self.point.get_discussion_mention_suggestions()
        with self.assertRaises(UserError), self.cr.savepoint():
            self.point.discussion_notes = self.mention()

    def test_public_content_keeps_published_name_without_live_contact_lookup(self):
        self.point.discussion_notes = self.mention()
        self.editor.groups_id += self.env.ref("community_meetings.group_meeting_approver")
        self.meeting.action_schedule()
        self.meeting.action_mark_held()
        self.meeting.action_draft_minutes()
        self.assertIn("@Mention Person 82", self.meeting.get_minutes_preview_html())
        report = self.env["ir.actions.report"]
        with patch.object(type(report), "_render_qweb_pdf", return_value=(b"%PDF-1.4 fixture", "pdf")):
            revision = self.meeting.action_approve_minutes()
        before = (revision.snapshot_json, revision.snapshot_sha256, revision.pdf_attachment_id.datas)
        self.person.unlink()
        revision.invalidate_recordset()
        after = (revision.snapshot_json, revision.snapshot_sha256, revision.pdf_attachment_id.datas)
        self.assertIn("@Mention Person 82", revision.snapshot_json)
        self.assertEqual(after, before)
