from odoo import _, api, fields, models
from odoo.exceptions import AccessError


MEETING_ROLE_XMLIDS = (
    "community_meetings.group_meeting_reader",
    "community_meetings.group_meeting_editor",
    "community_meetings.group_meeting_approver",
    "community_meetings.group_meeting_manager",
)


class ResUsers(models.Model):
    _inherit = "res.users"

    community_meeting_role_ids = fields.Many2many(
        "res.groups",
        string="Meeting roles",
        compute="_compute_community_meeting_role_ids",
        inverse="_inverse_community_meeting_role_ids",
        domain=lambda self: [("id", "in", self._community_meeting_role_groups().ids)],
        help="Choose any combination of meeting access roles. Higher roles include their implied roles.",
    )

    @api.model
    def _community_meeting_role_groups(self):
        groups = self.env["res.groups"]
        group_ids = []
        for xmlid in MEETING_ROLE_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        return groups.browse(group_ids)

    @api.depends("groups_id")
    def _compute_community_meeting_role_ids(self):
        role_groups = self._community_meeting_role_groups()
        for user in self:
            user.community_meeting_role_ids = user.groups_id & role_groups

    def _inverse_community_meeting_role_ids(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only an administrator can change meeting roles."))
        role_groups = self._community_meeting_role_groups()
        for user in self:
            selected = user.community_meeting_role_ids & role_groups
            current = user.groups_id & role_groups
            commands = [(3, group.id) for group in current - selected]
            commands.extend((4, group.id) for group in selected - current)
            if commands:
                user.write({"groups_id": commands})


class ResGroups(models.Model):
    _inherit = "res.groups"

    @api.model
    def get_groups_by_application(self):
        """Keep the meeting roles in their dedicated multi-select control."""
        role_ids = self.env["res.users"]._community_meeting_role_groups().ids
        groups_by_application = super().get_groups_by_application()
        result = []
        for app, kind, groups, category in groups_by_application:
            groups = groups.filtered(lambda group: group.id not in role_ids)
            if groups:
                result.append((app, kind, groups, category))
        return result

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        result = super().name_search(name=name, args=args, operator=operator, limit=limit)
        role_order = {
            group.id: index
            for index, group in enumerate(
                self.env["res.users"]._community_meeting_role_groups()
            )
        }
        if result and all(group_id in role_order for group_id, _label in result):
            result.sort(key=lambda item: role_order[item[0]])
        return result
