/** @odoo-module **/

import { Component } from "@odoo/owl";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const PAGE_SIZE = 20;

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

export function detectMentionTrigger(event, editable) {
    if (event.data !== "@" || event.isComposing || editable.getAttribute("contenteditable") !== "true") {
        return null;
    }
    const selection = editable.ownerDocument.getSelection();
    if (!selection?.isCollapsed || selection.anchorNode?.nodeType !== Node.TEXT_NODE) {
        return null;
    }
    const offset = selection.anchorOffset;
    const text = selection.anchorNode.textContent;
    if (text[offset - 1] !== "@" || (offset > 1 && /[\w@]/.test(text[offset - 2]))) {
        return null;
    }
    const caret = selection.getRangeAt(0).cloneRange();
    const replacement = caret.cloneRange();
    replacement.setStart(selection.anchorNode, offset - 1);
    return { caret, replacement };
}

export function createMentionElement({ partnerId, name, className = "o_meeting_person_mention" }) {
    const mention = document.createElement("span");
    mention.className = className;
    mention.dataset.oeModel = "res.partner";
    mention.dataset.oeId = partnerId;
    mention.setAttribute("contenteditable", "false");
    mention.textContent = `@${name}`;
    return mention;
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
    static props = [
        "fetchSuggestions",
        "onSelect",
        "onCancel",
        "label",
        "hint",
        "cancelLabel",
        "errorMessage",
        "canPick",
        "close?",
    ];

    setup() {
        this.notification = useService("notification");
        this.contacts = [];
        this.searchTerm = "";
        this.fetchNext = false;
        this.searchToken = 0;
        this.selectOption = this.selectOption.bind(this);
        this.sources = [
            {
                placeholder: _t("No matching contacts"),
                options: async (search) => {
                    const token = ++this.searchToken;
                    if (!this.fetchNext || search !== this.searchTerm) {
                        this.contacts = [];
                    }
                    this.searchTerm = search;
                    this.fetchNext = false;
                    const offset = this.contacts.length;
                    try {
                        const partners = await this.props.fetchSuggestions({
                            search,
                            offset,
                            limit: PAGE_SIZE,
                        });
                        if (token !== this.searchToken) {
                            return [];
                        }
                        this.contacts.push(...partners);
                        const options = this.contacts.map((partner) => ({
                            partnerId: partner.id,
                            name: partner.name,
                            label: `${partner.name} · #${partner.id}`,
                        }));
                        if (partners.length === PAGE_SIZE) {
                            options.push({
                                label: _t("More contacts…"),
                                loadMore: () => {
                                    this.fetchNext = true;
                                },
                            });
                        }
                        return options;
                    } catch {
                        this.notification.add(this.props.errorMessage, { type: "warning" });
                        return [];
                    }
                },
            },
        ];
    }

    selectOption(option) {
        if (!this.props.canPick()) {
            this.props.onCancel();
            return;
        }
        this.props.onSelect(option);
    }

    onKeydown(event) {
        if (event.key === "Escape") {
            event.stopPropagation();
            this.props.onCancel();
        }
    }
}
