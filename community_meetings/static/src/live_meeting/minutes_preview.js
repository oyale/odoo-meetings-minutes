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
            const params = this.props.action?.params || {};
            const revisionId =
                Number(params.revision_id)
                || (restore && Number(route.cm_minutes_revision_id))
                || false;
            const meetingId =
                Number(params.meeting_id)
                || this.props.action?.context?.active_id
                || (restore && Number(route.cm_minutes_meeting_id))
                || false;
            this.state.meetingId = meetingId || false;
            this.state.revisionId = revisionId || false;
            this.state.returnTo =
                params.return_to || (restore && route.cm_minutes_return_to) || "form";
            this.state.itemId =
                Number(params.item_id)
                || (restore && Number(route.cm_minutes_item_id))
                || 0;
            this.state.reviewReturn =
                params.review_return
                || (restore
                    && (Number(route.cm_minutes_return_meeting_id)
                        ? {
                              meeting_id: Number(route.cm_minutes_return_meeting_id),
                              item_id: Number(route.cm_minutes_return_item_id) || false,
                          }
                        : false));
            if (!meetingId) {
                this.state.error = _t("The meeting could not be identified.");
                this.state.loading = false;
                return;
            }
            if (revisionId) {
                this.router.pushState(
                    {
                        cm_minutes_preview: 1,
                        cm_minutes_meeting_id: meetingId || 0,
                        cm_minutes_revision_id: revisionId,
                        cm_minutes_return_to: this.state.returnTo,
                        cm_minutes_item_id: this.state.itemId || 0,
                        cm_minutes_return_meeting_id: 0,
                        cm_minutes_return_item_id: 0,
                    },
                    { sync: true },
                );
            }
            try {
                if (revisionId) {
                    this.state.html = markup(
                        await this.orm.call(
                            "community.meeting.revision",
                            "get_approved_minutes_preview_html",
                            [[revisionId]],
                        ),
                    );
                } else {
                    this.state.html = markup(
                        await this.orm.call(
                            "community.meeting",
                            "get_minutes_preview_html",
                            [[meetingId]],
                        ),
                    );
                }
            } catch (error) {
                this.state.error =
                    error?.data?.message
                    || error?.message
                    || _t("The minutes preview could not be loaded.");
            } finally {
                this.state.loading = false;
            }
        });
    }

    get previewLabel() {
        return this.state.revisionId
            ? _t("Approved minutes")
            : _t("Draft preview · saved content");
    }

    get backToMeetingLabel() {
        if (this.state.revisionId) {
            if (this.state.returnTo === "list") {
                return _t("Back to meetings");
            }
            if (this.state.returnTo === "live") {
                return _t("Back to live meeting");
            }
            return _t("Return to meeting");
        }
        return this.state.reviewReturn
            ? _t("Back to live meeting")
            : _t("Return to meeting to edit");
    }

    async backToMeeting() {
        if (this.state.revisionId) {
            return this.backToOrigin();
        }
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

    async backToOrigin() {
        const meetingId = this.state.meetingId;
        const returnTo = this.state.returnTo;
        this.clearMinutesPreviewRoute();
        if (returnTo === "list") {
            return this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "community.meeting",
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        }
        if (returnTo === "live") {
            if (this.state.itemId) {
                sessionStorage.setItem(
                    `community_meetings.review_return_item.${meetingId}`,
                    String(this.state.itemId),
                );
            }
            const action = await this.orm.call(
                "community.meeting",
                "action_open_live_meeting",
                [[meetingId]],
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

    clearMinutesPreviewRoute() {
        this.router.pushState(
            {
                cm_minutes_preview: 0,
                cm_minutes_meeting_id: 0,
                cm_minutes_revision_id: 0,
                cm_minutes_return_to: "",
                cm_minutes_item_id: 0,
                cm_minutes_return_meeting_id: 0,
                cm_minutes_return_item_id: 0,
            },
            { sync: true },
        );
    }
}

registry.category("actions").add("community_meetings.minutes_preview", MinutesPreview);
