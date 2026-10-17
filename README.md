# Meeting Minutes

Odoo 18 addons for preparing, running and documenting community meetings.
The suite keeps agenda points, discussion outcomes and follow-up work connected
across meetings, with optional Project and Calendar integrations.

[![Odoo 18.0](https://img.shields.io/badge/Odoo-18.0-714B67.svg)](https://github.com/oyale/meeting-minutes/tree/18.0)
[![Tests](https://github.com/oyale/meeting-minutes/actions/workflows/test.yml/badge.svg?branch=18.0)](https://github.com/oyale/meeting-minutes/actions/workflows/test.yml?query=branch%3A18.0)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-2f6f9f)](https://oyale.github.io/meeting-minutes/)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)

## Addons

| Addon | Description | Dependencies |
|---|---|---|
| [`community_meetings`](community_meetings/) | Meeting series, agendas, resolutions, follow-ups, minutes and approvals. | `base`, `web`, `web_editor`, `mail` |
| [`community_meetings_project`](community_meetings_project/) | Link agenda follow-ups to Odoo Project tasks and configure task policies. | `community_meetings`, `project` |
| [`community_meetings_calendar`](community_meetings_calendar/) | Synchronize scheduled meetings with private Odoo Calendar events and invitations. | `community_meetings`, `calendar` |
| [`community_meetings_extension_demo`](community_meetings_extension_demo/) | Minimal example of extending meeting behavior. | `community_meetings` |

## Installation

Add this repository's `addons` directory to the Odoo `addons_path`, update the
Apps list, and install **Community Meetings**. Install either integration addon
when its Odoo application is available. The extension demo is optional.

For pip-based deployments, each addon is packaged independently:

```console
pip install odoo-addon-community_meetings==18.0.*
pip install odoo-addon-community_meetings-project==18.0.*
pip install odoo-addon-community_meetings-calendar==18.0.*
pip install odoo-addon-community_meetings-extension-demo==18.0.*
```

The repository metapackage installs the full suite:

```console
pip install odoo-addons-oyale-meeting-minutes
```

## Documentation

Read the [English guide](https://oyale.github.io/meeting-minutes/html-en/index.html)
or [guía en español](https://oyale.github.io/meeting-minutes/html-es/index.html).
GitHub Pages builds the bilingual user and administrator documentation from
`docs/user/` and `docs/user_es/` on every push to `18.0`.

## Development

The addons follow OCA repository conventions for manifests, packaging and
continuous integration. Run the Odoo test suite with the standard OCA CI tools
or use the reusable Playwright checks in each addon's `tests/browser/` directory
against a disposable test database. See each generated addon README for details.

## License

This repository is licensed under AGPL-3.0-or-later. See [LICENSE](LICENSE).
