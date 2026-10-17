# Optional Time Tracking — Design

Date: 2026-10-17
Status: approved (design), pending implementation plan

Make meeting start/stop and point timers optional. Controlled per company (general settings) with per-series override. When off, timing UI disappears and the live meeting is editable without timers. Current behavior (tracking on) stays the default.

## Decisions (grilled 2026-10-17)

- Q1-A: when off, timing fully hidden — "Finish Meeting" direct from `scheduled`, live notes editable without point timers, no actual-duration display.
- Q2-A: single "time tracking" mode covers both meeting and point timers (point timing requires a started meeting anyway).
- Q3-A: live-read resolution, no copied field on meeting. Standalone meetings follow the company default.

## 1. Model

- `res.company.meeting_time_tracking` — Boolean, default `True`.
- `community.meeting.series.time_tracking` — Selection `inherit | on | off`, default `inherit`.
- `community.meeting.time_tracking_enabled` — computed non-stored Boolean:
  `series.time_tracking == 'inherit' ? company.meeting_time_tracking : series.time_tracking == 'on'`; no series → company flag.
- No change to `actual_*` fields; they keep recording when tracking is on and stay untouched when off.

## 2. Workflow guards (`meeting.py`, `topic.py`)

- `action_start_meeting` / `action_pause_meeting` / `action_resume_meeting`: raise `UserError` when tracking off.
- Point `action_start_timing` / `action_pause_timing`: raise when tracking off.
- `action_mark_held`: unchanged — already supports "never started" (Record as Already Held). With tracking off it is the only path. Its point-timing cleanup is guarded by `actual_started_at`, safe when nothing was ever timed.

## 3. Settings UI

- `res.config.settings` → Meetings app: new block "Time tracking" with the company toggle.
- Series form: `time_tracking` next to `carryover_policy`.
- Series wizard `structure` step: same field (default `inherit`), review step shows it readonly.

## 4. Live view (`live_meeting.js` / `.xml`)

- `get_live_capabilities` returns `time_tracking: bool`.
- When off:
  - Hide Start/Pause/Resume meeting buttons; "Finish Meeting" shown for `scheduled` unconditionally.
  - Hide point timer row (Begin/Pause point, "Point in progress/paused" badges).
  - `canEditDiscussion` = `!locked` (no `actual_started_at` requirement).
  - Hide "Actual start/end/duration" header cells.
  - `navigateItem` skips the pause-running-points sweep.

## 5. Form view (`meeting_views.xml`)

- Start/Pause/Resume buttons: `invisible="not time_tracking_enabled"` (OR-ed with existing conditions).
- `actual_start_datetime`, `actual_end_datetime`, `actual_duration_minutes`: invisible when tracking off.

## 6. Edge cases

- Toggle off mid-meeting: running point timers stay as-is until `action_mark_held` closes them (existing cleanup); UI stops offering timing immediately.
- Toggle back on: meeting without `actual_start_datetime` simply shows Start again; previously recorded partial durations are preserved.
- Reports: revision PDF already shows actual duration only when set — no change.

## 7. Tests (`tests/test_optional_timing.py`)

- Effective-mode resolution: company default, series `on`/`off` override, standalone meeting.
- Server guards: timing actions raise when off.
- `action_mark_held` without prior start succeeds when off.
- `get_live_capabilities` includes the flag.

## Out of scope

- Calendar module changes, per-meeting override field, historical data migration (none needed).

## Implementation surface

| File | Change |
|---|---|
| `models/preparation.py` | company field, settings related, series selection field, meeting compute |
| `models/meeting.py` | guards on start/pause/resume |
| `models/topic.py` | guards on point timing actions |
| `views/preparation_views.xml` | settings block, series form/wizard fields |
| `views/meeting_views.xml` | button/field visibility |
| `static/src/live_meeting/live_meeting.js` + `.xml` | capability flag + conditional rendering |
| `tests/test_optional_timing.py` | new |
