[![Odoo 18.0](https://img.shields.io/badge/Odoo-18.0-714B67.svg)](https://github.com/oyale/odoo-meetings-minutes/tree/18.0)
[![Tests](https://github.com/oyale/odoo-meetings-minutes/actions/workflows/test.yml/badge.svg?branch=18.0)](https://github.com/oyale/odoo-meetings-minutes/actions/workflows/test.yml?query=branch%3A18.0)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-2f6f9f)](https://oyale.github.io/odoo-meetings-minutes/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
<!-- /!\ do not modify above this line -->

Meeting Minutes
===============

Odoo 18 addons for preparing, running and documenting community meetings. The
suite keeps agenda points, discussion outcomes and follow-up work connected
across meetings, with optional Project and Calendar integrations.

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[community_meetings](community_meetings/) | 18.0.6.2.1 | [![oyale](https://github.com/oyale.png?size=30px)](https://github.com/oyale) | Operational meetings, agendas, resolutions and minutes
[community_meetings_calendar](community_meetings_calendar/) | 18.0.1.0.0 | [![oyale](https://github.com/oyale.png?size=30px)](https://github.com/oyale) | Create private Calendar invitations for scheduled community meetings
[community_meetings_extension_demo](community_meetings_extension_demo/) | 18.0.1.0.0 | [![oyale](https://github.com/oyale.png?size=30px)](https://github.com/oyale) | Synthetic example of meeting-kind and snapshot extension hooks
[community_meetings_project](community_meetings_project/) | 18.0.3.1.1 | [![oyale](https://github.com/oyale.png?size=30px)](https://github.com/oyale) | Link existing Odoo Project tasks to meetings

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Installation

Add this repository's `addons` directory to the Odoo `addons_path`, update the
Apps list, and install **Community Meetings**. Install either integration addon
when its Odoo application is available. The extension demo is optional.

For pip-based deployments, each addon is packaged independently:

```console
pip install 'odoo-addon-community_meetings==18.0.*'
pip install 'odoo-addon-community_meetings-project==18.0.*'
pip install 'odoo-addon-community_meetings-calendar==18.0.*'
pip install 'odoo-addon-community_meetings-extension-demo==18.0.*'
```

The repository metapackage installs the full suite:

```console
pip install odoo-meetings-minutes
```

## Documentation

Read the [English guide](https://oyale.github.io/odoo-meetings-minutes/html-en/index.html)
or [guía en español](https://oyale.github.io/odoo-meetings-minutes/html-es/index.html).
See the [changelog](CHANGELOG.md)
for user-facing changes between releases.

## Preparing a release

After bumping the versions of changed addons in their manifests, refresh the
addon version table in this README. Stage the changed manifest files first so
the generator reads their new versions:

```console
pre-commit run oca-gen-addons-table --hook-stage manual
```

If the command updates this README, pre-commit reports that change on the first
run. Review and stage the generated table, then rerun the command to confirm it
passes.

Then use Python 3.11 or newer and Towncrier 23.6 or newer to prepare the
changelog. Preview it, then run the same command without `--draft` to write
`CHANGELOG.md` and remove the consumed news fragments:

```console
python3.11 .github/scripts/prepare_release.py \
  --version 18.0.<date-or-sequence>.<revision> --draft
python3.11 .github/scripts/prepare_release.py \
  --version 18.0.<date-or-sequence>.<revision>
```

Commit the changelog, manifest versions, generated addon table, and fragment
removals together before tagging the release. The preparation command refuses
to add the same release version twice.
GitHub Pages builds the bilingual user and administrator documentation from
`docs/user/` and `docs/user_es/` on every push to `18.0`.
See [ROADMAP.md](ROADMAP.md) for planned user-facing improvements.

## License

This repository is licensed under AGPL-3.0. See [LICENSE](LICENSE).
