# Concepts and vocabulary

Everything in this guide uses the vocabulary below. Words are lowercase in the
interface but capitalized here when defined.

<div class="concept-map" id="concept-map" role="group" aria-label="How series, meetings, points, minutes and follow-ups relate">
  <div class="concept-setup-map">
    <div class="concept-origins">
      <article class="concept-node">
        <span class="concept-map-label">Recurring meetings</span>
        <strong>Series</strong>
        <p>Defaults and policies copied into each new meeting.</p>
      </article>
      <article class="concept-node concept-standalone">
        <span class="concept-map-label">One meeting</span>
        <strong>A standalone meeting</strong>
        <p>No series.</p>
      </article>
    </div>
    <div class="concept-map-arrow"><span>creates</span><b aria-hidden="true">→</b></div>
    <article class="concept-node concept-meeting-node">
      <span class="concept-map-label">Scheduled event</span>
      <strong>Meeting</strong>
      <div class="concept-meeting-meta"><span>Date and people</span><span>Agenda</span></div>
    </article>
  </div>

  <div class="concept-map-rule"><span>Agenda</span></div>
  <div class="concept-point-map">
    <div class="concept-case">
      <article class="concept-node concept-identity-node">
        <span class="concept-map-label">One participation</span>
        <strong>Point X</strong>
        <p>Title · description · presenter</p>
      </article>
      <div class="concept-map-arrow concept-case-arrow"><b aria-hidden="true">→</b></div>
      <article class="concept-node concept-participation">
        <span class="concept-map-label">Meeting A</span>
        <strong>Participation</strong>
        <p>Discussion, outcome and time.</p>
      </article>
    </div>
    <div class="concept-case">
      <article class="concept-node concept-identity-node">
        <span class="concept-map-label">Several participations</span>
        <strong>Point Y</strong>
        <p>Title · description · presenter</p>
      </article>
      <div class="concept-map-arrow concept-case-arrow"><b aria-hidden="true">→</b></div>
      <div class="concept-case-participations">
        <article class="concept-node concept-participation">
          <span class="concept-map-label">Meeting A</span>
          <strong>Participation</strong>
          <p>Discussion and outcome.</p>
        </article>
        <article class="concept-node concept-participation">
          <span class="concept-map-label">Meeting B</span>
          <strong>Participation</strong>
          <p>New discussion and outcome.</p>
        </article>
      </div>
    </div>
  </div>

  <div class="concept-map-outputs">
    <article class="concept-output">
      <span class="concept-map-label">Meeting record</span>
      <strong>Minutes → approved revision + PDF</strong>
      <p>The meeting's notes and point outcomes make up its formal record.</p>
    </article>
    <article class="concept-output">
      <span class="concept-map-label">Action item</span>
      <strong>Follow-up → assigned people</strong>
      <p>An open point can be carried into a later agenda; its next participation gets its own record too.</p>
    </article>
  </div>
</div>

## Core objects

