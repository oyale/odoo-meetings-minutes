# New point wizard UX — design

Date: 2026-10-16
Status: approved (design), pending spec review
Scope: `community_meetings` core. Ticket 21 ("Point wizard hierarchy") plus the
body-editor and live-context work pulled in by the same request.

## Context

The "new point" wizard (`community.meeting.point.wizard`, form
`community_meetings.view_point_wizard`) is launched from three places:

- the meeting form (**Add Point**), via `community.meeting.action_add_point`;
- the new-meeting wizard's agenda step;
- the live meeting (JS `addPoint`), via the same `action_add_point`.

Today it is a flat dialog: an **Existing point** picker sits at the very top,
then type/title/priority, a large body editor, and a **More options** toggle
(`more_options`) hiding deadline, estimated minutes and follow-up policy. There
is no guidance text, the title is a plain field, and the three launch contexts
behave identically.

`community.meeting.topic.origin_topic_id` ("Origin point") already exists and is
set by promotion/continuation, but is not surfaced in the wizard.

## Goals

- Give the title and body visual priority; group the planning metadata; tuck
  advanced controls away.
- Make the body editor comfortable to write in, framed with guidance.
- One consistent form across contexts; the live path favors speed.
- Add "Related points": show the origin point read-only when set, and allow a
  free set of related points.

## Non-goals

- Configurable default estimated duration (ticket 19).
- Point attachments (ticket 14).
- Cross-series related-point confidentiality policy (ticket 13).

## Decisions

1. **Approach: restructured single dialog** (not a mode switch, not steps).
2. **Default vs advanced split**
   - Visible by default: Type, Title, Body, Priority, Deadline, Estimated
     duration (grouped).
   - Behind **More options**: Existing point, Related points, Follow-up
     policy / default kind, and the read-only origin point when set.
3. **Related links live on the persistent point** (`community.meeting.topic`),
   not on the participation.
4. **Live = same form, different close**: from live a single *Add point*
   closes; from preparation *Add and continue* stays.
5. **Reuse stays a field in More options** (not a top-level mode); choosing an
   existing point collapses the create fields, as today.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Add a point                                          [ × ]   │
│  Adding to  ●  <meeting name> · <date>              (muted)   │
│                                                               │
│  What is this point about?                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  <title>                                               │  │  oe_title h1
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  Type:  [ Discussion ▾ ]                                      │
│                                                               │
│  ── Description ────────────────────────────────────────────  │
│  Explain the subject so any attendee can follow it. Add the   │
│  links or documents needed to act on it.                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  B  I  U   •   1.   🔗              (rich toolbar)      │  │  full width,
│  │                                                          │  │  ~12rem min
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ── Planning ───────────────────────────────────────────────  │
│  Priority [ Normal ▾ ]        Deadline      [        ]        │
│  Estimated minutes [ 0 ]                                      │
│                                                               │
│  ▸ More options                                               │
│                                                               │
│              [ Cancel ]   [ Add and continue ]   [ Add point ]│
└──────────────────────────────────────────────────────────────┘
```

- Title uses `oe_title`/`h1`; a muted context line shows the target
  meeting/series when known.
- Section labels via `separator` ("Description", "Planning").
- Body: full-width `widget="html"`, generous min-height, help text above it.
- Metadata: a two-column group (Priority, Deadline, Estimated duration).
- **More options** reveals the advanced block (Existing point, Related points,
  Follow-up policy / default kind, origin point read-only).
- Mobile stays single-column; no horizontal overflow at ~390px.

## Model changes

- `community.meeting.point.wizard`: add `related_topic_ids`
  (many2many → `community.meeting.topic`).
- `community.meeting.topic`: add persistent `related_topic_ids`
  (many2many → `community.meeting.topic`).
- The wizard writes `related_topic_ids` onto the created topic, and updates the
  topic's value when reusing an existing point.
- Domain for the picker: same company, not self; readable points only. Access
  relies on the topic record rules — no `sudo`, no widened visibility.
- Existing fields (name, agenda_type_id, description, priority, deadline,
  estimated_minutes, followup_policy, default_followup_kind, topic_id) are
  unchanged.

## Live behavior

- Add `community.meeting.action_add_point_live` returning the wizard action with
  `from_live: True` in context.
- The live JS `addPoint()` calls `action_add_point_live`.
- The wizard view hides «Add and continue» when `context.get('from_live')`, so a
  single **Add point** closes the dialog. Preparation contexts keep both buttons.

## Reuse mode

- **Existing point** lives in More options. Selecting one hides the create
  fields and shows the point's name/type plus its **origin point** (read-only)
  when set; Related points remains editable. Saving links it as a participation
  (unchanged behavior).

## Styling

- Odoo-native markup only; no custom widget.
- A scoped SCSS rule for `.o_meeting_point_wizard` (body min-height, section
  rhythm, title spacing, muted context line). Registered in
  `web.assets_backend`.

## Testing

- ORM (`post_install`):
  - creating a point through the wizard persists `related_topic_ids` on the
    topic;
  - reusing an existing point updates its `related_topic_ids`;
  - `action_add_point_live` returns an action whose context contains
    `from_live`.
- Keep existing wizard/live ORM flows green; view loads without error
  (module update).
- Browser verification is out of scope for this change (Playwright not run
  here); the live add-point flow is unchanged apart from the hidden button.

## Acceptance criteria

- [ ] Title and body are visually dominant; body editor is full-width and
      comfortable.
- [ ] Metadata (priority, deadline, estimated duration) is grouped and visible
      by default.
- [ ] Existing point, Related points and follow-up policy are behind
      More options.
- [ ] Related points persist on the point; origin point shows read-only when set.
- [ ] From live, a single Add closes the dialog; from preparation,
      Add and continue remains.
- [ ] No horizontal overflow on mobile; no regression in existing point flows.
