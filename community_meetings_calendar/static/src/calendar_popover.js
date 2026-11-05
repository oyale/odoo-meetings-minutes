/** @odoo-module **/

import { AttendeeCalendarCommonPopover } from "@calendar/views/attendee_calendar/common/attendee_calendar_common_popover";
import { patch } from "@web/core/utils/patch";

patch(AttendeeCalendarCommonPopover.prototype, {
    get isMeetingEvent() {
        return Boolean(this.props.record.rawRecord.community_meeting_id);
    },

    get displayAttendeeAnswerChoice() {
        // Managed events are read-only: Odoo does not initialize their statusInfo.
        return !this.isMeetingEvent && super.displayAttendeeAnswerChoice;
    },

    get isEventDetailsVisible() {
        return this.isMeetingEvent
            ? this.isCurrentUserAttendee
            : super.isEventDetailsVisible;
    },

    get isEventViewable() {
        return this.isMeetingEvent
            ? this.isCurrentUserAttendee
            : super.isEventViewable;
    },
});
