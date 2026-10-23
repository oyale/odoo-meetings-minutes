/** @odoo-module **/

import { Component } from "@odoo/owl";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export function createMentionAnchor(range, editable) {
    const document = editable.ownerDocument;
    const window = document.defaultView;
    const element = document.createElement("span");
    element.setAttribute("aria-hidden", "true");
    Object.assign(element.style, { position: "fixed", width: "1px", height: "1px", pointerEvents: "none" });
    const update = () => {
        const rect = range.getBoundingClientRect();
        element.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - 24))}px`;
        element.style.top = `${Math.max(56, Math.min(rect.bottom, window.innerHeight - 24))}px`;
    };
    document.body.append(element);
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return {
        element,
        remove: () => {
            window.removeEventListener("scroll", update, true);
            window.removeEventListener("resize", update);
            element.remove();
        },
    };
}

class MentionAutoComplete extends AutoComplete {
    externalClose(event) {
        // Inline inside a popover: scrolling must not disable keyboard
        // selection while this list remains visible.
        if (event.type !== "scroll") super.externalClose(event);
    }

    selectOption(option, params = {}) {
        if (option.loadMore) {
            option.loadMore();
            void this.open(true);
            return;
        }
        super.selectOption(option, params);
    }
}

export class DiscussionMentionPicker extends Component {
    static template = "community_meetings.DiscussionMentionPicker";
    static components = { AutoComplete: MentionAutoComplete };
    static props = ["itemId", "onSelect", "onCancel", "close?"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.contacts = [];
        this.searchTerm = "";
        this.fetchNext = false;
        this.searchToken = 0;
        this.sources = [{
            placeholder: _t("No matching contacts"),
            options: async (search) => {
                const token = ++this.searchToken;
                if (!this.fetchNext || search !== this.searchTerm) this.contacts = [];
                this.searchTerm = search;
                this.fetchNext = false;
                const offset = this.contacts.length;
                try {
                    const partners = await this.orm.call(
                        "community.meeting.agenda.item", "get_discussion_mention_suggestions",
                        [[this.props.itemId]], { search, offset, limit: 20 },
                    );
                    if (token !== this.searchToken) return [];
                    this.contacts.push(...partners);
                    const options = this.contacts.map((partner) => ({
                        partnerId: partner.id,
                        name: partner.name,
                        label: `${partner.name} · #${partner.id}`,
                    }));
                    if (partners.length === 20) {
                        options.push({
                            label: _t("More contacts…"),
                            loadMore: () => { this.fetchNext = true; },
                        });
                    }
                    return options;
                } catch {
                    this.notification.add(_t("Contacts could not be loaded. Check that this discussion is still editable."), { type: "warning" });
                    return [];
                }
            },
        }];
    }

    onKeydown(event) {
        if (event.key === "Escape") {
            event.stopPropagation();
            this.props.onCancel();
        }
    }
}
