/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const PRIORITIES = [
    { value: "0", label: _t("Low-key"), hint: _t("When there's room"), icon: "fa-leaf" },
    { value: "1", label: _t("Normal"), hint: _t("Steady pace"), icon: "fa-circle-o" },
    { value: "2", label: _t("High"), hint: _t("Needs attention"), icon: "fa-bolt" },
    { value: "3", label: _t("Critical"), hint: _t("Drop everything"), icon: "fa-fire" },
];

const CARRYOVER_DECISIONS = [
    { value: "include", label: _t("Accept"), icon: "fa-check", color: "include" },
    { value: "postpone", label: _t("Postpone"), icon: "fa-clock-o", color: "postpone" },
    { value: "discard", label: _t("Discard"), icon: "fa-times", color: "discard" },
];

export class MeetingPriorityField extends Component {
    static template = "community_meetings.MeetingPriorityField";
    static props = { ...standardFieldProps };

    get value() {
        return String(this.props.record.data[this.props.name] ?? "1");
    }

    get choices() {
        return PRIORITIES;
    }

    select(value) {
        if (!this.props.readonly) {
            this.props.record.update({ [this.props.name]: value });
        }
    }
}

export class MeetingMinutesField extends Component {
    static template = "community_meetings.MeetingMinutesField";
    static props = {
        ...standardFieldProps,
        companyDefault: { type: Boolean, optional: true },
    };

    get value() {
        return Number(this.props.record.data[this.props.name] || 0);
    }

    get usesCompanyDefault() {
        return this.props.companyDefault && this.value === 0;
    }

    setValue(value) {
        if (!this.props.readonly) {
            const minutes = Math.max(0, Number.parseInt(value, 10) || 0);
            this.props.record.update({ [this.props.name]: minutes });
        }
    }

    selectAll(event) {
        event.target.select();
    }

    useCompanyDefault() {
        this.setValue(0);
    }
}

export class MeetingMoreOptionsField extends Component {
    static template = "community_meetings.MeetingMoreOptionsField";
    static props = { ...standardFieldProps };

    get value() {
        return Boolean(this.props.record.data[this.props.name]);
    }

    toggle() {
        if (!this.props.readonly) {
            this.props.record.update({ [this.props.name]: !this.value });
        }
    }
}

export class MeetingCarryoverDecisionField extends Component {
    static template = "community_meetings.MeetingCarryoverDecisionField";
    static props = { ...standardFieldProps };

    get value() {
        return this.props.record.data[this.props.name];
    }

    get choices() {
        return CARRYOVER_DECISIONS;
    }

    stopRowEvent(event) {
        event.stopPropagation();
    }

    select(value, event) {
        event.stopPropagation();
        this.props.record.update({ [this.props.name]: value });
    }
}

export class MeetingClearTopicField extends Component {
    static template = "community_meetings.MeetingClearTopicField";
    static props = { ...standardFieldProps };

    clear() {
        if (!this.props.readonly) {
            this.props.record.update({ topic_id: false });
        }
    }
}

registry.category("fields").add("meeting_point_priority", {
    component: MeetingPriorityField,
    displayName: _t("Meeting point priority"),
    supportedTypes: ["selection"],
});
registry.category("fields").add("meeting_point_minutes", {
    component: MeetingMinutesField,
    displayName: _t("Meeting point estimate"),
    supportedTypes: ["integer"],
    extractProps: ({ options }) => ({
        companyDefault: Boolean(options.company_default),
    }),
});
registry.category("fields").add("meeting_point_more_options", {
    component: MeetingMoreOptionsField,
    displayName: _t("Meeting point extra options"),
    supportedTypes: ["boolean"],
});
registry.category("fields").add("meeting_carryover_decision", {
    component: MeetingCarryoverDecisionField,
    displayName: _t("Meeting carryover decision"),
    supportedTypes: ["selection"],
});
registry.category("fields").add("meeting_clear_topic", {
    component: MeetingClearTopicField,
    displayName: _t("Clear selected point"),
    supportedTypes: ["boolean"],
});
