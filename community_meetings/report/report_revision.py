import json

from markupsafe import Markup

from odoo import api, models


class MeetingRevisionReport(models.AbstractModel):
    _name = "report.community_meetings.report_revision_document"
    _description = "Approved Meeting Minutes PDF"

    @api.model
    def _selection_labels(self, model_name, field_name, lang):
        env = self.with_context(lang=lang).env
        return dict(env[model_name]._fields[field_name]._description_selection(env))

    @api.model
    def _prepare_document(self, snapshot, revision=None, draft=False, lang=None):
        lang = lang or self.env.lang or self.env.user.lang
        meeting = snapshot["meeting"]
        dispositions = self._selection_labels("community.meeting.agenda.item", "disposition", lang)
        decisions = self._selection_labels("community.meeting.agenda.item", "decision_result", lang)
        resolution_outcomes = self._selection_labels("community.meeting.resolution", "decision_outcome", lang)
        resolution_statuses = self._selection_labels("community.meeting.resolution", "status", lang)
        topic_states = self._selection_labels("community.meeting.topic", "state", lang)
        carryover_statuses = self._selection_labels("community.meeting.carryover", "status", lang)
        action_states = self._selection_labels("community.meeting.action", "state", lang)
        action_kinds = self._selection_labels("community.meeting.action", "followup_kind", lang)

        def resolution_doc(resolution):
            return {
                **resolution,
                "body_html": Markup(resolution["body"]),
                "decision_outcome_label": resolution_outcomes.get(resolution.get("decision_outcome"), ""),
                "status_label": resolution_statuses.get(resolution.get("status"), resolution.get("status", "")),
            }

        agenda = []
        for item in snapshot["agenda"]:
            disposition = item.get("disposition") or ""
            decision = item.get("decision_result") or ""
            agenda.append(
                {
                    **item,
                    "description_html": Markup(item["description"]),
                    "discussion_html": Markup(item["discussion"]),
                    "disposition_label": dispositions.get(disposition, item.get("disposition_label") or disposition),
                    "decision_result_label": decisions.get(decision, item.get("decision_result_label") or ""),
                    "related": [
                        {
                            **related,
                            "state_label": topic_states.get(related.get("state"), related.get("state", "")),
                        }
                        for related in item.get("related", [])
                    ],
                    "resolutions": [resolution_doc(resolution) for resolution in item.get("resolutions", [])],
                }
            )
        return {
            "revision": revision,
            "snapshot": snapshot,
            "draft": draft,
            "meeting": meeting,
            "description": Markup(meeting["description"]),
            "minutes_notes": Markup(meeting["minutes_notes"]),
            "agenda": agenda,
            "general_resolutions": [resolution_doc(resolution) for resolution in snapshot["general_resolutions"]],
            "actions": [
                {
                    **action,
                    "state_label": action_states.get(action.get("state"), action.get("state", "")),
                    "kind_label": action_kinds.get(action.get("followup_kind"), action.get("followup_kind", "")),
                }
                for action in snapshot["actions"]
            ],
            "dissents": [{**dissent, "body_html": Markup(dissent["body"])} for dissent in snapshot["dissents"]],
            "carryovers": [
                {
                    **carry,
                    "status_label": carryover_statuses.get(carry.get("status"), carry.get("status", "")),
                }
                for carry in snapshot.get("carryovers", [])
            ],
        }

    @api.model
    def _render_preview(self, meeting):
        snapshot = self.env["community.meeting.revision"]._build_public_content(meeting)
        doc = self._prepare_document(snapshot, draft=True, lang=self.env.user.lang)
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
        lang = self.env.context.get("lang") or self.env.user.lang
        docs = []
        for revision in revisions:
            snapshot = json.loads(revision.snapshot_json)
            docs.append(self._prepare_document(snapshot, revision=revision, lang=lang))
        return {
            "doc_ids": revisions.ids,
            "doc_model": "community.meeting.revision",
            "docs": docs,
        }
