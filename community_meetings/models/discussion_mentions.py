"""Person attribution in minutes, without chatter notifications or contact links."""

from lxml import etree, html
from markupsafe import escape

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression


def mention_nodes(value):
    root = html.fragment_fromstring(value or "", create_parent="div")
    return root, root.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' o_meeting_person_mention ')]")


def normalize_mentions(value, previous_html, resolve_label, invalid_message):
    """Canonicalize mention spans into inert HTML.

    ``resolve_label(identifier)`` returns the canonical label for a new mention
    or raises. Historical mentions keep their recorded label.
    """
    root, nodes = mention_nodes(value)
    if not nodes:
        return value
    _previous_root, previous = mention_nodes(previous_html)
    historical = {(node.get("data-oe-id"), node.text_content()) for node in previous}
    for node in nodes:
        identifier = node.get("data-oe-id", "")
        if node.get("data-oe-model") != "res.partner" or not identifier.isdecimal() or int(identifier) <= 0:
            raise ValidationError(invalid_message)
        label = node.text_content()
        if (identifier, label) not in historical:
            label = resolve_label(identifier)
        # Canonical inert HTML: no navigation, remote image or executable payload.
        tail = node.tail
        node.clear()
        node.tag = "span"
        node.attrib.update(
            {
                "data-oe-model": "res.partner",
                "data-oe-id": identifier,
                "class": "o_meeting_person_mention",
                "contenteditable": "false",
            }
        )
        node.text = label
        node.tail = tail
    return str(escape(root.text or "")) + "".join(
        etree.tostring(child, encoding="unicode", method="html") for child in root
    )


class AgendaDiscussionMentions(models.Model):
    _inherit = "community.meeting.agenda.item"

    def _mention_partner_domain(self):
        self.ensure_one()
        return [
            ("is_company", "=", False),
            ("active", "=", True),
            ("company_id", "in", [False, self.meeting_id.company_id.id]),
        ]

    def get_discussion_mention_suggestions(self, search="", limit=20, offset=0):
        """Return only readable people; an invitation is a ranking hint, not access."""
        self.ensure_one()
        self.check_access("write")
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("Only meeting editors can search discussion mentions."))
        self.meeting_id._check_live_editorial(self)
        limit = max(1, min(int(limit), 20))
        offset = max(0, int(offset))
        if offset > 10000:
            return []
        domain = self._mention_partner_domain()
        if search:
            domain = expression.AND([domain, [("name", "ilike", str(search)[:100])]])
        partners = self.env["res.partner"]
        invited = self.meeting_id.attendee_partner_ids.ids
        preferred_domain = expression.AND([domain, [("id", "in", invited)]])
        preferred_count = partners.search_count(preferred_domain)
        candidates = partners.search(preferred_domain, limit=limit, offset=offset, order="name, id")
        if len(candidates) < limit:
            candidates |= partners.search(
                expression.AND([domain, [("id", "not in", invited)]]),
                limit=limit - len(candidates),
                offset=max(0, offset - preferred_count),
                order="name, id",
            )
        return [{"id": partner.id, "name": partner.name} for partner in candidates]

    def _mention_label(self, identifier):
        partner = self.env["res.partner"].search(
            expression.AND([self._mention_partner_domain(), [("id", "=", int(identifier))]]),
            limit=1,
        )
        if not partner:
            raise AccessError(_("This contact is not available for a discussion mention."))
        return "@" + partner.name

    def _normalize_mentions(self, value, previous_html=""):
        self.ensure_one()
        return normalize_mentions(
            value,
            previous_html,
            self._mention_label,
            _("Choose a valid contact for the discussion mention."),
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.discussion_notes:
                normalized = record._normalize_mentions(record.discussion_notes)
                if normalized != record.discussion_notes:
                    record.write({"discussion_notes": normalized})
        return records

    def write(self, vals):
        if "discussion_notes" not in vals:
            return super().write(vals)
        for record in self:
            values = dict(vals)
            values["discussion_notes"] = record._normalize_mentions(vals["discussion_notes"], record.discussion_notes)
            super(AgendaDiscussionMentions, record).write(values)
        return True
