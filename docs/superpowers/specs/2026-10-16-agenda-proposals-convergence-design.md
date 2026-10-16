# Agenda proposals as proposed points — design

Date: 2026-10-16
Status: approved (design), pending spec review
Scope: `community_meetings` core. Backlog ticket 09 (proposal↔topic convergence),
plan §14.

## Context

`community.meeting.agenda.proposal` is a model separate from `community.meeting.topic`.
A proposal can target a series or a specific meeting; on acceptance it creates a
bare agenda row in a chosen draft meeting. It is **not** part of candidate
discovery (`_agenda_candidates`), so a proposal never surfaces when preparing the
next meeting — you must accept it manually into a draft meeting.

The desired model: a proposal **is** a proposed point of the series, and it is
offered for review when the next meeting is created.

## Goals

- Proposals become persistent points (`community.meeting.topic`, state `proposed`)
  with **all** point fields.
- A proposed point is offered as a candidate when preparing a meeting and is
  reviewed there: accept, postpone, or discard.
- Remove the separate proposal model and its intermediate "accept into a draft
  meeting" flow.

## Non-goals

- Migration of existing `agenda.proposal` rows (development environment; the user
  excluded migration).
- A portal web form. There was none — only ACL/rules.

## Decisions

1. **Eliminate the separate model.** A topic in state `proposed` *is* the
   proposal. No `community.meeting.agenda.proposal`, no
   `community.meeting.proposal.accept.wizard`.
2. **Series-only.** Proposals target a series (`series_id`). No per-meeting
   target; they always surface at the next meeting of the series.
3. **Reuse the point wizard to propose** (all point fields), reached from a new
   "Propose a point" entry.
4. **Eligibility is kept**: `community.meeting.proposal.group.policy`,
   `community.meeting.proposal.grant`, `group_agenda_proposer`, and
   `submit_on_behalf`. Being able to propose still does not grant general access
   to meetings.
5. **Review decisions**: `include / postpone / discard` per candidate line, for
   both proposed points and carried points.
6. Portal ACL/record rules referenced the removed model and are dropped with it.

## Data model

`community.meeting.topic` gains optional proposal fields (empty for ordinary
points):

| Field | Type | Notes |
|---|---|---|
| `proposer_partner_id` | Many2one `res.partner` | who the proposal is for |
| `submitted_by_user_id` | Many2one `res.users` | who submitted, readonly |
| `submitted_at` | Datetime | readonly |
| `proposal_status` | Selection | `submitted` / `accepted` / `rejected` / `withdrawn` |
| `proposal_response` | Text | reviewer's note |
| `responded_by_id` | Many2one `res.users` | readonly |
| `responded_at` | Datetime | readonly |

`state` (`proposed` / `open` / `closed`) remains the point lifecycle; a proposal
starts at `state=proposed`. `proposal_status` is set only through workflow
actions (never a direct write), like the previous model's status.

The old `proposal.group.policy` and `proposal.grant` are unchanged (they govern
who may propose; now checked when creating a proposed topic).

## Submission flow

- New **"Propose a point"** menu item and a button on the series form.
- Opens `community.meeting.point.wizard` in **propose mode** (series context, no
  meeting). Saving creates a `community.meeting.topic` with
  `state=proposed`, `proposal_status=submitted`, `submitted_by_user_id=self`,
  `submitted_at=now`, `proposer_partner_id=user partner`, and all point fields
  (name, description, agenda_type_id, priority, deadline, estimated_minutes,
  series, company, follow-up policy, related points).
- Eligibility is enforced on create: the user needs `group_agenda_proposer` or a
  matching `proposal.group.policy`; the proposer cannot be forged.
- `submit_on_behalf(partner_id, ...)` is retained and creates a proposed topic
  for the given contact after grant checks (as today).

## Candidate discovery

`_agenda_candidates(series, start)` adds topics with
`proposal_status='submitted'` (and `state='proposed'`) of the series, with
`reason = "Proposed point"` and key `proposal:<topic_id>`. Existing carryover and
promoted candidates are unchanged.

## Review flow

In the new-meeting wizard "Continue points" step, every candidate line has a
**decision** (radio, visual):

- `include` → include now.
  - proposal: `state=open`, `proposal_status=accepted`, and a participation of
    the topic is created in the meeting.
  - carried: as today (`_include_agenda_candidate`).
- `postpone` → not included; stays eligible.
  - proposal: stays `submitted` → offered again at future meetings.
  - carried: stays pending / review flag kept → offered again.
- `discard` → proposal only: `proposal_status=rejected`; never offered again.
  (Carried points keep their existing dismiss flow, not offered here.)

The decision control shows `discard` for proposed-point lines only; carried-point
lines offer `include` and `postpone`.

Proposer actions on their own proposal: `withdraw` while it is still `submitted`
(→ `proposal_status=withdrawn`).

A **"Proposals to review"** block on the series form (and the meeting form)
offers the same include/postpone/discard actions outside meeting creation.

## Removal / cleanup

- Delete `models/proposal.py` (`agenda.proposal`), `models/proposal_wizard.py`
  (accept wizard), their views/menus/actions, the accept-wizard view and action.
- Delete the proposal ACL rows and record rules that target the removed model
  (including the `base.group_portal` rows). Keep the eligibility groups,
  policies and grants.
- Remove proposal references from `models/__init__.py`, `__manifest__.py` data
  list, and any security CSV/rules.

## Wizard review-line change

`community.meeting.carry.review.line` replaces `accept` (boolean) with
`decision` (Selection `include` / `postpone` / `discard`, default `include`).
`MeetingCreateWizard.action_finish` dispatches on the decision. Existing carryover
include behaviour is preserved for `include`.

## Testing (ORM)

- Submitting creates a proposed topic with all point fields and `submitted`
  status; an ineligible user cannot create one; the proposer cannot be forged.
- `_agenda_candidates` includes submitted proposals of the series.
- Include: topic `open` + `accepted` + participation created.
- Postpone: topic stays `submitted` and is offered again.
- Discard: `rejected` and no longer offered.
- Withdraw: `withdrawn`, only by the proposer, only while `submitted`.
- Carried candidates: `postpone` keeps them eligible; `include` unchanged.
- Eligibility (`submit_on_behalf`, grants, policy group) still enforced.

## Acceptance criteria

- [ ] No `agenda.proposal` model; proposals are `topic(state=proposed)`.
- [ ] Proposing reuses the point wizard and captures every point field.
- [ ] Proposed points appear as candidates when preparing a meeting.
- [ ] Include/postpone/discard behave as specified; carried points are
      postponable too.
- [ ] Eligibility and audit (who proposed, who responded, when) are preserved.
- [ ] The old proposal UI is gone; a "Propose a point" entry exists.
