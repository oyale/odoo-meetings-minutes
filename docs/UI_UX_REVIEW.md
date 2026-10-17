# UI/UX Review — `community_meetings` addons

Date: 2026-10-17
Scope: `community_meetings`, `community_meetings_calendar`, `community_meetings_project`, `community_meetings_extension_demo`. Static review of all XML views, OWL components (`live_meeting`, `agenda_type` field, list controllers), SCSS, wizards and menus. No runtime/browser session included.

---

## 1. Summary

Solid base: live meeting screen has autosave with status indicator, `beforeunload` guard, good ARIA coverage, responsive breakpoints, progressive disclosure (`<details>`, "More options" toggles). Main weaknesses: terminology/label inconsistency, raw technical fields exposed to users, duplicated entry points, dead UI artifacts, and a few flows with surprising side effects.

Severity scale: **fail** = broken/confusing today, **weird** = works but surprising, **polish** = improvement.

---

## 2. Failures / likely bugs

| # | Where | Issue | Fix |
|---|-------|-------|-----|
| F1 | `meeting_views.xml` Editorial Notes page | `private_note_ids` list: `agenda_item_id` has **no domain** — user can link a note to an agenda item of another meeting. Dissents list right below has the correct domain. | Add `domain="[('meeting_id', '=', parent.id)]"`. |
| F2 | `preparation_views.xml` L72 | `menu_community_meeting_carryovers` is defined (carryover_views.xml L80) then **deactivated** in another file. Result: no way to browse all carryovers; editors only see them inside a meeting. Dead/ghost config. | Either delete the menu record entirely or reactivate — decide one. |
| F3 | `live_meeting.js` `navigateItem()` (L463) | Arrow up/down **silently pauses any running point timer**. User navigating the agenda stops time tracking without warning. | Pause only the active point when navigating *away from it*, or confirm. |
| F4 | `calendar_event_views.xml` L12-14 | Banner says *"Use the meeting link to view or edit meeting details"* but **no link/button to the meeting exists** on the event. Dead-end instruction. | Add a stat/header button `action_open_community_meeting`. |
| F5 | Form vs Live logic gap | Meeting form agenda list lets editors set `disposition`/`decision_result` directly (held state), bypassing live-screen rules (decision requires agreement, TODO requires follow-up task). Two paths, two rule sets. | Make those fields readonly in the form once state ≥ held, push users to Live. |
| F6 | `live_meeting.js` L314, 722, 744, 874, 891, 906, 968 | Several user-facing notification strings **not wrapped in `_t()`** — untranslatable. Others are. | Wrap all. |

---

## 3. Weird / confusing

| # | Where | Issue |
|---|-------|-------|
| W1 | Meeting form header | **11 header buttons**. "Finish Meeting" and "Record as Already Held" both call `action_mark_held` with opposite visibility — correct logic, but two labels for one action reads as duplication risk. |
| W2 | Carryover wizard + form + list | `origin_model` shown raw (`community.meeting.resolution`) to end users. Technical noise; also in list view. Should be invisible or human-labeled. |
| W3 | Approved Revisions tab | Full `snapshot_sha256` / `pdf_sha256` hashes in the list. Forensic data in primary UI. Move to form view or tooltip. |
| W4 | Statusbar vs reality | Meeting "in progress" is still state `scheduled` (+ `actual_start_datetime`). Statusbar shows "Scheduled" while meeting runs. A dedicated state or a visible "In progress" badge in form/list would match mental model (search filter already names it). |
| W5 | List default order | `start_datetime asc` → oldest meetings first, including past ones; no default filter hides approved/cancelled. First landing = archive. Suggest default `upcoming`-style filter or desc order. |
| W6 | Search filters | 4 overlapping scheduled-flavored filters (Scheduled / Upcoming / Scheduled in the Past / In Progress). Powerful but cluttered; consider grouping under a separator. |
| W7 | "My Meetings" | Only matches `organizer_id`. Secretary and attendees don't see "their" meetings. |
| W8 | Series form | "Propose a point" stat button shown to `base.group_user`, but the series menu is restricted to editors — readers can't reach the form anyway. Dead affordance or wrong group. |
| W9 | `menus.xml` | `<delete model="ir.ui.menu" id="menu_community_meetings"/>` — migration artifact living in view definitions. Move to a migration script. |
| W10 | Live topbar | "Record as Already Held" sits next to "Start Meeting" with no confirmation — one misclick ends a meeting that never started. |
| W11 | Live `toggle(item)` | Collapsing a card also sets it as `activeItemId` — keyboard nav then jumps to a collapsed card. |
| W12 | Inconsistent capitalization/verbs | "Propose a Point" (menu) vs "Propose a point" (button); "Follow Up" / "Follow up at another meeting" / "Request Follow-up" / "Move to another meeting" for the same concept; aria-label "Statement type" vs "Dissent reason" for the same field. Pick one verb set. |
| W13 | Point wizard placeholder | `placeholder="2026-10-16 Weekly series"` — hardcoded date example will age; use a relative/generic example. |

