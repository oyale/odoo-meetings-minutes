import json

from markupsafe import Markup

from odoo import api, models
from odoo.tools import is_html_empty
from odoo.tools.misc import format_datetime


class MeetingRevisionReport(models.AbstractModel):
    _name = "report.community_meetings.report_revision_document"
    _description = "Approved Meeting Minutes PDF"

    @api.model
    def _selection_labels(self, model_name, field_name, lang):
        env = self.with_context(lang=lang).env
        return dict(env[model_name]._fields[field_name]._description_selection(env))

    @api.model
    def _prepare_approval(self, meeting, approval, revision, lang):
        if revision and not approval.get("origin"):
            approved_at = revision.approved_at
            record = (
                self.env["community.meeting.minutes.approval"]
                .sudo()
                .search([("revision_id", "=", revision.id)], limit=1)
            )
            if record and record.agenda_item_id:
                later = record.agenda_item_id.meeting_id
                live = bool(
                    later.actual_start_datetime
                    and approved_at
                    and later.actual_start_datetime <= approved_at
                    and (not later.actual_end_datetime or approved_at <= later.actual_end_datetime)
                )
                approval.update(
                    {
                        "meeting_code": later.code or "",
                        "meeting_name": later.name or "",
                        "point_name": record.agenda_item_id.name or "",
                        "offline": not live,
                        "origin": "meeting" if live else "offline",
                        "manual": False,
                    }
                )
            else:
                meeting_now = revision.meeting_id
                live = bool(
                    meeting_now.actual_start_datetime
                    and approved_at
                    and meeting_now.actual_start_datetime <= approved_at
                    and (not meeting_now.actual_end_datetime or approved_at <= meeting_now.actual_end_datetime)
                )
                approval.update({"origin": "live" if live else "direct", "manual": False})
        approved_at_value = approval.get("approved_at")
        if approved_at_value:
            approval_timezone = meeting.get("actual_start_timezone") or meeting.get("start_timezone") or ""
            approval["approved_at_display"] = format_datetime(
                self.env,
                approved_at_value,
                tz=approval_timezone or False,
                dt_format="medium",
                lang_code=lang,
            )
            approval["approved_timezone"] = approval_timezone
        return approval

    @api.model
    def _prepare_document(self, snapshot, revision=None, draft=False, lang=None):
        lang = lang or self.env.lang or self.env.user.lang
        meeting = snapshot["meeting"]
        approval = self._prepare_approval(meeting, dict(snapshot.get("approval") or {}), revision, lang)
        if approval:
            snapshot = {**snapshot, "approval": approval}
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

        actions = []
        actions_by_item = {}
        actions_by_name = {}
        for action in snapshot["actions"]:
            prepared = {
                **action,
                "description_html": Markup(action.get("description") or ""),
                "state_label": action_states.get(action.get("state"), action.get("state", "")),
                "kind_label": action_kinds.get(action.get("followup_kind"), action.get("followup_kind", "")),
            }
            actions.append(prepared)
            if action.get("agenda_item_id"):
                actions_by_item.setdefault(action["agenda_item_id"], []).append(prepared)
            if action.get("agenda_item"):
                actions_by_name.setdefault(action["agenda_item"], []).append(prepared)
        agenda = []
        for item in snapshot["agenda"]:
            disposition = item.get("disposition") or ""
            decision = item.get("decision_result") or ""
            item_actions = actions_by_item.get(item.get("id"))
            if item_actions is None:
                item_actions = actions_by_name.get(item.get("name"), [])
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
                    "actions": item_actions,
                }
            )
        return {
            "revision": revision,
            "snapshot": snapshot,
            "draft": draft,
            "meeting": meeting,
            "has_description": not is_html_empty(meeting.get("description")),
            "has_minutes_notes": not is_html_empty(meeting.get("minutes_notes")),
            "description": Markup(meeting["description"]),
            "minutes_notes": Markup(meeting["minutes_notes"]),
            "agenda": agenda,
            "general_resolutions": [resolution_doc(resolution) for resolution in snapshot["general_resolutions"]],
            "actions": actions,
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

    @api.model
    def _render_revision_preview(self, revision):
        snapshot = json.loads(revision.snapshot_json)
        doc = self._prepare_document(snapshot, revision=revision, lang=self.env.user.lang)
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
