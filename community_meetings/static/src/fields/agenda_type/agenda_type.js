/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useSpecialData } from "@web/views/fields/relational_utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const BEHAVIOR_ICONS = {
    information: "fa-info-circle",
    discussion: "fa-comments-o",
    decision: "fa-gavel",
    todo: "fa-check-square-o",
    minutes_approval: "fa-check-circle-o",
    next_meeting: "fa-calendar-plus-o",
    followup: "fa-share",
};

export class AgendaTypeField extends Component {
    static template = "community_meetings.AgendaTypeField";
    static props = {
        ...standardFieldProps,
        domain: { type: [Array, Function], optional: true },
    };

    setup() {
        this.specialData = useSpecialData(async (orm, props) => {
            const { relation } = props.record.fields[props.name];
            const domain = getFieldDomain(props.record, props.name, props.domain);
            const { records } = await orm.call(relation, "web_search_read", [], {
                specification: { display_name: 1, icon: 1, behavior: 1 },
                domain,
            });
            return records.map((record) => ({
                id: record.id,
                name: record.display_name,
                icon: record.icon || BEHAVIOR_ICONS[record.behavior] || "fa-circle-o",
            }));
        });
    }

    get items() {
        return this.specialData.data || [];
    }

    get value() {
        const value = this.props.record.data[this.props.name];
        return Array.isArray(value) ? value[0] : value;
    }

    select(item) {
        if (this.props.readonly) return;
        this.props.record.update({ [this.props.name]: [item.id, item.name] });
    }
}

export const agendaTypeField = {
    component: AgendaTypeField,
    displayName: _t("Agenda type with icon"),
    supportedTypes: ["many2one"],
    extractProps: (_fieldDef, dynamicInfo) => ({ domain: dynamicInfo.domain }),
};

registry.category("fields").add("meeting_agenda_type", agendaTypeField);
