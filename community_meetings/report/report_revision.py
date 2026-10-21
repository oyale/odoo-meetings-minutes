import json

from markupsafe import Markup

from odoo import api, models


class MeetingRevisionReport(models.AbstractModel):
    _name = "report.community_meetings.report_revision_document"
    _description = "Approved Meeting Minutes PDF"

    @api.model
    def _prepare_document(self, snapshot, revision=None, draft=False):
        meeting = snapshot["meeting"]
        return {
            "revision": revision,
            "snapshot": snapshot,
            "draft": draft,
            "meeting": meeting,
            "description": Markup(meeting["description"]),
            "minutes_notes": Markup(meeting["minutes_notes"]),
            "agenda": [
                {
                    **item,
                    "description_html": Markup(item["description"]),
                    "discussion_html": Markup(item["discussion"]),
                    "resolutions": [
                        {**resolution, "body_html": Markup(resolution["body"])} for resolution in item["resolutions"]
                    ],
                }
                for item in snapshot["agenda"]
            ],
            "general_resolutions": [
                {**resolution, "body_html": Markup(resolution["body"])}
                for resolution in snapshot["general_resolutions"]
            ],
            "actions": snapshot["actions"],
            "dissents": [{**dissent, "body_html": Markup(dissent["body"])} for dissent in snapshot["dissents"]],
        }

    @api.model
    def _render_preview(self, meeting):
        snapshot = self.env["community.meeting.revision"]._build_public_content(meeting)
        doc = self._prepare_document(snapshot, draft=True)
        return (
            self.env["ir.qweb"]
            .with_context(lang=self.env.user.lang)
            ._render(
                "community_meetings.report_revision_preview",
                {"doc": doc, "lang": self.env.user.lang},
            )
        )

    def _get_report_values(self, docids, data=None):
        revisions = self.env["community.meeting.revision"].browse(docids)
        revisions.check_access("read")
        for revision in revisions:
            revision.meeting_id.check_access("read")
        docs = []
        for revision in revisions:
            snapshot = json.loads(revision.snapshot_json)
            docs.append(self._prepare_document(snapshot, revision=revision))
        return {
            "doc_ids": revisions.ids,
            "doc_model": "community.meeting.revision",
            "docs": docs,
        }
