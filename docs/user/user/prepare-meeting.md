# Preparing a meeting (editor)

Two entry points: the **New Meeting** wizard (guided) or opening a series and
pressing **New Meeting** there (same wizard, series pre-selected).

![Meetings list](img/meetings-list.png)

## The guided wizard

The wizard walks six steps; *Back/Next* are free, your edits are kept when
changing series.

1. **Series** — pick one, or leave empty for a standalone meeting. A button
   *Use series defaults* loads duration and attendees. Changing the series
   re-applies its defaults without losing what you typed.
2. **When** — start date/time, title (pre-filled with the series pattern
   `{date} {series}`) and duration. End time is derived.
3. **People** — attendees (pre-filled from the series).
4. **Continuing points** — if the series carryover policy is *Review*, the
   points carried from previous meetings appear here: **Accept** to include,
   **Postpone** to keep them offered for later, **Discard** to drop them
   permanently. If the policy is *Automatic* they are already included.
5. **Agenda** — add points now (or later). Reuse an existing point of the
   series via *More options → Existing point*.
6. **Review** — a summary of everything; **Create Meeting** finishes.

> **Tip:** The wizard copies series defaults; it does not link to them. Changing the
> series afterwards does not rewrite the meeting.

## Reading a meeting (reader track)

Readers open meetings from **Meetings → Meetings** (or the calendar). They see
the agenda with outcomes, discussion notes, published dissents, agreements,
follow-ups and — once approved — the minutes with a **PDF** download button on
the *Approved Revisions* tab. Everything is read-only.

## Adding points

On the meeting form, **Add Point** opens a focused dialog:

- **Title** — one clear line, this is what attendees read.
- **Point type** — decides the live behavior (see [catalogs](../admin/catalogs.md#agenda-point-types)).
- **Description** — rich text: context, links, documents.
- **Planning** — choose a priority (Low-key, Normal, High or Critical), use a
  minute preset or enter a custom estimate, and optionally set a deadline. The
  estimate is pre-filled from the series or company default.
- **Responsible** — choose who will present the point. You can also link
  related points in the main form.
- **More options** — reuse an existing point and adjust its follow-up rules.

The **Add and continue** button chains several points quickly.

> **Note:** Whether *Add Point* is available depends on the meeting state and the
> **adding-points policy** of its series — it disappears after the deadline and
> the server enforces it too.

The **estimated agenda over budget** warning appears when the sum of point
estimates exceeds the meeting duration. Plan or trim.

![Add point wizard with priority, estimated time and optional deadline](img/point-wizard.png)

## Scheduling and series changes

- **Schedule** confirms the meeting (requires a start date) and publishes the
  calendar event.
- The series can be changed while the meeting is *draft or scheduled* and live
  execution has not started. Points shared with other meetings constrain the
  move.
- **Cancel** is available in draft/scheduled.

## Access tab

Editors can grant **reader**/**editor** access on meetings they organize;
managers can also change the organizer, secretary and access of any meeting.

Next: run it live → [Live meeting](live-meeting.md).
