#!/usr/bin/env python3
"""Skip the Odoo matrix for documentation, versions and known non-Odoo tooling.

Used by the Tests workflow on push and pull_request to decide whether the Odoo
test matrix must run. Lint and publication changes use their own checks; addon,
test-environment and unknown paths run the matrix. When comparison is unavailable (force, unknown
event, missing base), run tests conservatively.
"""

from __future__ import annotations

import os
import subprocess

from odoo_code_changes import has_code_changes


def changed_refs() -> tuple[str, str] | None:
    if os.environ.get("FORCE_TESTS", "").lower() == "true":
        # None means the comparison is unavailable, so the caller runs tests
        # conservatively.
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

    return base_ref, os.environ["HEAD_SHA"]


def main() -> None:
    refs = changed_refs()
    run_tests = refs is None or has_code_changes(*refs)
    message = "Running Odoo test matrix." if run_tests else "Skipping Odoo tests: no Odoo or test-environment changes."
    print(message)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"run_tests={str(run_tests).lower()}\n")


if __name__ == "__main__":
    main()