### Meeting
A concrete event with a date, duration, attendees and an agenda. It follows a
lifecycle (see [States](#meeting-states)). Each meeting belongs to one
**company** and, optionally, to one **series**.

<div class="object-diagram" role="img" aria-label="A meeting contains agenda items and produces approved minutes">
  <div class="object-diagram-node"><strong>Meeting</strong><small>Date · attendees</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-branches">
    <div class="object-diagram-node"><strong>Agenda items</strong><small>Points for this meeting</small></div>
    <div class="object-diagram-node"><strong>Minutes</strong><small>Approved revision</small></div>
  </div>
</div>

### Series
A recurring meeting template: who coordinates it, its default attendees,
duration, timezone, naming pattern and — most importantly — its **policies**
(how points continue between meetings, whether time is tracked, when points can
be added, follow-up rules). Series *defaults are copied* into each new meeting:
changing the series later never rewrites existing meetings.

<div class="object-diagram" role="img" aria-label="Series defaults are copied into each new meeting">
  <div class="object-diagram-node"><strong>Series</strong><small>Defaults · policies</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-branches">
    <div class="object-diagram-node"><strong>Meeting A</strong><small>Values copied at creation</small></div>
    <div class="object-diagram-node"><strong>Meeting B</strong><small>Values copied at creation</small></div>
  </div>
</div>

### Point
A subject with its own identity that can be treated across **several meetings**.
The point holds the durable information: title, description, presenter,
priority, deadline, links to other points. It keeps a state of its own
(`open`, discussed, closed, proposed…) that survives across meetings.

<div class="object-diagram" role="img" aria-label="A point keeps its identity and state">
  <div class="object-diagram-node object-diagram-record"><strong>Point X</strong><small>Title · presenter</small><small>Priority · deadline</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Point state</strong><small>Open · discussed · closed</small></div>
</div>

### Participation (agenda item)
One participation links a point to one meeting. It stores what happened
*that day*: its discussion notes, its outcome (agreements, postponement…), the
time spent on it. When this guide says "a point in the agenda", it means a
participation.

<div class="object-diagram" role="img" aria-label="A point and meeting define one agenda participation">
  <div class="object-diagram-node"><strong>Point X</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">+</span>
  <div class="object-diagram-node"><strong>Meeting A</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Participation</strong><small>Notes · outcome · time</small></div>
</div>

### Agreement (resolution)
A documented decision produced in a meeting. On **decision** points the
agreement carries the *approved/rejected* result. Agreements have rich-text
bodies and can be withdrawn during the live meeting.

<div class="object-diagram" role="img" aria-label="A decision point is documented by an agreement with a result">
  <div class="object-diagram-node"><strong>Decision point</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Agreement</strong><small>Decision text</small><small>Approved / rejected</small></div>
</div>

### Dissent and reservations
A recorded objection or reservation, with a reason catalog, the person
expressing it, and a flag to include it in the minutes or keep it internal.

<div class="object-diagram" role="img" aria-label="A dissent can be included in the minutes or kept internal">
  <div class="object-diagram-node object-diagram-record"><strong>Dissent</strong><small>Author · reason · statement</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-branches">
    <div class="object-diagram-node"><strong>Include in minutes</strong></div>
    <div class="object-diagram-node"><strong>Keep internal</strong></div>
  </div>
</div>

### Follow-up
The durable record of "who has to do what": responsible people, deadline and an
execution mechanism — an Odoo **activity**, a native **To-do**, or (with the
Project addon) a **project task**. Follow-ups are born from points and keep
traceability to their origin.

<div class="object-diagram" role="img" aria-label="A point can lead to a follow-up assigned to people and tracked in an execution tool">
  <div class="object-diagram-node"><strong>Point</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Follow-up</strong><small>Responsible people · deadline</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Activity / To-do / Project task</strong></div>
</div>

### Minutes
The written record of the meeting. During the meeting the *live screen* feeds
them; when the meeting is **Held** they are formalized, and an **Approver**
freezes them into an immutable **revision** (with a PDF snapshot).

<div class="object-diagram" role="img" aria-label="Meeting content becomes an immutable approved minutes revision and PDF">
  <div class="object-diagram-node"><strong>Meeting content</strong><small>Notes · outcomes</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Minutes draft</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Approved revision</strong><small>Snapshot · PDF</small></div>
</div>

### Carryover
The act of including an already-existing point in a later meeting to continue
its treatment or to review a follow-up. Carryovers can be proposed
automatically by the series policy or requested manually.

<div class="object-diagram" role="img" aria-label="A carryover keeps its source and creates a new agenda item in a later meeting">
  <div class="object-diagram-node"><strong>Source record</strong><small>Point · agreement · follow-up</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Carryover</strong><small>Reason · destination</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>New agenda item</strong><small>Later meeting</small></div>
</div>

## Meeting states

| State | Meaning |
|---|---|
| **Draft** | Being prepared. Points can be added (subject to the series policy). |
| **Scheduled** | Date confirmed. It appears on calendars and participants get context. |
| **In progress** *(display)* | The scheduled meeting has actually started. Not a separate stored state — the badge and the live screen reflect it. |
| **Held** | The meeting took place; time to write the formal minutes. |
| **Minutes draft** | Minutes are being written/adjusted before approval. |
| **Approved** | Minutes are frozen. Content becomes read-only; changes require a new **amendment** revision. |
| **Cancelled** | The meeting will not happen. |

> **Note:** With **time tracking off** (see [series policies](admin/series.md#policies)),
> there is no "Start Meeting" step: a scheduled meeting goes straight to
> **Finish**, and the live screen is editable from the beginning.

## Point outcomes

Each participation ends with one outcome:

| Outcome | Where it comes from |
|---|---|
| **Discussed** | Information/discussion points that were covered. |
| **Agreement (approved / rejected)** | Decision points with a recorded agreement. |
| **Postponed** | Not treated; optionally moved to another meeting (carryover). |
| **Closed (resolved)** | Discussion/TODO points that finished. |
| **Will be reviewed at the next meeting** | Explicit flag, typical for follow-ups. |

## Two special points

Series can automatically add two structural points to every meeting:

- **Minutes approval** (first item): lists previous meetings whose minutes are
  pending approval. Reserving 5 minutes per pending acta.
- **Next meeting** (last item): proposes the next date using the series rule
  (weekday, day of month, or every N days). Reserves 5 minutes.
