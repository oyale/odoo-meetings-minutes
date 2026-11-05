"""Identify changes requiring the Odoo/OCB matrix.

Shared by the test filter (push/PR gating) and the release publish gate. A
manifest whose only difference is the ``version`` line, and the metapackage
whose only difference is its ``version``, count as non-code. Known lint,
documentation and publication tooling is checked separately; unknown paths
remain conservative, including the Odoo test workflow and shared test helpers.
"""

from __future__ import annotations

import re
import subprocess

import tomllib

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
NON_ODOO_FILES = {
    ".pre-commit-config.yaml",
    ".pre-commit-config.yml",
    ".ruff.toml",
    "ruff.toml",
    "towncrier.toml",
    ".github/dependabot.yml",
    ".github/workflows/pre-commit.yml",
    ".github/workflows/publish-pypi.yml",
    ".github/workflows/docs.yml",
    ".github/scripts/check_towncrier_fragments.py",
    ".github/scripts/filter_odoo_tests.py",
    ".github/scripts/last_code_commit.py",
    ".github/scripts/odoo_code_changes.py",
    ".github/scripts/reuse_release_tests.py",
}
NON_ODOO_DIRECTORIES = (".github/tests/", "towncrier-check/")


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


def normalized_project_config(commit: str, path: str):
    content = git_show(commit, path)
    if content is None:
        return None
    config = tomllib.loads(content)
    tools = config.get("tool", {})
    tools.pop("ruff", None)
    if not tools:
        config.pop("tool", None)
    return config


def project_config_changed(base: str, head: str, path: str) -> bool:
    try:
        return normalized_project_config(base, path) != normalized_project_config(head, path)
    except tomllib.TOMLDecodeError:
        # Unreadable configuration must not suppress Odoo validation.
        return True


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
    return git("diff", "--name-only", "--no-renames", base, head).splitlines()


def has_code_changes(base: str, head: str) -> bool:
    for path in changed_paths(base, head):
        if is_documentation_or_generated(path):
            continue
        if path in NON_ODOO_FILES or path.startswith(NON_ODOO_DIRECTORIES):
            continue
        if path == "pyproject.toml":
            if project_config_changed(base, head, path):
                return True
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
