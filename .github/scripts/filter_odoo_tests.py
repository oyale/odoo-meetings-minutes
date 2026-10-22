#!/usr/bin/env python3
"""Skip the Odoo test matrix for changes that only affect documentation."""

from __future__ import annotations

import os
import subprocess

ADDONS = (
    "community_meetings",
    "community_meetings_calendar",
    "community_meetings_project",
    "community_meetings_extension_demo",
)
DOCUMENTATION_FILES = {"CHANGELOG.md", "README.md", "README.rst"}
DOCUMENTATION_DIRECTORIES = ("readme/", "static/description/")


def affects_odoo(paths: list[str]) -> bool:
    for path in paths:
        if path in {"LICENSE", ".github/workflows/test.yml"}:
            return True

        for addon in ADDONS:
            prefix = f"{addon}/"
            if not path.startswith(prefix):
                continue

            addon_path = path[len(prefix) :]
            if addon_path in DOCUMENTATION_FILES or addon_path.startswith(DOCUMENTATION_DIRECTORIES):
                continue
            return True

    return False


def changed_paths() -> list[str] | None:
    if os.environ.get("FORCE_TESTS", "").lower() == "true":
        # None means the comparison is unavailable, so the caller runs tests
        # conservatively. A synthetic path would be classified as docs-only.
        return None

    event_name = os.environ.get("EVENT_NAME")
    if event_name == "pull_request":
        base_ref = os.environ.get("PR_BASE")
    elif event_name == "push":
        base_ref = os.environ.get("PUSH_BASE")
    else:
        # Unknown events, including workflow_call, run tests conservatively.
        return None

    if not base_ref or set(base_ref) == {"0"}:
        return None

    base_exists = subprocess.run(
        ["git", "cat-file", "-e", f"{base_ref}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if base_exists.returncode:
        # A force-push can remove the event's previous commit from the checkout.
        # This filter only skips work, so run tests when the comparison is unavailable.
        return None

    output = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRT",
            base_ref,
            os.environ["HEAD_SHA"],
        ],
        text=True,
    )
    return output.splitlines()


def main() -> None:
    paths = changed_paths()
    run_tests = paths is None or affects_odoo(paths)
    message = "Running Odoo test matrix." if run_tests else "Skipping Odoo tests: documentation-only changes."
    print(message)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"run_tests={str(run_tests).lower()}\n")


if __name__ == "__main__":
    main()
