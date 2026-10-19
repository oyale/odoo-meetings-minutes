# Implementation closeout and release readiness

Every implementation must assess the affected product surfaces before it is
closed. Update the relevant source documentation and artifacts in the same
change whenever practical. If a release-relevant follow-up remains, record it
in [`RELEASE_FOLLOWUPS.json`](../RELEASE_FOLLOWUPS.json); do not leave it only
in chat, a plan, or an issue tracker.

## Closeout review

For each changed addon, decide whether the implementation affects:

- user and technical documentation;
- user-guide screenshots or other embedded documentation images;
- `user_surface_inventory/` coverage and its linked follow-ups;
- English and Spanish translations or localized user materials;
- automated tests and the required validation evidence;
- upgrade/migration behavior and compatibility with existing data;
- security/access rules and accessibility/keyboard behavior;
- a Towncrier fragment for each changed addon, as required by `AGENTS.md`.

Complete applicable work as part of the implementation. For an item deferred
to a later change, add one ledger row with a precise, actionable description,
the related ticket or plan, and the affected addon (or `suite`). If an item
does not apply, record the reason in the implementation's ticket or closeout
note; do not add a placeholder ledger row. The inventory remains the canonical
place for user-surface coverage details; the ledger points to a release task
without copying the inventory.

## Release gate

The release helper reads `RELEASE_FOLLOWUPS.json` for every release operation,
including dry runs and resuming an already prepared release. An unreadable,
invalid, or non-empty ledger blocks the release. Resolve each listed action,
verify it, and remove the completed row before retrying. Never remove a row
merely to unblock a release. General backlog entries in
`user_surface_inventory/user_followups.json` do not block a release unless an
implementation records them here as a required release follow-up.

Each row must have this shape:

```json
{
  "ticket": "issue, plan, or change identifier",
  "addon": "community_meetings",
  "area": "screenshots",
  "action": "Replace the preparation dialog screenshot in the English guide"
}
```

Allowed `addon` values are the four release addons and `suite`. Allowed areas
are `documentation`, `screenshots`, `user_surface_inventory`, `translations`,
`tests_and_validation`, `migration`, `security`, `accessibility`, and `other`.
