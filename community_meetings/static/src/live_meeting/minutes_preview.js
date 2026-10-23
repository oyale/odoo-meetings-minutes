/** @odoo-module **/

import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { router } from "@web/core/browser/router";
import { useService } from "@web/core/utils/hooks";

export class MinutesPreview extends Component {
    static template = "community_meetings.MinutesPreview";
    static props = ["action", "*", "close?"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.router = router;
        this.state = useState({ loading: true, html: "", error: "" });
        onWillStart(async () => {
            const route = this.router.current;
            const restore = Number(route.cm_minutes_preview) === 1;
            const meetingId = this.props.action?.params?.meeting_id
                || this.props.action?.context?.active_id
                || (restore && Number(route.cm_minutes_meeting_id));
            this.state.meetingId = meetingId || false;
            this.state.reviewReturn = this.props.action?.params?.review_return || (restore && (
                Number(route.cm_minutes_return_meeting_id)
                    ? {
                        meeting_id: Number(route.cm_minutes_return_meeting_id),
                        item_id: Number(route.cm_minutes_return_item_id) || false,
                    }
                    : false
            ));
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
        return this.state.reviewReturn
            ? _t("Back to live meeting")
            : _t("Return to meeting to edit");
    }

    async backToMeeting() {
        const meetingId = this.state.meetingId;
        const reviewReturn = this.state.reviewReturn;
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
            const result = await this.actionService.doAction(action);
            this.clearMinutesPreviewRoute();
            return result;
        }
        const result = await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "community.meeting",
            res_id: meetingId,
            views: [[false, "form"]],
            target: "current",
        });
        this.clearMinutesPreviewRoute();
        return result;
    }

    clearMinutesPreviewRoute() {
        this.router.pushState({
            cm_minutes_preview: 0,
            cm_minutes_meeting_id: 0,
            cm_minutes_return_meeting_id: 0,
            cm_minutes_return_item_id: 0,
        }, { sync: true });
    }
}

registry.category("actions").add("community_meetings.minutes_preview", MinutesPreview);
