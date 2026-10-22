from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgendaPreparation(models.Model):
    _inherit = "community.meeting"

    @api.model
    def _agenda_candidates(self, series, start):
        """Pure preview shared by the wizard and ordinary meeting creation."""
        if not series or not start:
            return []
        series.check_access("read")
        start = fields.Datetime.to_datetime(start)
        transfers = (
            self.env["community.meeting.carryover"]
            .search(
                [
                    ("company_id", "=", series.company_id.id),
                    ("status", "in", ("pending", "proposed")),
                    ("origin_meeting_id.state", "!=", "cancelled"),
                    ("origin_meeting_id.start_datetime", "<", start),
                    "|",
                    ("destination_series_id", "=", series.id),
                    "&",
                    ("destination_series_id", "=", False),
                    ("series_id", "=", series.id),
                ]
            )
            .filtered(
                lambda transfer: (
                    not transfer.destination_meeting_id
                    or transfer.destination_meeting_id.state == "cancelled"
                    or transfer.destination_meeting_id.start_datetime >= start
                )
            )
        )
        promoted = (
            self.env["community.meeting.topic"]
            .search(
                [
                    ("series_id", "=", series.id),
                    ("state", "=", "open"),
                    ("origin_action_id", "!=", False),
                    ("origin_action_id.meeting_id.state", "!=", "cancelled"),
                    ("origin_action_id.meeting_id.start_datetime", "<", start),
                ]
            )
            .filtered(
                lambda topic: (
                    not topic.participation_ids.filtered(
                        lambda participation: participation.meeting_id.state != "cancelled"
                    )
                )
            )
        )
        # A source whose carryover for this series was already dismissed or
        # cancelled must not be offered again: re-adding it would reuse the closed
        # transfer and fail (the next review needs explicit reprogramming).
        sources = self._carryover_candidates(series, start)
        proposals = self.env["community.meeting.topic"].search(
            [
                ("series_id", "=", series.id),
                ("state", "=", "proposed"),
                ("proposal_status", "=", "submitted"),
            ]
        )
        closed = self._closed_carryover_keys(
            {f"agenda_item:{source.id}:series:{series.id}" for source in sources}
            | {f"action:{topic.origin_action_id.id}:series:{series.id}" for topic in promoted}
        )
        candidates, represented = self._agenda_transfer_candidates(transfers, promoted)
        candidates.extend(self._agenda_source_candidates(sources, represented, promoted, series, closed))
        candidates.extend(self._agenda_promoted_candidates(promoted, series, closed))
        candidates.extend(self._agenda_proposal_candidates(proposals))
        return candidates

    @api.model
    def _agenda_transfer_candidates(self, transfers, promoted):
        candidates, represented = [], set()
        for transfer in transfers:
            source = transfer.origin_agenda_item_id
            if transfer.origin_action_id in promoted.origin_action_id:
                continue
            if source:
                represented.add(source.topic_id.id)
            candidates.append(
                {
                    "key": f"transfer:{transfer.id}",
                    "transfer_id": transfer.id,
                    "source_id": source.id,
                    "name": transfer.origin_name,
                    "origin_meeting_id": transfer.origin_meeting_id.id,
                    "reason": transfer.reason,
                }
            )
        return candidates, represented

    @api.model
    def _agenda_source_candidates(self, sources, represented, promoted, series, closed):
        candidates = []
        for source in sources:
            if source.topic_id.id in represented:
                continue
            if f"agenda_item:{source.id}:series:{series.id}" in closed:
                continue
            if not source.review_next_meeting and source.topic_id in promoted.origin_topic_id:
                continue
            represented.add(source.topic_id.id)
            candidates.append(
                {
                    "key": f"source:{source.id}",
                    "source_id": source.id,
                    "name": source.name,
                    "origin_meeting_id": source.meeting_id.id,
                    "reason": source.deferral_reason,
                }
            )
        return candidates

    @api.model
    def _agenda_promoted_candidates(self, promoted, series, closed):
        candidates = []
        for topic in promoted:
            if f"action:{topic.origin_action_id.id}:series:{series.id}" in closed:
                continue
            candidates.append(
                {
                    "key": f"topic:{topic.id}",
                    "topic_id": topic.id,
                    "name": topic.name,
                    "origin_meeting_id": topic.origin_action_id.meeting_id.id,
                    "reason": _("Follow-up promoted from a closed point."),
                }
            )
        return candidates

    @api.model
    def _agenda_proposal_candidates(self, proposals):
        candidates = []
        for proposal in proposals:
            candidates.append(
                {
                    "key": f"proposal:{proposal.id}",
                    "topic_id": proposal.id,
                    "name": proposal.name,
                    "origin_meeting_id": False,
                    "reason": _("Proposed point"),
                }
            )
        return candidates

    @api.model
    def _closed_carryover_keys(self, cycle_keys):
        if not cycle_keys:
            return set()
        return set(
            self.env["community.meeting.carryover"]
            .sudo()
            .search(
                [
                    ("cycle_key", "in", list(cycle_keys)),
                    ("status", "in", ("dismissed", "cancelled")),
                ]
            )
            .mapped("cycle_key")
        )

    def _discard_agenda_candidate(self, key):
        self.ensure_one()
        self.check_access("write")
        candidate = next(
            (c for c in self._agenda_candidates(self.series_id, self.start_datetime) if c["key"] == key),
            None,
        )
        if not candidate:
            return
        if str(key).startswith("proposal:"):
            self.env["community.meeting.topic"].browse(candidate["topic_id"]).action_reject_proposal()
            return
        transfers = self.env["community.meeting.carryover"]
        if candidate.get("transfer_id"):
            transfers.browse(candidate["transfer_id"]).action_dismiss(_("Discarded when preparing the meeting."))
            return
        topic = self.env["community.meeting.topic"].browse(candidate.get("topic_id"))
        transfer = transfers.with_context(review_carryovers_in_wizard=True).create(
            {
                "origin_model": "action" if topic else "agenda_item",
                "origin_record_id": topic.origin_action_id.id if topic else candidate["source_id"],
                "destination_series_id": self.series_id.id,
            }
        )
        transfer.action_dismiss(_("Discarded when preparing the meeting."))

    def _include_agenda_candidate(self, candidate, accept=True):
        self.ensure_one()
        self.check_access("write")
        eligible = {c["key"]: c for c in self._agenda_candidates(self.series_id, self.start_datetime)}
        candidate = eligible.get(candidate["key"])
        if not candidate:
            raise ValidationError(_("A selected point is no longer eligible. Review the points to continue."))
        transfers = self.env["community.meeting.carryover"]
        if str(candidate["key"]).startswith("proposal:"):
            # Accepting is an explicit review decision: a deferred pass leaves the
            # proposal submitted so it stays eligible for the next meeting.
            if not accept:
                return
            topic = self.env["community.meeting.topic"].browse(candidate["topic_id"])
            topic.action_accept_proposal()
            return self.env["community.meeting.agenda.item"].create(
                {
                    "meeting_id": self.id,
                    "topic_id": topic.id,
                }
            )
        if candidate.get("transfer_id"):
            transfer = transfers.browse(candidate["transfer_id"])
            if not accept:
                transfer.action_retarget(self.id)
        else:
            topic = self.env["community.meeting.topic"].browse(candidate.get("topic_id"))
            transfer = transfers.create(
                {
                    "origin_model": "action" if topic else "agenda_item",
                    "origin_record_id": topic.origin_action_id.id if topic else candidate["source_id"],
                    "destination_series_id": self.series_id.id,
                    "destination_meeting_id": self.id,
                }
            )
        if accept and transfer.status != "accepted":
            transfer.action_accept(self.id)
        return transfer.destination_item_id
