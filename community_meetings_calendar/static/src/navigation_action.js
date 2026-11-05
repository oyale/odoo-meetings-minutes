/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ancestorBreadcrumb, restoreBreadcrumb } from "@community_meetings/live_meeting/live_meeting";

export class CalendarNavigationAction extends Component {
    static template = "community_meetings_calendar.NavigationAction";
    static props = ["action", "*", "close?"];

    setup() {
        this.actionService = useService("action");
        onWillStart(async () => {
            const { model, res_id: recordId, fallback } = this.props.action.params || {};
            const ancestor = ancestorBreadcrumb(this.env, model, recordId);
            if (ancestor && await restoreBreadcrumb(this.actionService, ancestor)) return;
            if (fallback) {
                await this.actionService.doAction(fallback, { stackPosition: "replaceCurrentAction" });
                return;
            }
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: model,
                res_id: recordId,
                views: [[false, "form"]],
                target: "current",
            }, { stackPosition: "replaceCurrentAction" });
        });
    }
}

registry.category("actions").add("community_meetings_calendar.navigate_record", CalendarNavigationAction);
