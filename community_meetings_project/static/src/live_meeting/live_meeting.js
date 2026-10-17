/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { LiveMeeting } from "@community_meetings/live_meeting/live_meeting";

patch(LiveMeeting.prototype, {
    followupKindLabel(action) {
        return {
            project_task: _t("Project task"),
            project_todo: _t("To-do"),
        }[action.followup_kind] || super.followupKindLabel(action);
    },
    actionHasExecutionEvidence(action) {
        return ["project_task", "project_todo"].includes(action.followup_kind) ? (this.state.projectTasksByAction?.[action.id] || []).some(task => task.valid) : super.actionHasExecutionEvidence(action);
    },
    async load(...args) {
        await super.load(...args);
        const requirements = await this.orm.read('community.meeting.agenda.item', this.state.items.map(i => i.id), ['requires_project_task']);
        const byId = Object.fromEntries(requirements.map(i => [i.id, i.requires_project_task]));
        for (const item of this.state.items) item.requires_project_task = byId[item.id];
        await this.refreshProjectTaskLinks();
    },

    async refreshProjectTaskLinks() {
        this.state.projectTasksByAction = {};
        const actions = await this.orm.searchRead(
            "community.meeting.action",
            [["id", "in", this.state.actions.map(a => a.id)]],
            ["project_task_ids"]
        );
        const taskIds = [...new Set(actions.flatMap((action) => action.project_task_ids))];
        if (!taskIds.length) return;
        const tasks = await this.orm.searchRead("project.task", [["id", "in", taskIds]], ["display_name", "user_ids", "state", "active"]);
        const validTasks = new Set(tasks.filter(t => t.active && t.state !== "1_canceled" && t.user_ids.length).map(t => t.id));
        const taskNames = Object.fromEntries(tasks.map((task) => [task.id, task.display_name]));
        this.state.projectTasksByAction = Object.fromEntries(actions.map((action) => [
            action.id,
            action.project_task_ids.filter((id) => taskNames[id]).map((id) => ({ id, name: taskNames[id], valid: validTasks.has(id) })),
        ]));
    },

    hasTodoAction(item) {
        if (this.typeBehavior(item) !== "todo" || !item.requires_project_task) return super.hasTodoAction(item);
        return this.pointActions(item).some((action) =>
            action.state !== "cancelled" && action.responsible_user_id && (this.state.projectTasksByAction[action.id] || []).some(task => task.valid)
        );
    },

    pointOutcomeLabel(item) {
        if (
            this.typeBehavior(item) === "todo" && item.disposition === "open" &&
            this.pointActions(item).some(action => action.state !== "cancelled" && action.responsible_user_id) && !this.hasTodoAction(item)
        ) {
            return _t("Project task required");
        }
        return super.pointOutcomeLabel(item);
    },

    async createProjectTask(action) {
        try {
            const actionWindow = await this.orm.call(
                "community.meeting.action", "action_create_project_task", [[action.id]]
            );
            await this.actionService.doAction(actionWindow, {
                onClose: () => this.refreshProjectTaskLinks(),
            });
        } catch (error) {
            this.notification.add(_t("Could not open the Project task form."), { type: "danger" });
        }
    },
});
