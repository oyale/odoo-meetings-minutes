#!/usr/bin/env python3
"""Print the nearest commit at or before the release tag that changes Odoo code.

Walks the first-parent chain from the tagged commit; the first commit that
changes code (or a root commit) is printed. A release commit that only bumps
versions or updates docs resolves to the last commit whose code actually
changed, whose test run validates the release's code.
"""

from __future__ import annotations

import os

from odoo_code_changes import git, has_code_changes

MAX_WALK = 50


def first_parent(commit: str) -> str | None:
    parents = git("rev-list", "--parents", "-n", "1", commit).split()
    return parents[1] if len(parents) >= 2 else None


def main() -> None:
    tag = os.environ["RELEASE_TAG"]
    commit = git("rev-parse", f"{tag}^{{commit}}")
    for _ in range(MAX_WALK):
        parent = first_parent(commit)
        if parent is None or has_code_changes(parent, commit):
            print(commit)
            return
        commit = parent
    # No code-changing commit found within the walk; treat the last one as code
    # so the caller runs tests conservatively.
    print(commit)


if __name__ == "__main__":
    main()
