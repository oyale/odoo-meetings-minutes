# Carryovers: moving points between meetings (editor)

A **carryover** continues the treatment of a point (or reviews a follow-up, or
moves an agreement) in a later meeting.

## The three ways a point moves

1. **Series policy — Review** *(default)*: when a meeting finishes, its
   unfinished points are offered to the next meeting of the series. Editors
   accept/discard during meeting creation and on the live screen (*Points to
   continue*).
2. **Series policy — Automatic**: same, without asking.
3. **Manual**: from any point, **Postpone → Move to another meeting** opens the
   carryover wizard, whichever the policy.

## The carryover wizard

![Carryover wizard](img/carryover-wizard.png)

- **Destination series** (mandatory for agreements/resolutions) or
  **destination meeting** (for points and follow-ups).
- **Reason** — free text; pre-filled with the postponement reason if any.
- With the Project addon: optionally carry **linked project tasks** (explicitly
  selected).

The destination meeting's editors receive it as *Points to continue* (policy
Review) or find it already in the agenda (policy Automatic). The record shows
origin meeting, context and who answered.

## Accepting / dismissing

- **Accept** — the point joins the destination agenda as a new participation of
  the same point (identity preserved).
- **Dismiss** — the offer is rejected; under policy *Review* it may be offered
  again later, *Discard* in the creation wizard drops it permanently.

## Related docs

- [Series carryover policy](../admin/series.md#policies)
- [Creation wizard, continuing points](prepare-meeting.md#the-guided-wizard)
- [Project tasks inside carryovers](../integrations/project.md)
