#!/usr/bin/env python3
"""Resolve the commits that can validate the release's Odoo code/environment.

Walks the first-parent chain from the tagged commit; the first commit that
changes code (or a root commit) is printed. A release commit that only bumps
versions or updates docs resolves to the last commit whose code actually
changed, whose test run validates the release's code. The GitHub-output mode
also exposes intervening equivalent commits: their push runs may contain the
successful matrix even when the code-changing commit has no separate run.
"""

from __future__ import annotations

import argparse
import json
import os

from odoo_code_changes import git, has_code_changes

MAX_WALK = 50


def first_parent(commit: str) -> str | None:
    parents = git("rev-list", "--parents", "-n", "1", commit).split()
    return parents[1] if len(parents) >= 2 else None


def equivalent_commits(commit: str) -> list[str]:
    candidates = []
    for _ in range(MAX_WALK):
        candidates.append(commit)
        parent = first_parent(commit)
        if parent is None or has_code_changes(parent, commit):
            return candidates
        commit = parent
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    tag = os.environ["RELEASE_TAG"]
    candidates = equivalent_commits(git("rev-parse", f"{tag}^{{commit}}"))
    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"code_commit={candidates[-1]}\n")
            output.write(f"equivalent_commits={json.dumps(candidates)}\n")
    else:
        print(candidates[-1])


if __name__ == "__main__":
    main()
