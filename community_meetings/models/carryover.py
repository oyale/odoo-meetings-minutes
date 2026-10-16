from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CommunityMeetingCarryover(models.Model):
    _name = "community.meeting.carryover"
    _description = "Meeting Agenda Carryover"
    _order = "create_date, id"
    _check_company_auto = True

    origin_meeting_id = fields.Many2one(
        "community.meeting", required=True, ondelete="restrict", index=True, check_company=True,
    )
    origin_agenda_item_id = fields.Many2one(
        "community.meeting.agenda.item", ondelete="restrict", check_company=True,
    )
    origin_resolution_id = fields.Many2one(
        "community.meeting.resolution", ondelete="restrict", check_company=True,
    )
    origin_action_id = fields.Many2one(
        "community.meeting.action", ondelete="restrict", check_company=True,
    )
    origin_name = fields.Char(required=True, readonly=True)
    origin_model = fields.Selection(
        [("agenda_item", "Agenda Item"), ("resolution", "Resolution"), ("action", "Action")],
        required=True, readonly=True,
    )
    origin_record_id = fields.Integer(required=True, readonly=True)
    origin_context = fields.Text(readonly=True)
    company_id = fields.Many2one(related="origin_meeting_id.company_id", store=True, index=True)
    series_id = fields.Many2one(related="origin_meeting_id.series_id", store=True, index=True)
    destination_meeting_id = fields.Many2one(
        "community.meeting", ondelete="restrict", check_company=True, index=True,
    )
    destination_item_id = fields.Many2one(
        "community.meeting.agenda.item", ondelete="restrict", check_company=True,
    )
    initiator_id = fields.Many2one("res.users", required=True, readonly=True, default=lambda self: self.env.user)
    reason = fields.Text()
    status = fields.Selection(
        [("pending", "Pending Destination"), ("proposed", "Awaiting Review"),
         ("accepted", "Accepted"), ("dismissed", "Dismissed"), ("cancelled", "Cancelled")],
        required=True, default="pending", index=True,
    )
    responded_by_id = fields.Many2one("res.users", readonly=True)
    responded_at = fields.Datetime(readonly=True)
    cycle_key = fields.Char(required=True, readonly=True, index=True)

    _sql_constraints = [
        ("carryover_cycle_unique", "unique(cycle_key)", "This source already has a carryover in this series or destination."),
        ("carryover_item_unique", "unique(destination_item_id)", "An agenda item can belong to only one carryover."),
    ]

    @api.constrains(
        "origin_meeting_id", "origin_agenda_item_id", "origin_resolution_id", "origin_action_id",
        "origin_model", "origin_record_id", "destination_meeting_id", "destination_item_id",
    )
    def _check_references(self):
        for transfer in self:
            sources = [transfer.origin_agenda_item_id, transfer.origin_resolution_id, transfer.origin_action_id]
            if sum(bool(source) for source in sources) != 1:
                raise ValidationError(_("A carryover must have exactly one source record."))
            source = next(source for source in sources if source)
            if source.meeting_id != transfer.origin_meeting_id:
                raise ValidationError(_("The carryover source must belong to its origin meeting."))
            expected = {
                "agenda_item": transfer.origin_agenda_item_id,
                "resolution": transfer.origin_resolution_id,
                "action": transfer.origin_action_id,
            }.get(transfer.origin_model)
            if expected != source or transfer.origin_record_id != source.id:
                raise ValidationError(_("The carryover source type and reference must agree."))
            if transfer.destination_meeting_id:
                transfer._validate_destination(transfer.destination_meeting_id)
            if transfer.destination_item_id and transfer.destination_item_id.carryover_id != transfer:
                raise ValidationError(_("The destination agenda item must link back to this carryover."))

    def _validate_destination(self, meeting):
        self.ensure_one()
        source_meeting = self.origin_meeting_id
        if meeting.company_id != source_meeting.company_id:
            raise ValidationError(_("A carryover destination must be in the same company."))
        if source_meeting.series_id and meeting.series_id != source_meeting.series_id:
            raise ValidationError(_("A carryover destination must be in the same meeting series."))
        if meeting.state not in ("draft", "scheduled"):
            raise ValidationError(_("Carryovers can only target a future draft or scheduled meeting."))
        if not source_meeting.start_datetime or not meeting.start_datetime or meeting.start_datetime <= source_meeting.start_datetime:
            raise ValidationError(_("The destination meeting must have a later scheduled start."))

    @api.model
    def _source_fields(self, model_name):
        mapping = {
            "agenda_item": ("community.meeting.agenda.item", "origin_agenda_item_id"),
            "resolution": ("community.meeting.resolution", "origin_resolution_id"),
            "action": ("community.meeting.action", "origin_action_id"),
        }
        if model_name not in mapping:
            raise ValidationError(_("This record type cannot be carried into an agenda."))
        return mapping[model_name]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("Only meeting editors can request agenda carryover."))
        results = self.browse()
        for original_vals in vals_list:
            vals = dict(original_vals)
            model_name = vals.get("origin_model")
            model, source_field = self._source_fields(model_name)
            source = self.env[model].browse(vals.get("origin_record_id")).exists()
            if not source:
                raise ValidationError(_("The carryover source is unavailable."))
            source.check_access_rights("read")
            source.check_access_rule("read")
            origin_meeting = source.meeting_id
            origin_meeting.check_access_rights("write")
            origin_meeting.check_access_rule("write")
            if origin_meeting.state == "cancelled":
                raise UserError(_("Cancelled meetings cannot start agenda carryovers."))
            destination = self.env["community.meeting"].browse(vals.get("destination_meeting_id")).exists()
            if destination:
                destination.check_access_rights("write")
                destination.check_access_rule("write")
            vals.update({
                "origin_meeting_id": origin_meeting.id,
                source_field: source.id,
                "origin_name": source.name if model_name != "action" else source.name,
                "origin_record_id": source.id,
                "initiator_id": self.env.uid,
                "status": "pending",
                "responded_by_id": False,
                "responded_at": False,
            })
            if model_name == "agenda_item":
                vals["origin_context"] = source.description or ""
            elif model_name == "resolution":
                vals["origin_context"] = source.body or ""
            else:
                vals["origin_context"] = source.description or ""
            vals["origin_context"] = vals["origin_context"][:2000]
            series = origin_meeting.series_id
            if series:
                vals["cycle_key"] = f"{model_name}:{source.id}:series:{series.id}"
            elif destination:
                vals["cycle_key"] = f"{model_name}:{source.id}:meeting:{destination.id}"
            else:
                raise ValidationError(_("Choose an explicit destination for meetings outside a series."))
            existing = self.sudo().search([("cycle_key", "=", vals["cycle_key"])], limit=1)
            if existing:
                results |= existing.with_env(self.env)
                continue
            policy = series.carryover_policy if series else "manual"
            if not destination and series:
                candidate = self._find_next_meeting(origin_meeting)
                if candidate:
                    destination = candidate.with_env(self.env)
                    try:
                        destination.check_access_rights("write")
                        destination.check_access_rule("write")
                    except AccessError:
                        destination = self.env["community.meeting"]
            if destination:
                self._validate_destination_for(origin_meeting, destination)
                vals["destination_meeting_id"] = destination.id
                vals["status"] = "proposed" if policy == "review" else "pending"
            try:
                with self.env.cr.savepoint():
                    transfer = super(CommunityMeetingCarryover, self).create(vals)
            except IntegrityError:
                transfer = self.sudo().search([("cycle_key", "=", vals["cycle_key"])], limit=1)
                if not transfer:
                    raise
                results |= transfer.with_env(self.env)
                continue
            results |= transfer
            if destination and policy == "automatic":
                transfer._materialize(destination, automatic=True)
            if model_name == "agenda_item" and vals.get("reason"):
                source.write({"disposition": "deferred", "deferral_reason": vals["reason"]})
        return results

    @api.model
    def _validate_destination_for(self, source_meeting, destination):
        if destination.company_id != source_meeting.company_id:
            raise ValidationError(_("A carryover destination must be in the same company."))
        if source_meeting.series_id and destination.series_id != source_meeting.series_id:
            raise ValidationError(_("A carryover destination must be in the same meeting series."))
        if destination.state not in ("draft", "scheduled"):
            raise ValidationError(_("Carryovers can only target a future draft or scheduled meeting."))
        if not source_meeting.start_datetime or not destination.start_datetime or destination.start_datetime <= source_meeting.start_datetime:
            raise ValidationError(_("The destination meeting must have a later scheduled start."))

    @api.model
    def _find_next_meeting(self, source_meeting):
        if not source_meeting.series_id or not source_meeting.start_datetime:
            return self.env["community.meeting"]
        return self.env["community.meeting"].sudo().search([
            ("company_id", "=", source_meeting.company_id.id),
            ("series_id", "=", source_meeting.series_id.id),
            ("state", "in", ("draft", "scheduled")),
            ("start_datetime", ">", source_meeting.start_datetime),
        ], order="start_datetime, id", limit=1)

    def _materialize(self, destination, automatic=False):
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM community_meeting_carryover WHERE id = %s FOR UPDATE", [self.id],
        )
        self.invalidate_recordset(["status", "destination_item_id"])
        if self.status == "accepted" and self.destination_item_id:
            return self.destination_item_id
        if self.status in ("dismissed", "cancelled"):
            raise UserError(_("This carryover has already been closed."))
        self._validate_destination(destination)
        if self.destination_item_id:
            return self.destination_item_id
        if destination.state not in ("draft", "scheduled"):
            raise UserError(_("The destination agenda is no longer editable."))
        labels = {"agenda_item": _("Continued topic"), "resolution": _("Resolution follow-up"), "action": _("Action follow-up")}
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": destination.id,
            "name": f"{labels[self.origin_model]}: {self.origin_name}",
            "description": _("Carried forward from %(meeting)s.", meeting=self.origin_meeting_id.code),
            "carryover_id": self.id,
        })
        write_values = {"destination_meeting_id": destination.id, "destination_item_id": item.id, "status": "accepted"}
        if not automatic:
            write_values.update({"responded_by_id": self.env.uid, "responded_at": fields.Datetime.now()})
        super(CommunityMeetingCarryover, self).write(write_values)
        return item

    def write(self, vals):
        if {"status", "origin_meeting_id", "origin_agenda_item_id", "origin_resolution_id", "origin_action_id",
            "origin_name", "origin_model", "origin_record_id", "origin_context", "initiator_id", "cycle_key",
            "destination_item_id", "destination_meeting_id", "responded_by_id", "responded_at"}.intersection(vals):
            raise UserError(_("Use a carryover workflow action to review or change a transfer."))
        if "reason" in vals and any(transfer.status in ("accepted", "dismissed", "cancelled") for transfer in self):
            raise UserError(_("A closed carryover cannot be edited."))
        return super().write(vals)

    def action_accept(self, destination_meeting_id=False):
        self.ensure_one()
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("Only meeting editors can accept carryovers."))
        self.check_access_rights("write")
        self.check_access_rule("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_carryover WHERE id = %s FOR UPDATE", [self.id],
        )
        self.invalidate_recordset(["status", "destination_item_id"])
        if self.status == "accepted":
            return True
        if self.status in ("dismissed", "cancelled"):
            raise UserError(_("This carryover has already been closed."))
        source = self.origin_meeting_id
        source.check_access_rights("write")
        source.check_access_rule("write")
        destination = self.env["community.meeting"].browse(destination_meeting_id or self.destination_meeting_id.id)
        if not destination and self.series_id:
            candidate = self._find_next_meeting(source)
            destination = candidate.with_env(self.env) if candidate else self.env["community.meeting"]
        if not destination:
            return False
        destination.check_access_rights("write")
        destination.check_access_rule("write")
        self._validate_destination(destination)
        self._materialize(destination)
        return True

    def action_retarget(self, destination_meeting_id):
        self.ensure_one()
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("Only meeting editors can retarget a carryover."))
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self.status not in ("pending", "proposed"):
            raise UserError(_("Only pending or proposed carryovers can be retargeted."))
        self.origin_meeting_id.check_access_rights("write")
        self.origin_meeting_id.check_access_rule("write")
        destination = self.env["community.meeting"].browse(destination_meeting_id)
        destination.check_access_rights("write")
        destination.check_access_rule("write")
        self._validate_destination(destination)
        policy = self.series_id.carryover_policy if self.series_id else "manual"
        cycle_key = self.cycle_key if self.series_id else f"{self.origin_model}:{self.origin_record_id}:meeting:{destination.id}"
        try:
            with self.env.cr.savepoint():
                super(CommunityMeetingCarryover, self).write({
                    "destination_meeting_id": destination.id,
                    "cycle_key": cycle_key,
                    "status": "proposed" if policy == "review" else "pending",
                    "responded_by_id": False,
                    "responded_at": False,
                })
        except IntegrityError as error:
            raise ValidationError(_("A carryover for this source and destination already exists.")) from error
        if policy == "automatic":
            self._materialize(destination, automatic=True)
        return True

    def action_dismiss(self, reason=False):
        self.ensure_one()
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("Only meeting editors can dismiss carryovers."))
        self.check_access_rights("write")
        self.check_access_rule("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_carryover WHERE id = %s FOR UPDATE", [self.id],
        )
        self.invalidate_recordset(["status"])
        if self.status in ("accepted", "dismissed", "cancelled"):
            raise UserError(_("This carryover has already been closed."))
        super(CommunityMeetingCarryover, self).write({
            "status": "dismissed", "reason": reason or self.reason,
            "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
        })
        return True

    @api.model
    def _process_new_meetings(self, meetings):
        for meeting in meetings.filtered("series_id"):
            pending = self.search([
                ("series_id", "=", meeting.series_id.id),
                ("company_id", "=", meeting.company_id.id),
                ("status", "=", "pending"),
                ("destination_meeting_id", "=", False),
                ("origin_meeting_id.start_datetime", "<", meeting.start_datetime),
            ], order="create_date, id")
            for transfer in pending:
                next_meeting = self._find_next_meeting(transfer.origin_meeting_id)
                if next_meeting != meeting:
                    continue
                transfer._validate_destination(meeting)
                meeting.check_access_rights("write")
                meeting.check_access_rule("write")
                super(CommunityMeetingCarryover, transfer).write({"destination_meeting_id": meeting.id})
                policy = transfer.series_id.carryover_policy
                if policy == "review":
                    super(CommunityMeetingCarryover, transfer).write({"status": "proposed"})
                elif policy == "automatic":
                    transfer._materialize(meeting, automatic=True)


