/** @odoo-module **/

import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { router } from "@web/core/browser/router";
import { useService } from "@web/core/utils/hooks";
import { Breadcrumbs } from "@web/search/breadcrumbs/breadcrumbs";

export class MinutesPreview extends Component {
    static template = "community_meetings.MinutesPreview";
    static displayName = _t("Minutes preview");
    static components = { Breadcrumbs };
    static props = ["action", "*", "close?"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({ loading: true, html: "", error: "" });
        onWillStart(async () => {
            const params = this.props.action?.params || {};
            const legacyRoute = router.current;
            const legacyPreview = Number(legacyRoute.cm_minutes_preview) === 1;
            const revisionId =
                Number(params.revision_id)
                || (legacyPreview && Number(legacyRoute.cm_minutes_revision_id))
                || false;
            const meetingId =
                Number(params.meeting_id)
                || Number(params.resId)
                || Number(params.active_id)
                || this.props.action?.context?.active_id
                || this.props.action?.context?.params?.id
                || (legacyPreview && Number(legacyRoute.cm_minutes_meeting_id))
                || false;
            this.state.meetingId = meetingId || false;
            this.state.revisionId = revisionId || false;
            this.state.returnTo =
                params.return_to || (legacyPreview && legacyRoute.cm_minutes_return_to) || "form";
            this.state.itemId =
                Number(params.item_id)
                || (legacyPreview && Number(legacyRoute.cm_minutes_item_id))
                || 0;
            this.state.reviewReturn =
                params.review_return
                || (Number(params.review_return_meeting_id)
                    ? {
                          meeting_id: Number(params.review_return_meeting_id),
                          item_id: Number(params.review_return_item_id) || false,
                      }
                    : false)
                || (legacyPreview && Number(legacyRoute.cm_minutes_return_meeting_id)
                    ? { meeting_id: Number(legacyRoute.cm_minutes_return_meeting_id), item_id: Number(legacyRoute.cm_minutes_return_item_id) || false }
                    : false);
            if (!meetingId) {
                this.state.error = _t("The meeting could not be identified.");
                this.state.loading = false;
                return;
            }
            this.env.config.setDisplayName?.(this.state.revisionId ? _t("Approved minutes") : _t("Minutes preview"));
            const originJsId = Number(params.origin_js_id);
            if (originJsId) this._originJsId = originJsId;
            this.props.updateActionState?.({
                meeting_id: meetingId,
                resId: meetingId,
                active_id: meetingId,
                revision_id: revisionId || 0,
                return_to: this.state.returnTo,
                item_id: this.state.itemId || 0,
                review_return_meeting_id: this.state.reviewReturn?.meeting_id || 0,
                review_return_item_id: this.state.reviewReturn?.item_id || 0,
                origin_js_id: originJsId || 0,
            });
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

    get breadcrumbs() {
        return this.env.config?.breadcrumbs || [];
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
        return this.backToOrigin();
    }

    async backToOrigin() {
        const meetingId = this.state.meetingId;
        const returnTo = this.state.returnTo;
        const originJsId = this._originJsId || Number(this.props.action?.params?.origin_js_id);
        if (originJsId) {
            try {
                await this.actionService.restore(originJsId);
                return;
            } catch (error) {
                if (error?.name !== "ControllerNotFoundError") throw error;
            }
        }
        if (this.state.revisionId && this.state.returnTo === "live") {
            if (this.state.itemId) {
                sessionStorage.setItem(
                    `community_meetings.review_return_item.${meetingId}`,
                    String(this.state.itemId),
                );
            }
            const action = await this.orm.call("community.meeting", "action_open_live_meeting", [[meetingId]]);
            action.params = { ...action.params, active_agenda_item_id: this.state.itemId || 0 };
            return this.actionService.doAction(action, { stackPosition: "replaceCurrentAction" });
        }
        if (this.state.reviewReturn?.meeting_id) {
            const reviewReturn = this.state.reviewReturn;
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
            action.params = {
                ...action.params,
                active_agenda_item_id: reviewReturn.item_id || 0,
            };
            return this.actionService.doAction(action, { stackPosition: "replaceCurrentAction" });
        }
        if (returnTo === "approved_minutes") {
            return this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "community.meeting.revision",
                views: [[false, "list"]],
                domain: [["status", "=", "approved"]],
                target: "current",
            }, { stackPosition: "replaceCurrentAction" });
        }
        if (returnTo === "list") {
            return this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "community.meeting",
                views: [[false, "list"], [false, "form"]],
                target: "current",
            }, { stackPosition: "replaceCurrentAction" });
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
            action.params = { ...action.params, active_agenda_item_id: this.state.itemId || 0 };
            return this.actionService.doAction(action, { stackPosition: "replaceCurrentAction" });
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "community.meeting",
            res_id: meetingId,
            views: [[false, "form"]],
            target: "current",
        }, { stackPosition: "replaceCurrentAction" });
    }
}

registry.category("actions").add("community_meetings.minutes_preview", MinutesPreview);
