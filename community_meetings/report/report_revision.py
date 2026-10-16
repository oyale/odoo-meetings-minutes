import json

from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import AccessError


class MeetingRevisionReport(models.AbstractModel):
    _name = "report.community_meetings.report_revision_document"
    _description = "Approved Meeting Minutes PDF"

    def _get_report_values(self, docids, data=None):
        revisions = self.env["community.meeting.revision"].browse(docids)
        revisions.check_access_rights("read")
        revisions.check_access_rule("read")
        for revision in revisions:
            revision.meeting_id.check_access_rights("read")
            revision.meeting_id.check_access_rule("read")
        docs = []
        for revision in revisions:
            snapshot = json.loads(revision.snapshot_json)
            meeting = snapshot["meeting"]
            docs.append({
                "revision": revision,
                "snapshot": snapshot,
                "meeting": meeting,
                "description": Markup(meeting["description"]),
                "minutes_notes": Markup(meeting["minutes_notes"]),
                "agenda": [{
                    **item,
                    "description_html": Markup(item["description"]),
                    "discussion_html": Markup(item["discussion"]),
                    "resolutions": [{**resolution, "body_html": Markup(resolution["body"])} for resolution in item["resolutions"]],
                } for item in snapshot["agenda"]],
                "general_resolutions": [{**resolution, "body_html": Markup(resolution["body"])} for resolution in snapshot["general_resolutions"]],
                "actions": snapshot["actions"],
                "dissents": [{**dissent, "body_html": Markup(dissent["body"])} for dissent in snapshot["dissents"]],
            })
        return {"doc_ids": revisions.ids, "doc_model": "community.meeting.revision", "docs": docs}
