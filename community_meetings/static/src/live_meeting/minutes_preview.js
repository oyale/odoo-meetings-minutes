/** @odoo-module **/

import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MinutesPreview extends Component {
    static template = "community_meetings.MinutesPreview";
    static props = ["action", "*", "close?"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({ loading: true, html: "", error: "" });
        onWillStart(async () => {
            const meetingId = this.props.action?.params?.meeting_id
                || this.props.action?.context?.active_id;
            if (!meetingId) {
                this.state.error = _t("The meeting could not be identified.");
                this.state.loading = false;
                return;
            }
            try {
                this.state.html = markup(await this.orm.call(
                    "community.meeting",
                    "get_minutes_preview_html",
                    [[meetingId]],
                ));
            } catch (error) {
                this.state.error = error?.data?.message || error?.message
                    || _t("The minutes preview could not be loaded.");
            } finally {
                this.state.loading = false;
            }
        });
    }

    get backToMeetingLabel() {
        return this.props.action?.params?.review_return
            ? _t("Back to live meeting")
            : _t("Return to meeting to edit");
    }

    async backToMeeting() {
        const meetingId = this.props.action?.params?.meeting_id
            || this.props.action?.context?.active_id;
        const reviewReturn = this.props.action?.params?.review_return;
        if (reviewReturn?.meeting_id) {
            if (reviewReturn.item_id) {
                sessionStorage.setItem(
                    `community_meetings.review_return_item.${reviewReturn.meeting_id}`,
                    String(reviewReturn.item_id),
                );
            }
            const action = await this.orm.call(
                "community.meeting",
                "action_open_live_meeting",
                [[reviewReturn.meeting_id]],
            );
            return this.actionService.doAction(action);
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "community.meeting",
            res_id: meetingId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("community_meetings.minutes_preview", MinutesPreview);
