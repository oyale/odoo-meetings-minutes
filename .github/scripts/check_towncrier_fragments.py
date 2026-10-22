#!/usr/bin/env python3
"""Require a Towncrier news fragment for each changed addon."""

import subprocess
import sys

ADDONS = {
    "community_meetings": "towncrier-check/community_meetings.toml",
    "community_meetings_calendar": "towncrier-check/community_meetings_calendar.toml",
    "community_meetings_project": "towncrier-check/community_meetings_project.toml",
    "community_meetings_extension_demo": ("towncrier-check/community_meetings_extension_demo.toml"),
}


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: check_towncrier_fragments.py BASE_REF HEAD_REF", file=sys.stderr)
        return 2

    base_ref, head_ref = sys.argv[1:]
    changed_paths = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", base_ref, head_ref],
        text=True,
    ).splitlines()

    # Correcting generated history must not create a duplicate release fragment.
    changed_addons = [
        (addon, config)
        for addon, config in ADDONS.items()
        if any(path.startswith(f"{addon}/") and path != f"{addon}/CHANGELOG.md" for path in changed_paths)
    ]

    if not changed_addons:
        print("No addon files changed; Towncrier fragment checks are not needed.")
        return 0

    for addon, config in changed_addons:
        print(f"Checking {addon} news fragment against {base_ref}...")
        result = subprocess.run(
            [
                "towncrier",
                "check",
                f"--config={config}",
                "--dir=.",
                f"--compare-with={base_ref}",
            ],
            check=False,
        )
        if result.returncode:
            return result.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
