#!/usr/bin/env python3
"""Reuse complete Odoo/OCB validation, preferring the exact release commit."""

from __future__ import annotations

import json
import os
import subprocess
import time
from urllib.parse import urlencode

REQUIRED_JOBS = {"Test (Odoo)", "Test (OCB)"}


def github_api(endpoint: str, *, paginate: bool = False):
    command = ["gh", "api", endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    return json.loads(subprocess.check_output(command, text=True))


def find_run(repository: str, sha: str):
    query = urlencode({"head_sha": sha, "event": "push", "branch": "18.0", "per_page": 1})
    runs = github_api(f"repos/{repository}/actions/workflows/test.yml/runs?{query}")["workflow_runs"]
    if not runs:
        return None
    run = runs[0]
    if run["head_sha"] != sha:
        raise RuntimeError("GitHub returned a Tests run for a different commit")
    return run


def wait_for_run(repository: str, run):
    while run["status"] != "completed":
        print(f"Waiting for Tests run {run['id']} at {run['head_sha']}.", flush=True)
        time.sleep(15)
        run = github_api(f"repos/{repository}/actions/runs/{run['id']}")
    return run


def reusable_tests(repository: str, candidates: list[str]) -> bool:
    # A release can arrive before its push-triggered Tests run is registered.
    for attempt in range(12):
        found_run = False
        for sha in candidates:
            run = find_run(repository, sha)
            if run is None:
                continue
            found_run = True
            run = wait_for_run(repository, run)
            if run["conclusion"] != "success":
                print(f"Tests run {run['id']} concluded {run['conclusion']}; running the release suite.")
                return False
            pages = github_api(
                f"repos/{repository}/actions/runs/{run['id']}/jobs?filter=latest&per_page=100",
                paginate=True,
            )
            tests = [job for page in pages for job in page["jobs"] if job["name"] in REQUIRED_JOBS]
            if any(job["conclusion"] not in {"success", "skipped"} for job in tests):
                print(f"Tests run {run['id']} has an unsuccessful required job; running the release suite.")
                return False
            passed = {job["name"] for job in tests if job["conclusion"] == "success"}
            if REQUIRED_JOBS <= passed:
                print(f"Reusing Tests run {run['id']} at {sha}: Odoo and OCB passed.")
                return True
            print(f"Tests run {run['id']} did not execute both Odoo and OCB; checking the next candidate.")
        if found_run:
            break
        if attempt < 11:
            time.sleep(10)
    print("No reusable Tests run; running the release suite.")
    return False


def main() -> None:
    candidates = list(dict.fromkeys([os.environ["RELEASE_SHA"], os.environ["CODE_COMMIT"]]))
    passed = reusable_tests(os.environ["REPOSITORY"], candidates)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"passed={str(passed).lower()}\n")


if __name__ == "__main__":
    main()
