# Changelog

User-facing changes to the Odoo Meetings Minutes suite. Each release records
the exact Odoo addon version included in the published suite packages.
History below starts at `18.0.20261018.2`; earlier releases are not backfilled.

<!-- towncrier release notes start -->
## Odoo Meetings Minutes 18.0.20261019.2 (2026-10-19)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| Community Meetings | `18.0.6.2.2` |
| Calendar Integration | `18.0.1.0.1` |
| Project Integration | `18.0.3.1.2` |
| Extension Demo | `18.0.1.0.0` |

### Community Meetings

#### Bugfixes

- Preserve execution-evidence checks supplied by addons when validating resolved TODOs.

### Calendar Integration

No user-facing changes.

### Project Integration

#### Bugfixes

- Serialize task deletion with TODO closure so a resolved TODO keeps its required Project task.

### Extension Demo

No significant changes.

## Odoo Meetings Minutes 18.0.20261019.1 (2026-10-19)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| Community Meetings | `18.0.6.2.1` |
| Calendar Integration | `18.0.1.0.0` |
| Project Integration | `18.0.3.1.1` |
| Extension Demo | `18.0.1.0.0` |

### Community Meetings

#### Features

- The Add Point wizard offers visual agenda type cards with behavior guidance. The New Meeting and New Series wizards group choices with contextual help, clear field labels, and scannable reviews.
- The meeting creation review warns when the selected agenda, including automatic points, exceeds the estimated meeting duration.

### Calendar Integration

No significant changes.

### Project Integration

#### Features

- The Project task wizard now shows the linked follow-up's title, owners and deadline as read-only context, and separates existing task selection from creating a new task.

### Extension Demo

No significant changes.

## Odoo Meetings Minutes 18.0.20261018.2 (2026-10-18)

### Addon versions

| Addon | Odoo module version |
|---|---:|
| Community Meetings | `18.0.6.2.0` |
| Calendar Integration | `18.0.1.0.0` |
| Project Integration | `18.0.3.1.0` |
| Extension Demo | `18.0.1.0.0` |

### Community Meetings

#### Features

- Added a dedicated Community Meetings icon to the Odoo app launcher.
- The point preparation form keeps priority, estimated duration and deadline together, makes related points available in the main flow, and reserves advanced options for reusing a point and configuring follow-ups. The description editor is highlighted so its purpose is clear while drafting.

#### Misc

- point-wizard-icon-labels

### Calendar Integration

No significant changes.

### Project Integration

No significant changes.

### Extension Demo

No significant changes.
