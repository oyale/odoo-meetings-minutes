import logging
from datetime import datetime
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    items = env["community.meeting.agenda.item"].search(
        [("topic_id", "=", False)], order="id"
    )
    mapped = {}
    for item in items:
        transfer = item.carryover_id
        source = (
            transfer.origin_agenda_item_id
            or transfer.origin_action_id.agenda_item_id
            or transfer.origin_resolution_id.agenda_item_id
        )
        topic = source.topic_id if source else False
        if topic and env["community.meeting.agenda.item"].search_count(
            [("meeting_id", "=", item.meeting_id.id), ("topic_id", "=", topic.id)]
        ):
            _logger.warning(
                "Ambiguous legacy carryover item %s: keeping separate identity", item.id
            )
            topic = False
        if not topic:
            topic = env["community.meeting.topic"].create(
                {
                    "name": item.name,
                    "description": item.description,
                    "agenda_type_id": item.agenda_type_id.id,
                    "company_id": item.company_id.id,
                    "series_id": item.meeting_id.series_id.id,
                }
            )
        cr.execute(
            "UPDATE community_meeting_agenda_item SET topic_id=%s, review_next_meeting=%s WHERE id=%s",
            [topic.id, item.disposition == "deferred", item.id],
        )
        item.invalidate_recordset(["topic_id", "review_next_meeting"])
        item.modified(["topic_id"])
        mapped[item.id] = topic.id
    # Replay legacy history without applying validations for new user transitions.
    # Session fields and approved JSON/PDF are never rewritten.
    for topic in env["community.meeting.topic"].browse(set(mapped.values())):
        state, outcome, postponed, last = "open", False, False, False
        history = env["community.meeting.agenda.item"].search(
            [("topic_id", "=", topic.id)]
        )
        for item in sorted(
            history,
            key=lambda i: (
                i.meeting_id.start_datetime or datetime.min,
                i.meeting_id.id,
                i.id,
            ),
        ):
            followup = state == "closed" and not (
                item.kind == "decision"
                and item.decision_result in ("approved", "denied")
            )
            cr.execute(
                "UPDATE community_meeting_agenda_item SET is_followup=%s WHERE id=%s",
                [followup, item.id],
            )
            if followup:
                continue
            closed = item.disposition == "closed" or (
                item.kind == "information" and item.disposition == "discussed"
            )
            state = "closed" if closed else "open"
            outcome = (
                (item.decision_result if item.kind == "decision" else item.disposition)
                if closed
                else False
            )
            postponed, last = item.disposition == "deferred", item.id
        cr.execute(
            "UPDATE community_meeting_topic SET state=%s,outcome=%s,postponed=%s,last_participation_id=%s WHERE id=%s",
            [state, outcome or None, postponed, last or None, topic.id],
        )
    env["community.meeting.agenda.item"].invalidate_model(["is_followup"])
    env["community.meeting.topic"].invalidate_model()
    cr.execute("""UPDATE community_meeting SET duration_hours =
        CASE WHEN end_datetime > start_datetime THEN EXTRACT(EPOCH FROM (end_datetime-start_datetime))/3600 ELSE 1 END""")
    env["community.meeting"].invalidate_model(["duration_hours"])
    env["community.meeting"].search([]).modified(["duration_hours"])
    _logger.info(
        "Point migration preserved %s agenda identifiers; mapping=%s",
        len(mapped),
        mapped,
    )
