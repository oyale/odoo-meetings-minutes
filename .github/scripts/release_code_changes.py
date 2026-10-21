#!/usr/bin/env python3
"""Detect product/code changes in the commit named by a release tag."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ADDONS = (
    "community_meetings",
    "community_meetings_calendar",
    "community_meetings_project",
    "community_meetings_extension_demo",
)
MANIFEST_VERSION = re.compile(
    r"(?m)^(\s*['\"]version['\"]\s*:\s*)['\"][^'\"]+['\"](,?\s*)$"
)
METAPACKAGE_VERSION = re.compile(r'(?m)^version = "[^"]+"$')


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def normalized_manifest(commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    return MANIFEST_VERSION.sub(r"\1<version>\2", result.stdout)


def normalized_metapackage(commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    return METAPACKAGE_VERSION.sub('version = "<version>"', result.stdout)


def is_documentation_or_generated(path: str) -> bool:
    if path in {"CHANGELOG.md", "README.md"} or path.startswith("docs/"):
        return True
    for addon in ADDONS:
        prefix = f"{addon}/"
        if not path.startswith(prefix):
            continue
        relative = path.removeprefix(prefix)
        return (
            relative in {"CHANGELOG.md", "README.md", "README.rst"}
            or relative.startswith(("readme/", "docs/", "static/description/"))
        )
    return False


def has_code_changes(tag: str) -> bool:
    commit = git("rev-parse", f"{tag}^{{commit}}")
    parents = git("rev-list", "--parents", "-n", "1", commit).split()
    if len(parents) < 2:
        return True
    parent = parents[1]
    # Include deletions too: removing executable code is still a code change.
    paths = git("diff", "--name-only", parent, commit).splitlines()

    for path in paths:
        if is_documentation_or_generated(path):
            continue
        if path.endswith("/__manifest__.py"):
            if normalized_manifest(parent, path) == normalized_manifest(commit, path):
                continue
            return True
        if path == "setup/_metapackage/pyproject.toml":
            if normalized_metapackage(parent, path) == normalized_metapackage(commit, path):
                continue
            return True
        return True
    return False


def main() -> None:
    tag = os.environ["RELEASE_TAG"]
    changed = has_code_changes(tag)
    print("Release commit changes code; the test suite is required." if changed else "Release commit only changes release metadata/docs.")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"code_changed={str(changed).lower()}\n")


if __name__ == "__main__":
    main()
