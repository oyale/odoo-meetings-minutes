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
    static props = { ...standardFieldProps };

    get value() {
        return Number(this.props.record.data[this.props.name] || 0);
    }

    setValue(value) {
        if (!this.props.readonly) {
            const minutes = Math.max(0, Number.parseInt(value, 10) || 0);
            this.props.record.update({ [this.props.name]: minutes });
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
});
