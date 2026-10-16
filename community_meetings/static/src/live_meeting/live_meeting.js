/** @odoo-module **/

import { Component, markup, onMounted, onPatched, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime, serializeDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { ensureJQuery } from "@web/core/ensure_jquery";
import { useService } from "@web/core/utils/hooks";

const { DateTime } = luxon;

const OUTCOMES = {
    information: [["open", _t("Pending")], ["discussed", _t("Discussed")], ["deferred", _t("Postponed")]],
    discussion: [["open", _t("Pending")], ["discussed", _t("Discussed")], ["closed", _t("Resolved")], ["deferred", _t("Postponed")]],
    decision: [["pending", _t("Pending")], ["discussed", _t("Discussed — decision pending")], ["approved", _t("Approved")], ["denied", _t("Rejected")], ["deferred", _t("Postponed")]],
    todo: [["open", _t("Task required")], ["closed", _t("Resolved")], ["deferred", _t("Postponed")]],
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
        onPatched(() => {
            for (const item of this.state.items) {
                const editor = this.editors.get(`discussion_notes:${item.id}`)?.$editable?.[0];
                if (editor) {
                    const editable = this.canEditDiscussion(item);
                    editor.setAttribute("contenteditable", String(editable));
                    editor.setAttribute("aria-readonly", String(!editable));
                }
            }
        });
        this.canApproveMinutes = false;
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, saving: 0, saveError: false, saveErrorDetail: "", unsavedEditors: {}, submitting: {}, editingRecords: {}, editingTypes: {}, headerDraft: {}, attendeeEditorOpen: false, attendeeIds: [], attendeeSearch: "", partnerResults: [], deferrals: {}, reopening: {}, meeting: {}, items: [], types: [], dissents: [], actions: [], resolutions: [], privateNotes: [], users: [], activityTypes: [], followupDefaults: { kind: "task", activity_type_id: false, todo_activity_type_id: false }, expanded: {}, activeItemId: false, showPendingOnly: false, newDissent: {}, newAction: {}, newResolution: {}, newPrivateNote: {}, panels: {}, attendees: [], incoming: [], pendingMinutes: [], defaultOwner: false });
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

    get meetingId() {
        const action = this.props.action || {};
        const routeIds = [...window.location.pathname.matchAll(/(?:^|\/)community\.meeting\/(\d+)(?=\/|$)/g)];
        return action.params?.meeting_id || action.context?.active_id || action.context?.params?.id
            || Number(routeIds.at(-1)?.[1]) || false;
    }
    get locked() { return !this.state.capabilities?.can_edit || ["approved", "cancelled"].includes(this.state.meeting.state); }
    get meetingPaused() { return Boolean(this.state.meeting.actual_paused_at); }
    get readOnly() { return this.locked || this.meetingPaused; }
    get draftingMinutes() { return ["held", "minutes_draft"].includes(this.state.meeting.state); }
    get hasUnsavedEditors() { return Object.values(this.state.unsavedEditors).some(Boolean); }

    async load() {
        if (!this.meetingId) {
            this.state.loading = false;
            this.notification.add(_t("Could not identify the meeting to open. Return to the Meetings list and open it again."), { type: "danger" });
            return;
        }
        this.state.capabilities = await this.orm.call("community.meeting", "get_live_capabilities", [[this.meetingId]]);
        this.canApproveMinutes = this.state.capabilities.can_approve;
        const editorial = this.state.capabilities.can_view_editorial;
        const [meetings, items, types, dissents, actions, resolutions, privateNotes] = await Promise.all([
            this.orm.read("community.meeting", [this.meetingId], ["name", "code", "state", "company_id", "start_datetime", "end_datetime", "actual_start_datetime", "actual_paused_at", "actual_paused_seconds", "actual_end_datetime", "actual_duration_minutes", "organizer_id", "secretary_id", "location", "meeting_url", "attendee_partner_ids", "minutes_notes", "series_id", "duration_minutes"]),
            this.orm.searchRead("community.meeting.agenda.item", [["meeting_id", "=", this.meetingId]], ["name", "topic_id", "sequence", "agenda_type_id", "kind", "disposition", "decision_result", "description", "discussion_notes", "deferral_reason", "deferral_reason_code", "deferral_blocked_by", "presenter_partner_id", "priority", "deadline", "estimated_minutes", "actual_minutes", "actual_seconds", "actual_started_at", "has_started", "review_next_meeting", "is_followup", "topic_state", "topic_outcome", "next_meeting_datetime"], { order: "sequence, id" }),
            this.orm.searchRead("community.meeting.agenda.type", [], ["name", "behavior", "active"], { order: "sequence, name", context: { active_test: false } }),
            editorial ? this.orm.searchRead("community.meeting.dissent", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "body", "kind", "author_display_name", "author_partner_id"], { order: "sequence, id" }) : this.orm.call("community.meeting", "get_live_published_dissents", [[this.meetingId]]),
            this.orm.searchRead("community.meeting.action", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "name", "description", "responsible_user_id", "deadline", "state"], { order: "deadline, id" }),
            this.orm.searchRead("community.meeting.resolution", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "title", "body", "status", "decision_outcome"], { order: "id" }),
            editorial ? this.orm.searchRead("community.meeting.editor.note", [["meeting_id", "=", this.meetingId]], ["agenda_item_id", "content"], { order: "id" }) : Promise.resolve([]),
        ]);
        this.state.meeting = meetings[0];
        this.state.followupDefaults = await this.orm.call("community.meeting", "get_followup_defaults", [[this.meetingId]]);
        this.state.activityTypes = await this.orm.searchRead("mail.activity.type", [["active", "=", true]], ["name"], { order: "sequence, name" });
        this.state.attendeeIds = [...meetings[0].attendee_partner_ids];
        const users = await this.orm.searchRead("res.users", [
            ["active", "=", true], ["share", "=", false], ["company_ids", "in", [meetings[0].company_id[0]]],
        ], ["name"], { order: "name", limit: 200 });
        this.state.attendees = meetings[0].attendee_partner_ids.length
            ? await this.orm.searchRead("res.partner", [["id", "in", meetings[0].attendee_partner_ids]], ["name"], { order: "name" })
            : [];
        this.state.items = items;
        this.state.followupByItem = Object.fromEntries(await Promise.all(items.map(async (item) => [item.id,
            await this.orm.call("community.meeting", "get_followup_defaults", [[this.meetingId], item.id])])));
        this.state.types = types;
        this.state.dissents = dissents;
        this.state.defaultOwner = (await this.orm.call("community.meeting.action", "default_get", [["responsible_user_id"]])).responsible_user_id;
        const topicIds = items.map((i) => i.topic_id?.[0]).filter(Boolean);
        this.state.actions = await this.orm.searchRead("community.meeting.action", [["topic_id", "in", topicIds]], ["agenda_item_id", "topic_id", "name", "description", "responsible_user_id", "responsible_user_ids", "deadline", "state", "followup_kind", "followup_activity_type_id", "followup_activity_id", "followup_activity_completed_on"], { order: "deadline, id" });
        this.state.incoming = this.state.capabilities.can_edit ? await this.orm.searchRead("community.meeting.carryover", [["destination_meeting_id", "=", this.meetingId], ["status", "in", ["pending", "proposed"]]], ["origin_name", "origin_meeting_id", "reason"]) : [];
        this.state.pendingMinutes = await this.orm.call("community.meeting", "get_pending_minutes_for_approval", [[this.meetingId]]);
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
    followupKindLabel(action) {
        return {
            activity: _t("Odoo activity"),
            todo: _t("Odoo To-do"),
        }[action.followup_kind] || _t("Follow-up");
    }
    followupDefaults(item) { return this.state.followupByItem?.[item.id] || this.state.followupDefaults; }
    followupChoices(item) { return (this.followupDefaults(item).allowed_kinds || []).map(kind => ({ kind, label: this.followupKindLabel({followup_kind: kind}) })); }
    actionActivityType(action) {
        return this.state.activityTypes.find(
            (type) => type.id === action.followup_activity_type_id?.[0]
        )?.name || "";
    }
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
        if (model === "community.meeting.agenda.item" && field === "discussion_notes") {
            // Discussion notes are the minutes content. During the live meeting
            // (scheduled) they are editable only while the point timer is
            // running. Once the meeting is held or in minutes_draft the timer is
            // gone, but the minutes must stay editable until approval.
            const item = this.state.items.find((row) => row.id === recordId);
            const state = this.state.meeting.state;
            const editable = !this.locked && (
                state !== "scheduled"
                || (Boolean(item?.actual_started_at) && !this.meetingPaused)
            );
            wysiwyg.$editable[0].setAttribute("contenteditable", editable ? "true" : "false");
            wysiwyg.$editable[0].setAttribute("aria-readonly", editable ? "false" : "true");
        }
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
        // Notes are readonly outside a treated point; never save them then.
        if (model === "community.meeting.agenda.item" && field === "discussion_notes" && !this.canEditDiscussion(record)) {
            delete this.state.unsavedEditors[key];
            return true;
        }
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
        if (this.locked) return true;
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
    canEditDiscussion(item) {
        return !this.locked && (this.draftingMinutes || (!this.meetingPaused && Boolean(item.actual_started_at)));
    }
    async saveHeaderField(field, value) {
        if (this.locked) return;
        value = field === "secretary_id" ? (Number(value) || false) : value.trim();
        if (field === "name" && !value) return;
        await this.write(`meeting:${this.meetingId}`, "community.meeting", [this.meetingId], {
            [field]: value || false,
        }, async () => {
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], [field]);
            Object.assign(this.state.meeting, saved);
            if (this.state.headerDraft[field]?.trim() === value) delete this.state.headerDraft[field];
        });
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
        if (this.typeBehavior(item) === "todo") return item.disposition;
        if (this.typeBehavior(item) === "decision") {
            const agreement = this.decisionAgreement(item);
            if (agreement) return agreement.decision_outcome;
            return item.disposition === "deferred" ? "deferred" : item.decision_result === "pending" && item.disposition === "discussed" ? "discussed" : item.decision_result || "pending";
        }
        return item.disposition;
    }
    pointOutcomeLabel(item) {
        if (this.typeBehavior(item) === "todo" && item.disposition === "open" && this.hasTodoAction(item)) return _t("Task assigned");
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
        if (this.typeBehavior(item) === "todo" && value === "closed" && !this.hasTodoAction(item)) {
            this.notification.add(_t("Add a follow-up task before resolving this TODO."), { type: "warning" });
            return;
        }
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
        const [saved] = await this.orm.read("community.meeting.agenda.item", [itemId], ["disposition", "decision_result", "topic_state", "topic_outcome", "is_followup"]);
        Object.assign(item, saved);
        const resolutions = await this.orm.searchRead("community.meeting.resolution", [["agenda_item_id", "=", itemId]], ["agenda_item_id", "title", "body", "status", "decision_outcome"], { order: "id" });
        const refreshed = new Map(resolutions.map((row) => [row.id, row]));
        this.state.resolutions = this.state.resolutions
            .filter((row) => row.agenda_item_id?.[0] !== itemId || refreshed.has(row.id))
            .map((row) => refreshed.get(row.id) || row);
        for (const row of resolutions) {
            if (!this.state.resolutions.some((existing) => existing.id === row.id)) this.state.resolutions.push(row);
        }
    }
    pointDissents(item) {
        const resolutionIds = new Set(this.pointResolutions(item).map((row) => row.id));
        return this.state.dissents.filter((row) => row.topic_id?.[0] === item.topic_id?.[0] || row.agenda_item_id?.[0] === item.id || resolutionIds.has(row.resolution_id?.[0]));
    }
    pointResolutions(item) { return this.state.resolutions.filter((row) => row.agenda_item_id?.[0] === item.id); }
    pointPrivateNotes(item) { return this.state.privateNotes.filter((row) => row.agenda_item_id?.[0] === item.id); }
    pointActions(item) {
        const resolutionIds = new Set(this.pointResolutions(item).map((row) => row.id));
        return this.state.actions.filter((row) => row.topic_id?.[0] === item.topic_id?.[0] || row.agenda_item_id?.[0] === item.id || resolutionIds.has(row.resolution_id?.[0]));
    }
    actionHasExecutionEvidence(action) { return Boolean(action.followup_activity_id || action.followup_activity_completed_on); }
    hasTodoAction(item) { return this.pointActions(item).some((action) => action.state !== "cancelled" && action.responsible_user_id && this.actionHasExecutionEvidence(action)); }
    get visibleItems() {
        return this.state.showPendingOnly
            ? this.state.items.filter((item) => !["closed", "discussed"].includes(item.disposition) || (this.typeBehavior(item) === "decision" && item.decision_result === "pending"))
            : this.state.items;
    }
    get completedCount() { return this.state.items.filter((item) => ["discussed", "closed"].includes(item.disposition)).length; }
    canStartPoint(item) {
        return item.disposition !== "closed"
            && !(this.typeBehavior(item) === "information" && item.disposition === "discussed");
    }
    canCompletePoint(item) {
        if (item.is_followup) return true;
        const behavior = this.typeBehavior(item);
        if (behavior === "information") return item.disposition !== "discussed";
        if (behavior === "decision") return Boolean(this.decisionAgreement(item));
        if (behavior === "todo") return item.disposition !== "closed" && this.hasTodoAction(item);
        return item.disposition !== "closed";
    }
    async completePoint(item) {
        if (!this.canCompletePoint(item)) return;
        if (item.is_followup) return this.applyPointAction(item, "discussed");
        const behavior = this.typeBehavior(item);
        const outcome = behavior === "information" ? "discussed"
            : behavior === "decision" ? this.decisionAgreement(item).decision_outcome
                : behavior === "todo" ? "closed" : "closed";
        return this.applyPointAction(item, outcome);
    }
    togglePanel(item, name) {
        this.state.panels[item.id] ||= {};
        this.state.panels[item.id][name] = !this.state.panels[item.id][name];
    }
    async deleteFollowup(item, action) {
        if (item.topic_state !== "open" || action.agenda_item_id?.[0] !== item.id) return;
        try {
            await this.orm.unlink("community.meeting.action", [action.id]);
            this.state.actions = this.state.actions.filter((row) => row.id !== action.id);
        } catch (error) {
            this.notification.add(_t("This follow-up could not be deleted."), { type: "danger" });
        }
    }
    setPointEditorsEditable(item, editable) {
        document.querySelectorAll(`#agenda-card-${item.id} [contenteditable]`).forEach((editor) => {
            editor.setAttribute("contenteditable", editable ? "true" : "false");
            editor.setAttribute("aria-readonly", editable ? "false" : "true");
        });
    }
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
    async navigateItem(offset) {
        const items = this.visibleItems;
        const index = items.findIndex((item) => item.id === this.state.activeItemId);
        const next = items[Math.max(0, Math.min(items.length - 1, index + offset))];
        if (!next || next.id === this.state.activeItemId) return;
        if (!await this.flushEditors()) return;
        const running = this.state.items.filter((item) => item.actual_started_at);
        for (const item of running) {
            await this.orm.call("community.meeting.agenda.item", "action_pause_timing", [[item.id]]);
        }
        if (running.length) {
            await this.refreshPointTiming();
            for (const item of running) this.setPointEditorsEditable(item, false);
        }
        for (const item of this.state.items) this.state.expanded[item.id] = false;
        this.state.activeItemId = next.id;
        this.state.expanded[next.id] = true;
        document.getElementById(`agenda-card-${next.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    async refreshPointTiming() {
        const records = await this.orm.read("community.meeting.agenda.item", this.state.items.map((item) => item.id), ["actual_minutes", "actual_seconds", "actual_started_at", "has_started", "review_next_meeting"]);
        const byId = new Map(records.map((record) => [record.id, record]));
        for (const item of this.state.items) Object.assign(item, byId.get(item.id) || {});
    }

    async startPoint(item) {
        if (!await this.flushEditors()) return;
        try {
            await this.orm.call("community.meeting.agenda.item", "action_start_timing", [[item.id]]);
            await this.refreshPointTiming();
            this.setPointEditorsEditable(item, true);
            for (const point of this.state.items) this.state.expanded[point.id] = false;
            this.state.activeItemId = item.id;
            this.state.expanded[item.id] = true;
        } catch (error) {
            this.notification.add(_t("The point timer could not be started."), { type: "danger" });
        }
    }

    async pausePoint(item) {
        try {
            if (!await this.flushEditors()) return;
            await this.orm.call("community.meeting.agenda.item", "action_pause_timing", [[item.id]]);
            await this.refreshPointTiming();
            this.setPointEditorsEditable(item, false);
        } catch (error) {
            this.notification.add(_t("The point timer could not be paused."), { type: "danger" });
        }
    }

    async write(key, model, ids, values, apply) {
        const writeKey = ids.length === 1 ? `${model}:${ids[0]}` : key;
        const previous = this.pendingWrites.get(writeKey) || Promise.resolve();
        this.state.saving++;
        const operation = previous.catch(() => {}).then(async () => {
            this.state.saveError = false;
            this.state.saveErrorDetail = "";
            try {
                await this.orm.write(model, ids, values);
                await apply?.();
                return true;
            } catch (error) {
                this.state.saveError = true;
                const serverMessage = error?.data?.message || error?.message || "";
                this.state.saveErrorDetail = serverMessage || `#${ids.join(", ")}`;
                console.error("Live meeting write failed", { model, ids, values, error });
                this.notification.add(
                    serverMessage
                        ? _t("Could not save this change: %(message)s", { message: serverMessage })
                        : _t("Could not save this change. Your text is still available; retry by editing the field again."),
                    { type: "danger" },
                );
                return false;
            } finally {
                this.state.saving--;
                if (this.pendingWrites.get(writeKey) === operation) this.pendingWrites.delete(writeKey);
            }
        });
        this.pendingWrites.set(writeKey, operation);
        return operation;
    }

    async toggleReview(item, checked) {
        const key = `review:${item.id}`;
        if (this.state.submitting[key]) return;
        this.state.submitting[key] = true;
        const previous = item.review_next_meeting;
        item.review_next_meeting = checked;
        try {
            if (!await this.updateItem(item, "review_next_meeting", checked)) {
                item.review_next_meeting = previous;
            }
        } finally {
            this.state.submitting[key] = false;
        }
    }

    async updateItem(item, field, value) {
        const normalized = field === "agenda_type_id" ? Number(value) : value;
        return this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], { [field]: normalized }, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result", "review_next_meeting", "actual_minutes", "actual_seconds", "actual_started_at", "has_started"]);
            Object.assign(item, saved);
            if (!item.actual_started_at) this.setPointEditorsEditable(item, false);
            this.state.editingTypes[item.id] = false;
        });
    }

    async setNextMeetingDate(item, value) {
        const zone = this.state.capabilities.timezone;
        const local = value ? DateTime.fromISO(value, { zone }) : null;
        if (local && (!local.isValid || local.toFormat("yyyy-MM-dd'T'HH:mm") !== value || local.getPossibleOffsets().length > 1)) {
            this.notification.add(_t("Choose an unambiguous date and time in the meeting timezone."), { type: "warning" });
            return;
        }
        return this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], { next_meeting_datetime: local ? serializeDateTime(local) : false }, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["next_meeting_datetime"]);
            item.next_meeting_datetime = saved.next_meeting_datetime;
        });
    }
    nextMeetingLocalValue(item) {
        return item.next_meeting_datetime ? deserializeDateTime(item.next_meeting_datetime).setZone(this.state.capabilities.timezone).toFormat("yyyy-MM-dd'T'HH:mm") : "";
    }

    async openMeeting(id) {
        if (!await this.flushEditors()) return;
        const action = await this.orm.call("community.meeting", "action_open_live_meeting", [[id]]);
        return this.actionService.doAction(action);
    }
    async approveMinutes() {
        if (!await this.flushEditors()) return;
        await this.transition("action_approve_minutes", "approved");
    }

    async updateOutcome(item, value) {
        if (this.typeBehavior(item) === "decision") {
            const agreement = this.decisionAgreement(item);
            if (["approved", "denied"].includes(value)) return this.applyPointAction(item, value);
        }
        if (value === "deferred") {
            this.state.deferrals[item.id] = { reason: item.deferral_reason || "", code: item.deferral_reason_code || "", blocked_by: item.deferral_blocked_by || "" };
            this.state.expanded[item.id] = true;
            return;
        }
        if (!await this.flushEditors()) return;
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
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result", "actual_started_at", "actual_minutes", "actual_seconds"]);
            Object.assign(item, saved);
            if (!item.actual_started_at) this.setPointEditorsEditable(item, false);
        });
    }

    setDeferralReason(item, value) {
        this.state.deferrals[item.id] ||= { reason: item.deferral_reason || "", code: item.deferral_reason_code || "", blocked_by: item.deferral_blocked_by || "" };
        this.state.deferrals[item.id].reason = value;
    }

    setDeferralCode(item, value) {
        this.state.deferrals[item.id] ||= { reason: item.deferral_reason || "", code: item.deferral_reason_code || "", blocked_by: item.deferral_blocked_by || "" };
        this.state.deferrals[item.id].code = value;
        if (!this.isBlockedReason(value)) this.state.deferrals[item.id].blocked_by = "";
    }

    setDeferralBlockedBy(item, value) {
        this.state.deferrals[item.id] ||= { reason: item.deferral_reason || "", code: item.deferral_reason_code || "", blocked_by: item.deferral_blocked_by || "" };
        this.state.deferrals[item.id].blocked_by = value;
    }

    isBlockedReason(code) {
        return ["blocked_point", "blocked_task", "blocked_activity", "blocked_todo"].includes(code);
    }

    get deferralReasonChoices() {
        return [
            ["blocked_point", _t("Blocked by another point"), "fa-dot-circle-o"],
            ["blocked_task", _t("Blocked by a task"), "fa-tasks"],
            ["blocked_activity", _t("Blocked by an activity"), "fa-bell-o"],
            ["blocked_todo", _t("Blocked by a To-do"), "fa-check-square-o"],
            ["no_time", _t("Lack of time"), "fa-clock-o"],
            ["other", _t("Other reason"), "fa-ellipsis-h"],
        ];
    }

    deferralBlockedOptions(item) {
        const options = [];
        for (const point of this.state.items) {
            if (point.id !== item.id && point.topic_id) {
                options.push({ value: `community.meeting.topic,${point.topic_id[0]}`, label: point.name });
            }
        }
        for (const action of this.pointActions(item)) {
            if (action.state !== "cancelled") {
                options.push({ value: `community.meeting.action,${action.id}`, label: action.name });
            }
        }
        return options;
    }

    cancelDeferral(item) { delete this.state.deferrals[item.id]; }

    async saveDeferral(item) {
        const draft = this.state.deferrals[item.id] || {};
        const reason = (draft.reason || "").trim();
        const code = draft.code || "";
        if (!code && !reason) {
            this.notification.add(_t("Choose a reason before postponing this point."), { type: "warning" });
            return;
        }
        if (code === "other" && !reason) {
            this.notification.add(_t("Describe the reason before postponing this point."), { type: "warning" });
            return;
        }
        const agreement = this.decisionAgreement(item);
        if (agreement && !(await this.updateResolution(agreement, "status", "withdrawn"))) return;
        await this.write(`item:${item.id}`, "community.meeting.agenda.item", [item.id], {
            disposition: "deferred", deferral_reason: reason, deferral_reason_code: code || false,
            deferral_blocked_by: this.isBlockedReason(code) ? (draft.blocked_by || false) : false,
            review_next_meeting: true,
            ...(this.typeBehavior(item) === "decision" ? { decision_result: "pending" } : {}),
        }, async () => {
            const [saved] = await this.orm.read("community.meeting.agenda.item", [item.id], ["agenda_type_id", "kind", "disposition", "decision_result", "deferral_reason", "deferral_reason_code", "deferral_blocked_by", "review_next_meeting", "actual_started_at", "actual_minutes", "actual_seconds"]);
            Object.assign(item, saved);
            if (!item.actual_started_at) this.setPointEditorsEditable(item, false);
            delete this.state.deferrals[item.id];
        });
    }

    deferralReasonLabel(code) {
        const entry = this.deferralReasonChoices.find(([value]) => value === code);
        return entry ? entry[1] : "";
    }

    async requestCarryover(item) {
        const draft = this.state.deferrals[item.id] || {};
        const reason = (draft.reason || "").trim() || this.deferralReasonLabel(draft.code);
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
    async addAction(item) {
        const form = this.state.newAction[item.id] || {};
        if (!form.name?.trim()) return;
        const defaults = this.followupDefaults(item);
        const followupKind = form.followup_kind || defaults.kind;
        const activityType = Number(form.followup_activity_type_id || defaults.activity_type_id) || false;
        if (followupKind === "activity" && !activityType) {
            this.notification.add(_t("Choose an Odoo activity type."), { type: "warning" });
            return;
        }
        const values = { meeting_id: this.meetingId, agenda_item_id: item.id, name: form.name.trim(), deadline: form.deadline || false, responsible_user_id: form.responsible_user_id === undefined ? this.state.defaultOwner : (Number(form.responsible_user_id) || false), followup_kind: followupKind, followup_activity_type_id: followupKind === "todo" ? this.state.followupDefaults.todo_activity_type_id : activityType };
        if (form.responsible_user_ids) values.responsible_user_ids = [[6, 0, form.responsible_user_ids]];
        await this.createRecord(`action:${item.id}`, "community.meeting.action", values, async (record) => {
            const [saved] = await this.orm.read("community.meeting.action", [record.id], ["topic_id", "followup_activity_id", "followup_activity_completed_on", "responsible_user_id", "responsible_user_ids", "followup_kind", "followup_activity_type_id"]);
            this.state.actions.push({ ...record, ...saved });
            this.state.newAction[item.id] = {};
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
    selectedUserIds(event) { return Array.from(event.target.selectedOptions, option => Number(option.value)); }
    async updateAction(action, field, value) {
        const normalized = field === "responsible_user_id" ? (Number(value) || false) : (value || false);
        if (field === "responsible_user_id" && action.responsible_user_ids?.length > 1) {
            const owners = action.responsible_user_ids.filter(id => id !== action.responsible_user_id?.[0]);
            if (normalized) owners.push(normalized);
            return this.updateActionOwners(action, [...new Set(owners)]);
        }
        const values = field === "state" && normalized !== "done"
            ? { state: normalized, completed_on: false }
            : { [field]: normalized };
        await this.write(`action:${action.id}`, "community.meeting.action", [action.id], values, async () => {
            const [saved] = await this.orm.read("community.meeting.action", [action.id], field === "state" ? ["state", "completed_on"] : [field]);
            Object.assign(action, saved);
        });
    }
    async updateActionOwners(action, owners) {
        return this.write(`action:${action.id}`, "community.meeting.action", [action.id], { responsible_user_ids: [[6, 0, owners]] }, async () => {
            const [saved] = await this.orm.read("community.meeting.action", [action.id], ["responsible_user_id", "responsible_user_ids"]);
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
    setResolution(item, key, value) {
        this.state.newResolution[item.id] ||= {};
        this.state.newResolution[item.id][key] = value;
    }
    async updateResolution(resolution, field, value) {
        return this.write(`resolution:${resolution.id}`, "community.meeting.resolution", [resolution.id], { [field]: value }, async () => {
            if (resolution.agenda_item_id) {
                await this.refreshDecision(resolution.agenda_item_id[0]);
            } else {
                const [saved] = await this.orm.read("community.meeting.resolution", [resolution.id], ["title", "body", "status", "decision_outcome"]);
                Object.assign(resolution, saved);
            }
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
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], ["actual_start_datetime", "actual_end_datetime", "actual_duration_minutes"]);
            Object.assign(this.state.meeting, saved);
            if (state === "held") {
                await this.refreshPointTiming();
                for (const item of this.state.items) this.setPointEditorsEditable(item, false);
            }
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
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], ["actual_start_datetime", "actual_paused_at", "actual_paused_seconds", "actual_duration_minutes"]);
            Object.assign(this.state.meeting, saved);
        } catch (error) {
            this.notification.add("The meeting could not be started. Please retry.", { type: "danger" });
        } finally {
            this.state.submitting[key] = false;
        }
    }
    async setMeetingPaused(paused) {
        const key = `meeting:${this.meetingId}`;
        if (this.state.submitting[key] || !await this.flushEditors()) return;
        this.state.submitting[key] = true;
        try {
            await this.orm.call("community.meeting", paused ? "action_pause_meeting" : "action_resume_meeting", [[this.meetingId]]);
            const [saved] = await this.orm.read("community.meeting", [this.meetingId], ["actual_paused_at", "actual_paused_seconds", "actual_duration_minutes"]);
            Object.assign(this.state.meeting, saved);
            await this.refreshPointTiming();
            if (paused) for (const item of this.state.items) this.setPointEditorsEditable(item, false);
        } catch (error) {
            this.notification.add(paused ? _t("The meeting could not be paused.") : _t("The meeting could not be resumed."), { type: "danger" });
        } finally {
            this.state.submitting[key] = false;
        }
    }
    pauseMeeting() { return this.setMeetingPaused(true); }
    resumeMeeting() { return this.setMeetingPaused(false); }
    prepareMinutes() { return this.transition("action_draft_minutes", "minutes_draft"); }
    durationLabel(minutes) { return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`; }
    async editPoint(item) {
        if (!await this.flushEditors()) return;
        const action = await this.orm.call('community.meeting.agenda.item', 'action_edit_point', [[item.id]]);
        return this.actionService.doAction(action);
    }
    priorityLabel(item) { return { "0": _t("Low"), "1": _t("Normal"), "2": _t("High"), "3": _t("Critical") }[item.priority]; }
    async addPoint() {
        if (!await this.flushEditors()) return;
        const action = await this.orm.call("community.meeting", "action_add_point_live", [[this.meetingId]]);
        await this.actionService.doAction(action, { onClose: () => this.load() });
    }
    async reviewCarryover(transfer, accept) {
        if (!await this.flushEditors()) return;
        try {
            await this.orm.call("community.meeting.carryover", accept ? "action_accept" : "action_dismiss", [[transfer.id]]);
            await this.load();
        } catch (error) { this.notification.add(_t("Could not review this continuing point."), { type: "danger" }); }
    }
    async reopenPoint(item) {
        const reason = (this.state.reopening[item.id] || "").trim();
        if (!await this.flushEditors()) return;
        const key = `reopen:${item.id}`;
        this.state.submitting[key] = true;
        try {
            await this.orm.write("community.meeting.agenda.item", [item.id], { reopen_reason: reason });
            await this.orm.call("community.meeting.agenda.item", "action_reopen", [[item.id]]);
            delete this.state.reopening[item.id];
            await this.load();
        } catch (error) {
            this.notification.add(_t("The point could not be reopened. Retry after checking its current status."), { type: "danger" });
        } finally {
            this.state.submitting[key] = false;
        }
    }
    setReopenReason(item, value) { this.state.reopening[item.id] = value; }
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
