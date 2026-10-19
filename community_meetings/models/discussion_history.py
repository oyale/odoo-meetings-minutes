from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import is_html_empty


class AgendaDiscussionHistory(models.Model):
    _inherit = "community.meeting.agenda.item"

    discard_previous_discussion = fields.Boolean(
        string="Start without previous notes",
        copy=False,
        help="Hide earlier discussion here and stop carrying it into later meetings. Original notes are preserved.",
    )
    discussion_history = fields.Json(compute="_compute_discussion_history", compute_sudo=False)
    has_previous_discussion = fields.Boolean(compute="_compute_discussion_history", compute_sudo=False)
    previous_discussion_html = fields.Html(
        string="Previous discussion",
        compute="_compute_discussion_history",
        compute_sudo=False,
    )

    def _discussion_predecessor_ids(self, frontier):
        """Resolve one level of predecessor IDs, batching recurring lookups."""
        if not frontier:
            return {}
        sudo_frontier = frontier.sudo()
        source_ids = {}
        recurring = {}
        topic_ids = set()
        company_ids = set()
        latest_start = False
        for item in sudo_frontier:
            if item.kind in ("minutes_approval", "next_meeting") or not item.meeting_id.start_datetime:
                continue
            transfer = item.carryover_id
            source = (
                transfer.origin_agenda_item_id
                or transfer.origin_action_id.agenda_item_id
                or transfer.origin_resolution_id.agenda_item_id
            )
            if source:
                source_ids[item.id] = source.id
                continue
            previous_topic = item.topic_id.previous_occurrence_id
            if not previous_topic:
                continue
            start = item.meeting_id.start_datetime
            recurring[item.id] = (previous_topic.id, item.company_id.id, start)
            topic_ids.add(previous_topic.id)
            company_ids.add(item.company_id.id)
            latest_start = max(latest_start or start, start)

        candidates_by_topic = {}
        if topic_ids:
            candidates = self.sudo().search(
                [
                    ("topic_id", "in", list(topic_ids)),
                    ("company_id", "in", list(company_ids)),
                    ("meeting_id.start_datetime", "<", latest_start),
                    ("kind", "not in", ["minutes_approval", "next_meeting"]),
                ]
            )
            for candidate in candidates:
                candidates_by_topic.setdefault(candidate.topic_id.id, []).append(candidate)
            for item_id, (topic_id, company_id, start) in recurring.items():
                candidates = [
                    candidate
                    for candidate in candidates_by_topic.get(topic_id, [])
                    if candidate.company_id.id == company_id
                    and candidate.meeting_id.start_datetime
                    and candidate.meeting_id.start_datetime < start
                ]
                predecessor = max(
                    candidates,
                    key=lambda candidate: (candidate.meeting_id.start_datetime, candidate.id),
                    default=self.browse(),
                )
                if predecessor:
                    source_ids[item_id] = predecessor.id

        return source_ids

    def _accessible_discussion_predecessors(self, frontier, predecessor_ids):
        """Resolve IDs under normal rules; an inaccessible source stops the chain."""
        source_ids = set(predecessor_ids.values())
        if not source_ids:
            return {}
        sources = self.search(
            [
                ("id", "in", list(source_ids)),
                ("meeting_id.state", "!=", "cancelled"),
                ("kind", "not in", ["minutes_approval", "next_meeting"]),
            ]
        )
        source_meeting_ids = set(sources.mapped("meeting_id").ids)
        readable_meeting_ids = set(self.env["community.meeting"].search([("id", "in", list(source_meeting_ids))]).ids)
        current_by_id = {item.id: item for item in frontier}
        sources_by_id = {item.id: item for item in sources}
        result = {}
        for current_id, source_id in predecessor_ids.items():
            current = current_by_id[current_id]
            source = sources_by_id.get(source_id)
            if not source or source.meeting_id.id not in readable_meeting_ids:
                continue
            if source.company_id != current.company_id:
                continue
            if (
                not source.meeting_id.start_datetime
                or source.meeting_id.start_datetime >= current.meeting_id.start_datetime
            ):
                continue
            result[current_id] = source
        return result

    def _resolve_discussion_history(self):
        """Resolve visible lineage by agenda depth, not one query per card."""
        predecessor_ids = {}
        sources_by_id = {}
        frontier = self
        seen = set(self.ids)
        while frontier:
            identities = frontier._discussion_predecessor_ids(frontier)
            accessible = frontier._accessible_discussion_predecessors(frontier, identities)
            next_frontier = self.browse()
            for item_id in identities:
                source = accessible.get(item_id)
                if not source:
                    continue
                predecessor_ids[item_id] = source.id
                sources_by_id[source.id] = source
                current = frontier.browse(item_id)
                if current.discard_previous_discussion or source.discard_previous_discussion or source.id in seen:
                    continue
                seen.add(source.id)
                next_frontier |= source
            frontier = next_frontier
        return predecessor_ids, sources_by_id

    @api.depends(
        "discard_previous_discussion",
        "discussion_notes",
        "topic_id.previous_occurrence_id",
        "carryover_id",
        "kind",
        "meeting_id.start_datetime",
        "topic_id.all_participation_ids.discussion_notes",
        "topic_id.all_participation_ids.discard_previous_discussion",
        "topic_id.previous_occurrence_id.all_participation_ids.discussion_notes",
        "topic_id.previous_occurrence_id.all_participation_ids.discard_previous_discussion",
        "carryover_id.origin_agenda_item_id.discussion_notes",
        "carryover_id.origin_agenda_item_id.discard_previous_discussion",
        "carryover_id.origin_action_id.agenda_item_id.discussion_notes",
        "carryover_id.origin_action_id.agenda_item_id.discard_previous_discussion",
        "carryover_id.origin_resolution_id.agenda_item_id.discussion_notes",
        "carryover_id.origin_resolution_id.agenda_item_id.discard_previous_discussion",
    )
    @api.depends_context("uid", "company")
    def _compute_discussion_history(self):
        predecessor_ids, sources_by_id = self._resolve_discussion_history()
        for item in self:
            entries = []
            has_predecessor = False
            current = item._origin
            seen = set()
            while current and current.id not in seen:
                seen.add(current.id)
                source_id = predecessor_ids.get(current.id)
                source = sources_by_id.get(source_id)
                if not source:
                    break
                has_predecessor = True
                if not is_html_empty(source.discussion_notes):
                    entries.append(
                        {
                            "item_id": source.id,
                            "meeting_id": source.meeting_id.id,
                            "meeting_name": source.meeting_id.name,
                            "meeting_code": source.meeting_id.code,
                            "date": fields.Datetime.to_string(source.meeting_id.start_datetime),
                            "notes": source.discussion_notes,
                        }
                    )
                if source.discard_previous_discussion:
                    break
                current = source
            visible = [] if item.discard_previous_discussion else entries
            # Keep the controls visible for an empty but valid predecessor, or
            # an existing cutoff with no visible cards, so editors can set or
            # restore continuity without inventing an empty note card.
            available = bool(entries) or has_predecessor or item.discard_previous_discussion
            item.discussion_history = {"available": available, "entries": visible}
            item.has_previous_discussion = available
            item.previous_discussion_html = Markup("").join(
                Markup("<section><h4>%s — %s</h4><p>%s</p><div>%s</div></section>")
                % (entry["meeting_code"], entry["meeting_name"], entry["date"], Markup(entry["notes"]))
                for entry in visible
            )

    def write(self, vals):
        if "discard_previous_discussion" in vals:
            self.meeting_id._check_live_editorial(self)
        return super().write(vals)


class RecurringDiscussionHistory(models.Model):
    _inherit = "community.meeting.series.agenda.template"

    show_previous_discussion = fields.Boolean(
        string="Show previous discussion",
        default=True,
        help=(
            "New occurrences show earlier discussion as read-only context. "
            "Minutes approval and next meeting points always start fresh."
        ),
    )
