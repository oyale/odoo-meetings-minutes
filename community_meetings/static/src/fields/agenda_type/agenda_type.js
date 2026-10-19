/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
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
const BEHAVIOR_HINTS = {
    information: _t("Share updates and background."),
    discussion: _t("Explore a question together."),
    decision: _t("Record a decision and its outcome."),
    todo: _t("Agree on work to follow up."),
    minutes_approval: _t("Review and approve the meeting minutes."),
    next_meeting: _t("Agree when the group will meet again."),
    followup: _t("Review progress on an existing follow-up."),
};

export class AgendaTypeField extends Component {
    static template = "community_meetings.AgendaTypeField";
    static props = {
        ...standardFieldProps,
        domain: { type: [Array, Function], optional: true },
        richChoices: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({ showAllRichChoices: true });
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
                behavior: record.behavior,
                hint: BEHAVIOR_HINTS[record.behavior] || _t("Choose the type that best fits this point."),
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
        if (this.props.richChoices && !this.state.showAllRichChoices && item.id === this.value) {
            this.state.showAllRichChoices = true;
            return;
        }
        this.props.record.update({ [this.props.name]: [item.id, item.name] });
        if (this.props.richChoices) this.state.showAllRichChoices = false;
    }

    onKeydown(ev, item) {
        if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " ", "Enter"].includes(ev.key)) return;
        ev.preventDefault();
        if (ev.key === " " || ev.key === "Enter") {
            this.select(item);
            return;
        }
        const buttons = [...ev.currentTarget.parentElement.querySelectorAll("button:not(:disabled)")];
        const index = buttons.indexOf(ev.currentTarget);
        const delta = ["ArrowRight", "ArrowDown"].includes(ev.key) ? 1 : -1;
        const nextButton = buttons[(index + delta + buttons.length) % buttons.length];
        nextButton?.focus();
        const nextItem = this.items.find(
            (candidate) => String(candidate.id) === nextButton?.dataset.itemId
        );
        if (nextItem) this.select(nextItem);
    }
}

export const agendaTypeField = {
    component: AgendaTypeField,
    displayName: _t("Agenda type with icon"),
    supportedTypes: ["many2one"],
    extractProps: (_fieldDef, dynamicInfo) => ({ domain: dynamicInfo.domain }),
};

registry.category("fields").add("meeting_agenda_type", agendaTypeField);
registry.category("fields").add("meeting_agenda_type_rich", {
    ...agendaTypeField,
    displayName: _t("Meeting agenda type cards"),
    extractProps: (_fieldDef, dynamicInfo) => ({
        domain: dynamicInfo.domain,
        richChoices: true,
    }),
});