---

## 4. UX proposals (prioritized)

**P0 — do first**
1. Fix F1 domain, F2 menu, F3 silent pause, F4 dead-end banner, F6 `_t`.
2. Meeting list: default filter "Upcoming" + `decoration-*` or badge colors per state (today all badges look identical).
3. Carryovers: give editors a real browse view (reactivate menu) or remove the model's list action entirely.

**P1**
4. Meeting form: add `oe_button_box` stats (open follow-ups, agenda count, pending carryovers) — currently zero stat buttons while series form has two.
5. Live meeting: single primary CTA per meeting state; move "Record as Already Held" into a dropdown/secondary with `confirm`.
6. Rename visible state to "In progress" when `actual_start_datetime` set (at least badge in form/list).
7. "My Meetings" filter: `organizer_id = uid OR secretary_id = uid OR attendee = me`.
8. Hash columns out of revisions list; show short SHA + copy button on form.

**P2**
9. Role assignment UX: meeting roles group on user form is `base.group_system` only — meeting managers (the natural role-granters) can't assign. Consider `group_meeting_manager` visibility.
10. Consolidate proposal entry points: menu "Propose a Point" + series stat button — keep both but same label and same wizard defaults.
11. Wizard statusbars: set `statusbar_visible` explicitly and decide if steps are clickable (today ambiguous).

---

## 5. Performance affecting UX

- `live_meeting.js load()`: N+1 — one `get_followup_defaults` RPC **per agenda item** (L111-112), plus ~10 other calls. Large agenda = slow open. Batch into one RPC returning a map.
- `searchPartners`: fires per keystroke (token-guarded but no debounce). Add ~300 ms debounce.
- `res.users` loaded with `limit: 200` for owner selects — silent truncation past 200 users; at minimum document, better use a many2one-autocomplete component.

## 6. Accessibility

Good: aria-labels on icon buttons, `visually-hidden` current-point marker, `aria-live` save status, radiogroup for deferral reasons, focus move to agreement title.
Gaps:
- Priority flag is color-only (icon + color); has hidden label — OK, but consider text in list view too.
- Outcome badges rely on color (`text-bg-*`); paired text exists — acceptable.
- "⋯" convert-followup dropdown: keyboard reachable but menu items are `<button>` inside `<li>` without `menuitem` role — minor.
- Attendee editor checkboxes: fine; "No matching contacts" not `aria-live`.

## 7. Dead code / hygiene

- SCSS: `.o_live_general_records`, `.o_live_general_task` styled but absent from current template (removed feature?). `.o_meeting_type_choices` lives in `agenda_type` template — verify usage of both blocks.
- `menus.xml` delete hack (W9).
- Disabled carryovers menu record (F2).
- Hardcoded brand fallback `#714B67` in SCSS — fine as fallback, but duplicated brand knowledge.

## 8. Calendar module note

Readonly-overriding ~25 fields individually is brittle — any new `calendar.event` field from upstream stays editable, breaking the "managed by meeting" invariant. Consider a computed `user_can_edit`-style single gate if Odoo allows, or accept and document the whitelist approach.

---

*Skipped: runtime/browser click-through, report template (PDF) review, translations audit beyond JS `_t`. Add when a running instance is available.*

---

## Status — 2026-10-17

Implemented: F1, F5, F6, W1+W10 (confirm), W2, W4 (display-only `display_state`, debt comment in `meeting.py`), W5, W6, W7 (organizer+secretary+attendee), W9 (moved to `migrations/18.0.6.1.0`), W11, W12 (canonical: Postpone / Move to another meeting / Propose a point / Dissent reason), W13. Manifest bumped to 18.0.6.1.0.
Skipped: F2, F3, F4 (not requested), W3 (kept per decision), W8 (left as-is per decision).
Pending verification: Odoo view validation + browser pass on a running instance (`run_development_suite.py --development`).
