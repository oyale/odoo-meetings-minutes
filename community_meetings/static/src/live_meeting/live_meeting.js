/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const OUTCOMES = {
    information: [["open", "Pending"], ["discussed", "Discussed"], ["deferred", "Postponed"]],
    discussion: [["open", "Pending"], ["discussed", "Discussed"], ["closed", "Resolved"], ["deferred", "Postponed"]],
    decision: [["pending", "Pending"], ["discussed", "Discussed — decision pending"], ["approved", "Approved"], ["denied", "Denied"], ["deferred", "Postponed"]],
};

export class LiveMeeting extends Component {
    static template = "community_meetings.LiveMeeting";
    static props = ["action", "*", "close?"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, saving: 0, saveError: false, submitting: {}, deferrals: {}, meeting: {}, items: [], types: [], dissents: [], actions: [], expanded: {}, newDissent: {}, newAction: {}, attendees: [] });
        this.pendingWrites = new Map();
        this.beforeUnload = (ev) => {
            if (this.pendingWrites.size || Object.values(this.state.submitting).some(Boolean)) {
                ev.preventDefault();
                ev.returnValue = "";
            }
        };
        onWillStart(() => this.load());
        onMounted(() => window.addEventListener("beforeunload", this.beforeUnload));
        onWillUnmount(() => window.removeEventListener("beforeunload", this.beforeUnload));
    }

    get meetingId() { return this.props.action.params.meeting_id; }
    get locked() { return ["approved", "cancelled"].includes(this.state.meeting.state); }

    async load() {
        const [meetings, items, types, dissents, actions] = await Promise.all([
            this.orm.read("community.meeting", [this.meetingId], ["name", "code", "state", "start_datetime", "end_datetime", "organizer_id", "location", "meeting_url", "attendee_partner_ids", "minutes_notes", "series_id"]),
            this.orm.searchRead("community.meeting.agenda.item", [["meeting_id", "=", this.meetingId]], ["name", "sequence", "agenda_type_id", "kind", "disposition", "decision_result", "description", "discussion_notes", "deferral_reason"], { order: "sequence, id" }),
            this.orm.searchRead("community.meeting.agenda.type", [], ["name", "behavior", "active"], { order: "sequence, name", context: { active_test: false } }),
            this.orm.searchRead("community.meeting.dissent", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "body", "kind", "author_display_name", "author_partner_id"], { order: "sequence, id" }),
            this.orm.searchRead("community.meeting.action", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "name", "description", "responsible_user_id", "deadline", "state"], { order: "deadline, id" }),
        ]);
        this.state.meeting = meetings[0];
        this.state.attendees = meetings[0].attendee_partner_ids.length
            ? await this.orm.searchRead("res.partner", [["id", "in", meetings[0].attendee_partner_ids]], ["name"], { order: "name" })
            : [];
        this.state.items = items;
        this.state.types = types;
        this.state.dissents = dissents;
        this.state.actions = actions;
        this.state.expanded = Object.fromEntries(items.map((item, index) => [item.id, index === 0]));
        this.state.loading = false;
    }

    label(value) { return Array.isArray(value) ? value[1] : (value || ""); }
    attendees() {
        return this.state.attendees.map((partner) => partner.name).join(", ") || "No attendees listed";
    }
    typeBehavior(item) { return this.state.types.find((type) => type.id === item.agenda_type_id?.[0])?.behavior || item.kind; }
    pointOutcome(item) {
        if (this.typeBehavior(item) === "decision") {
            return item.disposition === "deferred" ? "deferred" : item.decision_result === "pending" && item.disposition === "discussed" ? "discussed" : item.decision_result || "pending";
        }
        return item.disposition;
    }
    outcomeOptions(item) { return OUTCOMES[this.typeBehavior(item)] || OUTCOMES.discussion; }
    pointDissents(item) { return this.state.dissents.filter((row) => row.agenda_item_id?.[0] === item.id); }
    pointActions(item) { return this.state.actions.filter((row) => row.agenda_item_id?.[0] === item.id); }
    toggle(item) { this.state.expanded[item.id] = !this.state.expanded[item.id]; }

    async write(key, model, ids, values, apply) {
        const previous = this.pendingWrites.get(key) || Promise.resolve();
        const operation = previous.catch(() => {}).then(async () => {
            this.state.saving++;
            this.state.saveError = false;
            try {
                await this.orm.write(model, ids, values);
                apply?.();
            } catch (error) {
                this.state.saveError = true;
                this.notification.add("Could not save this change. Your text is still available; retry by editing the field again.", { type: "danger" });
            } finally {
                this.state.saving--;
                if (this.pendingWrites.get(key) === operation) this.pendingWrites.delete(key);
            }
        });
        this.pendingWrites.set(key, operation);
        return operation;
    }

    async updateItem(item, field, value) {
        const normalized = field === "agenda_type_id" ? Number(value) : value;
        return this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], { [field]: normalized }, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result"]);
            Object.assign(item, saved);
        });
    }

    async updateOutcome(item, value) {
        if (value === "deferred") {
            this.state.deferrals[item.id] = { reason: item.deferral_reason || "" };
            this.state.expanded[item.id] = true;
            return;
        }
        let values;
        if (this.typeBehavior(item) === "decision") {
            values = value === "deferred"
                ? { disposition: "deferred", decision_result: "pending" }
                : value === "discussed"
                    ? { disposition: "discussed", decision_result: "pending" }
                    : { disposition: value === "approved" || value === "denied" ? "closed" : "open", decision_result: value };
        } else {
            values = { disposition: value };
        }
        return this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], values, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result"]);
            Object.assign(item, saved);
        });
    }

    setDeferralReason(item, value) {
        this.state.deferrals[item.id] ||= { reason: item.deferral_reason || "" };
        this.state.deferrals[item.id].reason = value;
    }

    cancelDeferral(item) { delete this.state.deferrals[item.id]; }

    async saveDeferral(item) {
        const reason = (this.state.deferrals[item.id]?.reason || "").trim();
        if (!reason) {
            this.notification.add("Add a reason before postponing this point.", { type: "warning" });
            return;
        }
        await this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], {
            disposition: "deferred", deferral_reason: reason,
            ...(this.typeBehavior(item) === "decision" ? { decision_result: "pending" } : {}),
        }, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result", "deferral_reason"]);
            Object.assign(item, saved);
            delete this.state.deferrals[item.id];
        });
    }

    async requestCarryover(item) {
        const reason = (this.state.deferrals[item.id]?.reason || "").trim();
        if (!reason) {
            this.notification.add("Add a reason before requesting a carryover.", { type: "warning" });
            return;
        }
        try {
            const action = await this.orm.call("community.meeting.agenda.item", "action_request_followup", [[item.id]]);
            action.context = { ...action.context, default_reason: reason };
            await this.actionService.doAction(action, { onClose: async () => {
                const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result", "deferral_reason"]);
                Object.assign(item, saved);
                delete this.state.deferrals[item.id];
            } });
        } catch (error) {
            this.notification.add("Could not open the carryover request.", { type: "danger" });
        }
    }

    async saveItemText(item, field, ev) {
        const value = ev.target.value;
        if (value === (item[field] || "")) return;
        await this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], { [field]: value }, () => { item[field] = value; });
    }

    async saveMinutes(ev) {
        const value = ev.target.value;
        if (value !== (this.state.meeting.minutes_notes || "")) {
            await this.write(`meeting:${this.meetingId}`, "community.meeting", [this.meetingId], { minutes_notes: value }, () => { this.state.meeting.minutes_notes = value; });
        }
    }

    async createRecord(key, model, values, onCreated) {
        if (this.state.submitting[key]) return;
        this.state.submitting[key] = true;
        this.state.saving++;
        this.state.saveError = false;
        try {
            const [id] = await this.orm.create(model, [values]);
            const [record] = await this.orm.read(model, [id], model === "community.meeting.dissent"
                ? ["agenda_item_id", "body", "kind", "author_display_name", "author_partner_id"]
                : ["agenda_item_id", "name", "description", "responsible_user_id", "deadline", "state"]);
            onCreated(record);
        } catch (error) {
            this.state.saveError = true;
            this.notification.add("Could not save this record. Your entry is still available; retry when ready.", { type: "danger" });
        } finally {
            this.state.saving--;
            this.state.submitting[key] = false;
        }
    }

    async addDissent(item) {
        const body = (this.state.newDissent[item.id] || "").trim();
        if (!body) return;
        await this.createRecord(`dissent:${item.id}`, "community.meeting.dissent", {
            meeting_id: this.meetingId, agenda_item_id: item.id, body,
        }, (record) => {
            this.state.dissents.push(record);
            this.state.newDissent[item.id] = "";
        });
    }

    async addAction(item) {
        const form = this.state.newAction[item.id] || {};
        if (!form.name?.trim()) return;
        const values = { meeting_id: this.meetingId, agenda_item_id: item.id, name: form.name.trim(), deadline: form.deadline || false };
        await this.createRecord(`action:${item.id}`, "community.meeting.action", values, (record) => {
            this.state.actions.push(record);
            this.state.newAction[item.id] = {};
        });
    }

    setDissent(item, value) { this.state.newDissent[item.id] = value; }
    setAction(item, key, value) {
        this.state.newAction[item.id] ||= {};
        this.state.newAction[item.id][key] = value;
    }
    async updateAction(action, field, value) {
        await this.write(`action:${action.id}`, "community.meeting.action", [action.id], { [field]: value || false }, () => { action[field] = value; });
    }
    async transition(method, state) {
        const key = `meeting:${this.meetingId}`;
        if (this.state.submitting[key]) return;
        this.state.submitting[key] = true;
        try {
            await this.orm.call("community.meeting", method, [[this.meetingId]]);
            this.state.meeting.state = state;
        } catch (error) {
            this.notification.add("The meeting status could not be changed. Please retry.", { type: "danger" });
        } finally {
            this.state.submitting[key] = false;
        }
    }
    markHeld() { return this.transition("action_mark_held", "held"); }
    prepareMinutes() { return this.transition("action_draft_minutes", "minutes_draft"); }
    async close() { await this.actionService.doAction({ type: "ir.actions.act_window", res_model: "community.meeting", views: [[false, "list"], [false, "form"]], target: "current" }); }
}

registry.category("actions").add("community_meetings.live_meeting", LiveMeeting);
