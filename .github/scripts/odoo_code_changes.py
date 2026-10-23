"""Classify commits as Odoo code changes vs. documentation/version-only changes.

Shared by the test filter (push/PR gating) and the release publish gate. A
manifest whose only difference is the ``version`` line, and the metapackage
whose only difference is its ``version``, count as non-code.
"""

from __future__ import annotations

import re
import subprocess

ADDONS = (
    "community_meetings",
    "community_meetings_calendar",
    "community_meetings_project",
    "community_meetings_extension_demo",
)

MANIFEST_VERSION = re.compile(r"(?m)^(\s*['\"]version['\"]\s*:\s*)['\"][^'\"]+['\"](,?\s*)$")
METAPACKAGE_VERSION = re.compile(r'(?m)^version = "[^"]+"$')

DOCUMENTATION_FILES = {"CHANGELOG.md", "README.md", "README.rst"}
DOCUMENTATION_DIRECTORIES = ("readme/", "docs/", "static/description/")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def git_show(commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def normalized_manifest(commit: str, path: str) -> str | None:
    content = git_show(commit, path)
    if content is None:
        return None
    return MANIFEST_VERSION.sub(r"\1<version>\2", content)


def normalized_metapackage(commit: str, path: str) -> str | None:
    content = git_show(commit, path)
    if content is None:
        return None
    return METAPACKAGE_VERSION.sub('version = "<version>"', content)


def is_documentation_or_generated(path: str) -> bool:
    if path in DOCUMENTATION_FILES or path.startswith("docs/"):
        return True
    for addon in ADDONS:
        prefix = f"{addon}/"
        if not path.startswith(prefix):
            continue
        relative = path[len(prefix) :]
        return relative in DOCUMENTATION_FILES or relative.startswith(DOCUMENTATION_DIRECTORIES)
    return False


def changed_paths(base: str, head: str) -> list[str]:
    # Include deletions: removing code is still a code change.
    return git("diff", "--name-only", base, head).splitlines()


def has_code_changes(base: str, head: str) -> bool:
    for path in changed_paths(base, head):
        if is_documentation_or_generated(path):
            continue
        if path.endswith("/__manifest__.py"):
            if normalized_manifest(base, path) == normalized_manifest(head, path):
                continue
            return True
        if path == "setup/_metapackage/pyproject.toml":
            if normalized_metapackage(base, path) == normalized_metapackage(head, path):
                continue
            return True
        return True
    return False
