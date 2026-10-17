# Series configuration (manager / editor)

A **series** is a recurring meeting template. Everything configured here is
copied into new meetings at creation time — later edits do not affect existing
meetings.

Location: **Meetings → Meeting Series**. The creation wizard (*New* in the
series list) asks the same information in steps: basics → schedule → structure
→ review.

![Series form](img/series-form.png)

## Header: What and People

| Field | Meaning |
|---|---|
| **Kind** | Type of meetings this series holds (from the Meeting Kinds catalog). |
| **Company** | Owner company (multi-company only). |
| **Active** | Archived series keep their meetings but disappear from lists and menus. |
| **Coordinators** | Users responsible for preparing the meetings of this series. |
| **Default attendees** | People invited to every new meeting; still changeable per meeting. |

## Purpose

Free rich-text description, handy for newcomers. It is shown read-only on each
meeting as *Series description*.

## Scheduling

| Field | Meaning |
|---|---|
| **Default duration** | Planned length of each meeting. |
| **Timezone** | Used to propose the next meeting date unambiguously. |
| **New meeting name pattern** | E.g. `{date} {series}` → "2026-11-08 Community assembly". Tokens: `{date}`, `{series}`. |

## Agenda structure

| Field | Meaning |
|---|---|
| **Minutes approval point** | Adds a first agenda point to approve previous minutes. Only appears when there are pending actas. Reserve: 5 minutes per pending acta. |
| **Next meeting point** | Adds a last agenda point to set the next date. Reserves 5 minutes. |
| **Next meeting default** | Rule to pre-fill that date: *next weekday* (always Tuesday), *day of month*, or *after N days*. |

## Policies

This tab decides how the series behaves. Every value can stay on
**Company default**.

### Unfinished points (carryover policy)

| Value | Behavior |
|---|---|
| **Review** *(default)* | Unfinished points are offered to the next meeting; an editor accepts or discards each one. |
| **Automatic** | Unfinished points continue into the next meeting without asking. |
| **Manual** | Nobody offers anything automatically; someone moves each point explicitly (*Move to another meeting*). |

### Time tracking

| Value | Behavior |
|---|---|
| **Company default** | Whatever Settings say. The effective company value is shown inline. |
| **On** | Timers and actual durations for this series' meetings. |
| **Off** | No start/pause timers: the live meeting is editable from the start; only the finish is recorded. |

### Adding points

| Value | Behavior |
|---|---|
| **Company default** | Follows *Settings → Adding points*. |
| **Draft only** | Points only while preparing the meeting. |
| **Before it starts** | Also once scheduled, until it begins. |
| **While it runs** | Also while the meeting is in progress, until it finishes. |

### Point estimates

| Field | Meaning |
|---|---|
| **Default point estimate (minutes)** | Pre-filled estimate for new points of this series. Empty → company value (shown next to it). |

Minutes-approval and next-meeting structural points ignore this value: they
reserve 5 minutes each (5 per pending acta for approvals).

### Role names

Optional overrides of the coordination/secretary labels for this series only.

### Follow-ups

| Field | Meaning |
|---|---|
| **Allowed follow-up types** | Types new points of this series may use. |
| **Default follow-up type** | Pre-selected type. |
| **Default activity type** | For follow-ups recorded as Odoo activities. |

With the Project addon, a **Follow-up and Task Policy** page is added here —
see [Project](../integrations/project.md#task-policy).

## Buttons and proposals

- **New Meeting** — opens the meeting creation wizard pre-loaded with this series.
- **Propose a point** — opens the proposal wizard targeted at this series.
- The **Proposals to review** alert (editors only) appears under the title when
  there are pending proposals, with Accept/Reject buttons — see
  [Propose a point](../user/propose-a-point.md).

## Meetings tab

Read-only list of this series' meetings, newest first, with state badges.
Open one to work on it.