class CommunityMeetingCarryoverWizard(models.TransientModel):
    _name = "community.meeting.carryover.wizard"
    _description = "Request Meeting Follow-up"

    origin_model = fields.Selection(
        [("agenda_item", "Agenda Item"), ("resolution", "Resolution"), ("action", "Action")],
        required=True, readonly=True,
    )
    origin_record_id = fields.Integer(required=True, readonly=True)
    origin_meeting_id = fields.Many2one("community.meeting", required=True, readonly=True)
    company_id = fields.Many2one(related="origin_meeting_id.company_id", readonly=True)
    series_id = fields.Many2one(related="origin_meeting_id.series_id", readonly=True)
    destination_meeting_id = fields.Many2one(
        "community.meeting", domain="[('company_id', '=', company_id), ('state', 'in', ['draft', 'scheduled'])]",
    )
    reason = fields.Text()

    @api.model
    def action_open_for(self, record, origin_model):
        field_map = {
            "agenda_item": "community.meeting.agenda.item",
            "resolution": "community.meeting.resolution",
            "action": "community.meeting.action",
        }
        if record._name != field_map.get(origin_model):
            raise ValidationError(_("The selected follow-up source is invalid."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Follow up at another meeting"),
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_origin_model": origin_model,
                "default_origin_record_id": record.id,
                "default_origin_meeting_id": record.meeting_id.id,
                "default_series_id": record.meeting_id.series_id.id,
            },
        }

    def action_request(self):
        self.ensure_one()
        model, _field = self.env["community.meeting.carryover"]._source_fields(self.origin_model)
        source = self.env[model].browse(self.origin_record_id).exists()
        if not source or source.meeting_id != self.origin_meeting_id:
            raise ValidationError(_("The selected follow-up source is unavailable."))
        values = {
            "origin_model": self.origin_model,
            "origin_record_id": source.id,
            "destination_meeting_id": self.destination_meeting_id.id,
            "reason": self.reason,
        }
        transfer = self.env["community.meeting.carryover"].create(values)
        return {"type": "ir.actions.act_window_close"}
