/** @odoo-module **/

import { Component, markup, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { ensureJQuery } from "@web/core/ensure_jquery";
import { useService } from "@web/core/utils/hooks";

const OUTCOMES = {
    information: [["open", _t("Pending")], ["discussed", _t("Discussed")], ["deferred", _t("Postponed")]],
    discussion: [["open", _t("Pending")], ["discussed", _t("Discussed")], ["closed", _t("Resolved")], ["deferred", _t("Postponed")]],
    decision: [["pending", _t("Pending")], ["discussed", _t("Discussed — decision pending")], ["approved", _t("Approved")], ["denied", _t("Rejected")], ["deferred", _t("Postponed")]],
};
const ACTION_STATES = { open: _t("Open"), in_progress: _t("In progress"), done: _t("Done"), cancelled: _t("Cancelled") };
const MEETING_STATES = {
    draft: _t("Draft"), scheduled: _t("Scheduled"), held: _t("Held"),
    minutes_draft: _t("Minutes to prepare"), approved: _t("Approved"), cancelled: _t("Cancelled"),
};

export class LiveMeeting extends Component {
    static template = "community_meetings.LiveMeeting";
    static props = ["action", "*", "close?"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, saving: 0, saveError: false, unsavedEditors: {}, submitting: {}, editingRecords: {}, editingTypes: {}, attendeeEditorOpen: false, attendeeIds: [], attendeeSearch: "", partnerResults: [], deferrals: {}, meeting: {}, items: [], types: [], dissents: [], actions: [], resolutions: [], privateNotes: [], users: [], expanded: {}, activeItemId: false, showPendingOnly: false, newDissent: {}, newAction: {}, newResolution: {}, newPrivateNote: {}, attendees: [] });
        this.pendingWrites = new Map();
        this.editors = new Map();
        this.editorTimers = new Map();
        this.editorMeta = new Map();
        this.partnerSearchToken = 0;
        this.beforeUnload = (ev) => {
            if (this.pendingWrites.size || Object.values(this.state.submitting).some(Boolean) || Object.values(this.state.unsavedEditors).some(Boolean)) {
                ev.preventDefault();
                ev.returnValue = "";
            }
        };
        onWillStart(async () => {
            await ensureJQuery();
            await loadBundle("web_editor.backend_assets_wysiwyg");
            const { Wysiwyg } = await odoo.loader.modules.get("@web_editor/js/wysiwyg/wysiwyg");
            this.Wysiwyg = Wysiwyg;
            await this.load();
        });
        onMounted(() => window.addEventListener("beforeunload", this.beforeUnload));
        onWillUnmount(() => {
            window.removeEventListener("beforeunload", this.beforeUnload);
            void this.flushEditors();
        });
    }

    get meetingId() { return this.props.action.params.meeting_id; }
    get locked() { return ["approved", "cancelled"].includes(this.state.meeting.state); }
    get hasUnsavedEditors() { return Object.values(this.state.unsavedEditors).some(Boolean); }

    async load() {
        const [meetings, items, types, dissents, actions, resolutions, privateNotes] = await Promise.all([
            this.orm.read("community.meeting", [this.meetingId], ["name", "code", "state", "company_id", "start_datetime", "end_datetime", "actual_start_datetime", "actual_end_datetime", "organizer_id", "location", "meeting_url", "attendee_partner_ids", "minutes_notes", "series_id"]),
            this.orm.searchRead("community.meeting.agenda.item", [["meeting_id", "=", this.meetingId]], ["name", "sequence", "agenda_type_id", "kind", "disposition", "decision_result", "description", "discussion_notes", "deferral_reason"], { order: "sequence, id" }),
            this.orm.searchRead("community.meeting.agenda.type", [], ["name", "behavior", "active"], { order: "sequence, name", context: { active_test: false } }),
            this.orm.searchRead("community.meeting.dissent", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "body", "kind", "author_display_name", "author_partner_id"], { order: "sequence, id" }),
            this.orm.searchRead("community.meeting.action", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "name", "description", "responsible_user_id", "deadline", "state"], { order: "deadline, id" }),
            this.orm.searchRead("community.meeting.resolution", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "title", "body", "status", "decision_outcome"], { order: "id" }),
            this.orm.searchRead("community.meeting.editor.note", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "content"], { order: "id" }),
        ]);
        this.state.meeting = meetings[0];
        this.state.attendeeIds = [...meetings[0].attendee_partner_ids];
        const users = await this.orm.searchRead("res.users", [
            ["active", "=", true], ["share", "=", false], ["company_ids", "in", [meetings[0].company_id[0]]],
        ], ["name"], { order: "name", limit: 200 });
        this.state.attendees = meetings[0].attendee_partner_ids.length
            ? await this.orm.searchRead("res.partner", [["id", "in", meetings[0].attendee_partner_ids]], ["name"], { order: "name" })
            : [];
        this.state.items = items;
        this.state.types = types;
        this.state.dissents = dissents;
        this.state.actions = actions;
        this.state.resolutions = resolutions;
        this.state.privateNotes = privateNotes;
        this.state.users = users;
        this.state.expanded = Object.fromEntries(items.map((item, index) => [item.id, index === 0]));
        this.state.activeItemId = items[0]?.id || false;
        this.state.loading = false;
    }

    label(value) { return Array.isArray(value) ? value[1] : (value || ""); }
    dateTime(value) { return value ? formatDateTime(deserializeDateTime(value)) : _t("Not set"); }
    stateLabel(value) { return MEETING_STATES[value] || value || ""; }
    actionStateLabel(value) { return ACTION_STATES[value] || value || ""; }
    safeHtml(value) { return markup(value || ""); }
    richTextOptions(value, key, model, recordId, field) {
        return {
            value: value || "",
            autostart: false,
            recordInfo: { res_model: model, res_id: recordId },
            allowCommandImage: false,
            allowCommandVideo: false,
            userGeneratedContent: true,
            onWysiwygBlur: () => this.saveRichText(key, recordId, model, field),
        };
    }
    richTextStarter(key, recordId, model, field) {
        return (wysiwyg) => this.startRichText(key, wysiwyg, recordId, model, field);
    }
    async startRichText(key, wysiwyg, recordId, model, field) {
        this.editors.set(key, wysiwyg);
        this.editorMeta.set(key, { recordId, model, field });
        await wysiwyg.startEdition();
        wysiwyg.$editable[0].classList.add("odoo-editor-qweb");
        const label = key === "minutes_notes" ? _t("Meeting minutes")
            : key.startsWith("discussion_notes:") ? _t("Discussion notes")
                : key.startsWith("dissent:") ? _t("Dissent or reservation")
                    : key.startsWith("resolution:") ? _t("Agreement") : _t("Private editorial note");
        wysiwyg.$editable[0].setAttribute("aria-label", label);
        wysiwyg.odooEditor.addEventListener("historyStep", () => {
            this.state.unsavedEditors[key] = true;
            clearTimeout(this.editorTimers.get(key));
            this.editorTimers.set(key, setTimeout(() => this.saveRichText(key, recordId, model, field), 700));
        });
    }
    async saveRichText(key, recordId, model, field) {
        clearTimeout(this.editorTimers.get(key));
        this.editorTimers.delete(key);
        const editor = this.editors.get(key);
        if (!editor) return;
        const value = editor.getValue();
        const record = field === "minutes_notes" ? this.state.meeting
            : model === "community.meeting.agenda.item" ? this.state.items.find((row) => row.id === recordId)
                : model === "community.meeting.resolution" ? this.state.resolutions.find((row) => row.id === recordId)
                    : model === "community.meeting.editor.note" ? this.state.privateNotes.find((row) => row.id === recordId)
                        : this.state.dissents.find((row) => row.id === recordId);
        if (!record) return false;
        if (value === (record[field] || "")) {
            delete this.state.unsavedEditors[key];
            return true;
        }
        const queueKey = field === "minutes_notes" ? `meeting:${this.meetingId}` : `${model}:${recordId}`;
        const savedSuccessfully = await this.write(queueKey, model, [recordId], { [field]: value }, async () => {
            const [saved] = await this.orm.read(model, [recordId], [field]);
            record[field] = saved[field];
        });
        if (savedSuccessfully) delete this.state.unsavedEditors[key];
        return savedSuccessfully;
    }
    async flushEditors() {
        const saves = [...this.editorMeta.entries()].map(([key, meta]) =>
            this.saveRichText(key, meta.recordId, meta.model, meta.field)
        );
        const results = await Promise.all(saves);
        await Promise.all([...this.pendingWrites.values()]);
        return results.every((result) => result !== false) && !Object.values(this.state.unsavedEditors).some(Boolean);
    }
    attendees() {
        return this.state.attendees.map((partner) => partner.name).join(", ") || _t("No attendees listed");
    }
    toggleAttendeeEditor() {
        this.state.attendeeEditorOpen = !this.state.attendeeEditorOpen;
        this.state.attendeeIds = [...this.state.meeting.attendee_partner_ids];
        this.state.attendeeSearch = "";
        this.state.partnerResults = [];
    }
    async searchPartners(value) {
        this.state.attendeeSearch = value;
        const token = ++this.partnerSearchToken;
        if (!value.trim()) {
            this.state.partnerResults = [];
            return;
        }
        try {
            const results = await this.orm.searchRead("res.partner", [["name", "ilike", value]], ["name"], { order: "name", limit: 20 });
            if (token === this.partnerSearchToken) this.state.partnerResults = results;
        } catch (error) {
            if (token === this.partnerSearchToken) this.notification.add("Contacts could not be searched.", { type: "danger" });
        }
    }
    toggleAttendee(partnerId) {
        const ids = new Set(this.state.attendeeIds);
        if (ids.has(partnerId)) ids.delete(partnerId); else ids.add(partnerId);
        this.state.attendeeIds = [...ids];
    }
    async saveAttendees() {
        await this.write(`meeting:${this.meetingId}`, "community.meeting", [this.meetingId], {
            attendee_partner_ids: [[6, 0, this.state.attendeeIds]],
        }, async () => {
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], ["attendee_partner_ids"]);
            this.state.meeting.attendee_partner_ids = saved.attendee_partner_ids;
            this.state.attendees = saved.attendee_partner_ids.length
                ? await this.orm.searchRead("res.partner", [["id", "in", saved.attendee_partner_ids]], ["name"], { order: "name" })
                : [];
            this.state.attendeeEditorOpen = false;
        });
    }
    typeBehavior(item) { return this.state.types.find((type) => type.id === item.agenda_type_id?.[0])?.behavior || item.kind; }
    pointOutcome(item) {
        if (this.state.deferrals[item.id]) return "deferred";
        if (this.typeBehavior(item) === "decision") {
            return item.disposition === "deferred" ? "deferred" : item.decision_result === "pending" && item.disposition === "discussed" ? "discussed" : item.decision_result || "pending";
        }
        return item.disposition;
    }
    pointOutcomeLabel(item) {
        if (this.typeBehavior(item) === "information" && item.disposition === "discussed") return _t("Done");
        const entry = (OUTCOMES[this.typeBehavior(item)] || OUTCOMES.discussion).find(([value]) => value === this.pointOutcome(item));
        return entry?.[1] || _t("Pending");
    }
    outcomeBadgeClass(item) {
        const value = this.pointOutcome(item);
        return ["approved", "closed", "discussed"].includes(value) ? "text-bg-success"
            : value === "denied" ? "text-bg-danger"
                : value === "deferred" ? "text-bg-warning" : "text-bg-secondary";
    }
    async applyPointAction(item, value) {
        if (this.typeBehavior(item) === "decision" && ["approved", "denied"].includes(value)) {
            const agreement = this.decisionAgreement(item);
            if (agreement) return;
            this.state.newResolution[item.id] = { ...this.state.newResolution[item.id], decision_outcome: value };
            this.state.expanded[item.id] = true;
            requestAnimationFrame(() => document.getElementById(`agreement-title-${item.id}`)?.focus());
            return;
        }
        return this.updateOutcome(item, value);
    }
    async withdrawDecisionAgreement(item, resolution) {
        const saved = await this.updateResolution(resolution, "status", "withdrawn");
        if (saved) {
            this.notification.add(_t("The decision is pending again. Record a new agreement to resolve it."), { type: "info" });
        }
    }
    decisionAgreement(item) { return this.pointResolutions(item).find((row) => row.status === "active" && row.decision_outcome); }
    newDecisionOutcome(item) { return this.state.newResolution[item.id]?.decision_outcome ?? (this.decisionAgreement(item) ? "" : "approved"); }
    async refreshDecision(itemId) {
        const item = this.state.items.find((row) => row.id === itemId);
        if (!item) return;
        const [saved] = await this.orm.read("community.meeting.agenda.item", [itemId], ["disposition", "decision_result"]);
        Object.assign(item, saved);
    }
    pointDissents(item) {
        const resolutionIds = new Set(this.pointResolutions(item).map((row) => row.id));
        return this.state.dissents.filter((row) => row.agenda_item_id?.[0] === item.id || resolutionIds.has(row.resolution_id?.[0]));
    }
    pointResolutions(item) { return this.state.resolutions.filter((row) => row.agenda_item_id?.[0] === item.id); }
    pointPrivateNotes(item) { return this.state.privateNotes.filter((row) => row.agenda_item_id?.[0] === item.id); }
    pointActions(item) {
        const resolutionIds = new Set(this.pointResolutions(item).map((row) => row.id));
        return this.state.actions.filter((row) => row.agenda_item_id?.[0] === item.id || resolutionIds.has(row.resolution_id?.[0]));
    }
    get generalResolutions() { return this.state.resolutions.filter((row) => !row.agenda_item_id); }
    get generalDissents() {
        const resolutionIds = new Set(this.generalResolutions.map((row) => row.id));
        return this.state.dissents.filter((row) => !row.agenda_item_id && (!row.resolution_id || resolutionIds.has(row.resolution_id[0])));
    }
    get generalActions() { return this.state.actions.filter((row) => !row.agenda_item_id && !row.resolution_id); }
    get visibleItems() {
        return this.state.showPendingOnly
            ? this.state.items.filter((item) => item.disposition === "open" || (this.typeBehavior(item) === "decision" && item.decision_result === "pending"))
            : this.state.items;
    }
    get completedCount() { return this.state.items.filter((item) => ["discussed", "closed", "deferred"].includes(item.disposition)).length; }
    toggle(item) {
        this.state.activeItemId = item.id;
        this.state.expanded[item.id] = !this.state.expanded[item.id];
    }
    toggleTypeEditor(item) { this.state.editingTypes[item.id] = !this.state.editingTypes[item.id]; }
    toggleAll() {
        const expand = this.visibleItems.some((item) => !this.state.expanded[item.id]);
        for (const item of this.visibleItems) this.state.expanded[item.id] = expand;
    }
    togglePending() { this.state.showPendingOnly = !this.state.showPendingOnly; }
    navigateItem(offset) {
        const items = this.visibleItems;
        const index = items.findIndex((item) => item.id === this.state.activeItemId);
        const next = items[Math.max(0, Math.min(items.length - 1, index + offset))];
        if (!next) return;
        this.state.activeItemId = next.id;
        this.state.expanded[next.id] = true;
        document.getElementById(`agenda-card-${next.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    async write(key, model, ids, values, apply) {
        const writeKey = ids.length === 1 ? `${model}:${ids[0]}` : key;
        const previous = this.pendingWrites.get(writeKey) || Promise.resolve();
        this.state.saving++;
        const operation = previous.catch(() => {}).then(async () => {
            this.state.saveError = false;
            try {
                await this.orm.write(model, ids, values);
                await apply?.();
                return true;
            } catch (error) {
                this.state.saveError = true;
                this.notification.add("Could not save this change. Your text is still available; retry by editing the field again.", { type: "danger" });
                return false;
            } finally {
                this.state.saving--;
                if (this.pendingWrites.get(writeKey) === operation) this.pendingWrites.delete(writeKey);
            }
        });
        this.pendingWrites.set(writeKey, operation);
        return operation;
    }

    async updateItem(item, field, value) {
        const normalized = field === "agenda_type_id" ? Number(value) : value;
        return this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], { [field]: normalized }, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result"]);
            Object.assign(item, saved);
            this.state.editingTypes[item.id] = false;
        });
    }

    async updateOutcome(item, value) {
        if (this.typeBehavior(item) === "decision") {
            const agreement = this.decisionAgreement(item);
            if (["approved", "denied"].includes(value)) return this.applyPointAction(item, value);
        }
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
        const agreement = this.decisionAgreement(item);
        if (agreement && !(await this.updateResolution(agreement, "status", "withdrawn"))) return;
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
                if (saved.disposition === "deferred") delete this.state.deferrals[item.id];
            } });
        } catch (error) {
            this.notification.add("Could not open the carryover request.", { type: "danger" });
        }
    }

    async createRecord(key, model, values, onCreated) {
        if (this.state.submitting[key]) return;
        this.state.submitting[key] = true;
        this.state.saving++;
        this.state.saveError = false;
        try {
            const [id] = await this.orm.create(model, [values]);
            const fields = model === "community.meeting.dissent"
                ? ["agenda_item_id", "body", "kind", "author_display_name", "author_partner_id", "include_in_minutes"]
                : model === "community.meeting.editor.note"
                    ? ["agenda_item_id", "content"]
                : model === "community.meeting.resolution"
                    ? ["agenda_item_id", "title", "body", "status", "decision_outcome"]
                    : ["agenda_item_id", "resolution_id", "name", "description", "responsible_user_id", "deadline", "state"];
            const [record] = await this.orm.read(model, [id], fields);
            await onCreated(record);
        } catch (error) {
            this.state.saveError = true;
            this.notification.add("Could not save this record. Your entry is still available; retry when ready.", { type: "danger" });
        } finally {
            this.state.saving--;
            this.state.submitting[key] = false;
        }
    }

    async addDissent(item) {
        const form = this.state.newDissent[item.id] || {};
        const body = (form.body || "").trim();
        if (!body) return;
        await this.createRecord(`dissent:${item.id}`, "community.meeting.dissent", {
            meeting_id: this.meetingId, agenda_item_id: item.id, body,
            kind: form.kind || "dissent", author_display_name: form.author_display_name || false,
            include_in_minutes: form.include_in_minutes !== false,
        }, (record) => {
            this.state.dissents.push(record);
            this.state.newDissent[item.id] = "";
        });
    }
    async addGeneralDissent() {
        const form = this.state.newDissent.general || {};
        const body = (form.body || "").trim();
        if (!body) return;
        await this.createRecord("dissent:general", "community.meeting.dissent", {
            meeting_id: this.meetingId, body, kind: form.kind || "dissent",
            author_display_name: form.author_display_name || false,
            include_in_minutes: form.include_in_minutes !== false,
        }, (record) => {
            this.state.dissents.push(record);
            this.state.newDissent.general = {};
        });
    }

    async addAction(item) {
        const form = this.state.newAction[item.id] || {};
        if (!form.name?.trim()) return;
        const values = { meeting_id: this.meetingId, agenda_item_id: item.id, name: form.name.trim(), deadline: form.deadline || false, responsible_user_id: Number(form.responsible_user_id) || false };
        await this.createRecord(`action:${item.id}`, "community.meeting.action", values, (record) => {
            this.state.actions.push(record);
            this.state.newAction[item.id] = {};
        });
    }
    async addGeneralAction() {
        const form = this.state.newAction.general || {};
        if (!form.name?.trim()) return;
        await this.createRecord("action:general", "community.meeting.action", {
            meeting_id: this.meetingId, name: form.name.trim(), deadline: form.deadline || false,
            responsible_user_id: Number(form.responsible_user_id) || false,
        }, (record) => {
            this.state.actions.push(record);
            this.state.newAction.general = {};
        });
    }

    setDissent(item, key, value) {
        this.state.newDissent[item.id] ||= { include_in_minutes: true };
        this.state.newDissent[item.id][key] = value;
    }
    setAction(item, key, value) {
        this.state.newAction[item.id] ||= {};
        this.state.newAction[item.id][key] = value;
    }
    async updateAction(action, field, value) {
        const normalized = field === "responsible_user_id" ? (Number(value) || false) : (value || false);
        const values = field === "state" && normalized !== "done"
            ? { state: normalized, completed_on: false }
            : { [field]: normalized };
        await this.write(`action:${action.id}`, "community.meeting.action", [action.id], values, async () => {
            const [saved] = await this.orm.read("community.meeting.action", [action.id], field === "state" ? ["state", "completed_on"] : [field]);
            Object.assign(action, saved);
        });
    }
    async addResolution(item) {
        const form = this.state.newResolution[item.id] || {};
        if (!form.title?.trim()) return;
        await this.createRecord(`resolution:${item.id}`, "community.meeting.resolution", {
            meeting_id: this.meetingId, agenda_item_id: item.id, title: form.title.trim(), body: form.body || false,
            decision_outcome: this.typeBehavior(item) === "decision" ? (this.newDecisionOutcome(item) || false) : false,
        }, async (record) => {
            this.state.resolutions.push(record);
            this.state.newResolution[item.id] = {};
            await this.refreshDecision(item.id);
        });
    }
    async addGeneralResolution() {
        const form = this.state.newResolution.general || {};
        if (!form.title?.trim()) return;
        await this.createRecord("resolution:general", "community.meeting.resolution", {
            meeting_id: this.meetingId, title: form.title.trim(), body: form.body || false,
        }, (record) => {
            this.state.resolutions.push(record);
            this.state.newResolution.general = {};
        });
    }
    async addPrivateNote(item) {
        const content = (this.state.newPrivateNote[item.id] || "").trim();
        if (!content) return;
        await this.createRecord(`private-note:${item.id}`, "community.meeting.editor.note", {
            meeting_id: this.meetingId, agenda_item_id: item.id, content,
        }, (record) => {
            this.state.privateNotes.push(record);
            this.state.newPrivateNote[item.id] = "";
        });
    }
    setPrivateNote(item, value) { this.state.newPrivateNote[item.id] = value; }
    setGeneralValue(collection, field, value) {
        this.state[collection].general ||= {};
        this.state[collection].general[field] = value;
    }
    setResolution(item, key, value) {
        this.state.newResolution[item.id] ||= {};
        this.state.newResolution[item.id][key] = value;
    }
    async updateResolution(resolution, field, value) {
        return this.write(`resolution:${resolution.id}`, "community.meeting.resolution", [resolution.id], { [field]: value }, async () => {
            resolution[field] = value;
            if (resolution.agenda_item_id) await this.refreshDecision(resolution.agenda_item_id[0]);
        });
    }
    toggleRecordEditor(key) { this.state.editingRecords[key] = !this.state.editingRecords[key]; }
    async updateDissent(dissent, field, value) {
        await this.write(`dissent:${dissent.id}`, "community.meeting.dissent", [dissent.id], { [field]: value }, () => { dissent[field] = value; });
    }
    async requestRecordCarryover(model, record) {
        try {
            const action = await this.orm.call(model, "action_request_followup", [[record.id]]);
            await this.actionService.doAction(action);
        } catch (error) {
            this.notification.add("Could not open the carryover request.", { type: "danger" });
        }
    }
    async transition(method, state) {
        const key = `meeting:${this.meetingId}`;
        if (this.state.submitting[key]) return;
        this.state.submitting[key] = true;
        try {
            await this.orm.call("community.meeting", method, [[this.meetingId]]);
            this.state.meeting.state = state;
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], ["actual_start_datetime", "actual_end_datetime"]);
            Object.assign(this.state.meeting, saved);
        } catch (error) {
            this.notification.add("The meeting status could not be changed. Please retry.", { type: "danger" });
        } finally {
            this.state.submitting[key] = false;
        }
    }
    markHeld() { return this.transition("action_mark_held", "held"); }
    async startMeeting() {
        const key = `meeting:${this.meetingId}`;
        if (this.state.submitting[key]) return;
        this.state.submitting[key] = true;
        try {
            await this.orm.call("community.meeting", "action_start_meeting", [[this.meetingId]]);
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], ["actual_start_datetime"]);
            Object.assign(this.state.meeting, saved);
        } catch (error) {
            this.notification.add("The meeting could not be started. Please retry.", { type: "danger" });
        } finally {
            this.state.submitting[key] = false;
        }
    }
    prepareMinutes() { return this.transition("action_draft_minutes", "minutes_draft"); }
    async close() {
        if (!await this.flushEditors()) {
            this.notification.add("Save the pending edits before leaving this meeting.", { type: "warning" });
            return;
        }
        if (this.props.close) return this.props.close();
        return this.actionService.doAction({ type: "ir.actions.act_window", res_model: "community.meeting", views: [[false, "list"], [false, "form"]], target: "current" });
    }
}

registry.category("actions").add("community_meetings.live_meeting", LiveMeeting);
