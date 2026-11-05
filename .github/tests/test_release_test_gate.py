"""Exercise the publication gate through its workflow command and GitHub API seam."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RELEASE_SHA = "a" * 40
CODE_SHA = "b" * 40

FAKE_GH = r"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

root = Path(os.environ["GATE_FIXTURE"])
fixture = json.loads((root / "fixture.json").read_text())
endpoint = next(arg for arg in sys.argv if arg.startswith("repos/"))
with (root / "requests.jsonl").open("a") as stream:
    stream.write(json.dumps(endpoint) + "\n")
if any(marker in endpoint for marker in fixture.get("errors", [])):
    raise SystemExit("GitHub API unavailable")
if "/workflows/test.yml/runs?" in endpoint:
    sha = parse_qs(urlsplit(endpoint).query)["head_sha"][0]
    result = {"workflow_runs": fixture["runs"].get(sha, [])}
elif "/jobs" in endpoint:
    run_id = endpoint.split("/runs/", 1)[1].split("/", 1)[0]
    pages = fixture.get("job_pages", {}).get(run_id, [fixture["jobs"].get(run_id, [])])
    result = [{"jobs": jobs} for jobs in pages] if "--slurp" in sys.argv else {"jobs": pages[0]}
else:
    run_id = endpoint.rsplit("/", 1)[-1]
    result = fixture.get("details", {}).get(run_id)
    if result is None:
        result = next(run for runs in fixture["runs"].values() for run in runs if str(run["id"]) == run_id)
print(json.dumps(result))
"""


def successful_run(sha, run_id=101):
    return {"id": run_id, "head_sha": sha, "status": "completed", "conclusion": "success"}


def successful_jobs():
    return [
        {"name": "changes", "conclusion": "success"},
        {"name": "Test (Odoo)", "conclusion": "success"},
        {"name": "Test (OCB)", "conclusion": "success"},
    ]


class ReleaseTestGateTests(unittest.TestCase):
    def run_gate(
        self, runs, jobs, *, details=None, job_pages=None, errors=None, succeeds=True, equivalent_commits=None
    ):
        workflow = yaml.safe_load((ROOT / ".github/workflows/publish-pypi.yml").read_text())
        command = next(step["run"] for step in workflow["jobs"]["tests_gate"]["steps"] if step.get("id") == "gate")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.json").write_text(
                json.dumps(
                    {
                        "runs": runs,
                        "jobs": jobs,
                        "details": details or {},
                        "job_pages": job_pages or {},
                        "errors": errors or [],
                    }
                )
            )
            # Mock only the external clock; the workflow command and API client run normally.
            (root / "sitecustomize.py").write_text("import time\ntime.sleep = lambda seconds: None\n")
            (root / "gh").write_text(f"#!{sys.executable}\n" + FAKE_GH)
            (root / "gh").chmod(0o755)
            (root / "sleep").write_text("#!/bin/sh\nexit 0\n")
            (root / "sleep").chmod(0o755)
            (root / "python").symlink_to(sys.executable)
            output = root / "output"
            environment = {
                **os.environ,
                "PATH": str(root) + os.pathsep + os.environ["PATH"],
                "GATE_FIXTURE": str(root),
                "PYTHONPATH": str(root),
                "GITHUB_OUTPUT": str(output),
                "REPOSITORY": "owner/repo",
                "RELEASE_SHA": RELEASE_SHA,
                "CODE_COMMIT": CODE_SHA,
                "EQUIVALENT_COMMITS": json.dumps(equivalent_commits if equivalent_commits is not None else []),
            }
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            if succeeds:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            else:
                self.assertNotEqual(result.returncode, 0)
            log_path = root / "requests.jsonl"
            requests = [json.loads(row) for row in log_path.read_text().splitlines()] if log_path.exists() else []
            return output.read_text() if output.exists() else "", requests, result.stdout

    def test_reuses_the_release_sha_when_the_code_commit_has_no_run(self):
        output, requests, _log = self.run_gate(
            {RELEASE_SHA: [successful_run(RELEASE_SHA)]}, {"101": successful_jobs()}
        )
        self.assertEqual(output, "passed=true\n")
        self.assertIn("head_sha=" + RELEASE_SHA, requests[0])
        self.assertFalse(any("head_sha=" + CODE_SHA in request for request in requests))

    def test_waits_for_the_exact_release_run_before_using_an_older_success(self):
        pending = {**successful_run(RELEASE_SHA), "status": "in_progress", "conclusion": None}
        output, requests, _log = self.run_gate(
            {RELEASE_SHA: [pending], CODE_SHA: [successful_run(CODE_SHA, 102)]},
            {"101": successful_jobs(), "102": successful_jobs()},
            details={"101": successful_run(RELEASE_SHA)},
        )
        self.assertEqual(output, "passed=true\n")
        self.assertTrue(any(request.endswith("/runs/101") for request in requests))
        self.assertFalse(any("head_sha=" + CODE_SHA in request for request in requests))

    def test_falls_back_to_the_code_commit_when_the_release_run_is_absent(self):
        output, requests, _log = self.run_gate({CODE_SHA: [successful_run(CODE_SHA)]}, {"101": successful_jobs()})
        self.assertEqual(output, "passed=true\n")
        self.assertIn("head_sha=" + RELEASE_SHA, requests[0])
        self.assertIn("head_sha=" + CODE_SHA, requests[1])

    def test_skipped_release_matrices_can_use_complete_code_commit_tests(self):
        output, _requests, _log = self.run_gate(
            {RELEASE_SHA: [successful_run(RELEASE_SHA)], CODE_SHA: [successful_run(CODE_SHA, 102)]},
            {"101": [{"name": "changes", "conclusion": "success"}], "102": successful_jobs()},
        )
        self.assertEqual(output, "passed=true\n")

    def test_neither_matrix_can_be_missing_skipped_or_failed(self):
        for name in ("Test (Odoo)", "Test (OCB)"):
            for conclusion in (None, "skipped", "failure"):
                with self.subTest(name=name, conclusion=conclusion):
                    jobs = [job for job in successful_jobs() if job["name"] != name]
                    if conclusion is not None:
                        jobs.append({"name": name, "conclusion": conclusion})
                    output, _requests, _log = self.run_gate(
                        {RELEASE_SHA: [successful_run(RELEASE_SHA)]}, {"101": jobs}
                    )
                    self.assertEqual(output, "passed=false\n")

    def test_failed_or_cancelled_release_run_cannot_be_hidden_by_older_success(self):
        for conclusion in ("failure", "cancelled", "timed_out"):
            with self.subTest(conclusion=conclusion):
                run = {**successful_run(RELEASE_SHA), "conclusion": conclusion}
                output, requests, _log = self.run_gate(
                    {RELEASE_SHA: [run], CODE_SHA: [successful_run(CODE_SHA, 102)]},
                    {"101": successful_jobs(), "102": successful_jobs()},
                )
                self.assertEqual(output, "passed=false\n")
                self.assertFalse(any("head_sha=" + CODE_SHA in request for request in requests))

    def test_collects_both_required_jobs_across_paginated_responses(self):
        output, _requests, _log = self.run_gate(
            {RELEASE_SHA: [successful_run(RELEASE_SHA)]},
            {},
            job_pages={"101": [[successful_jobs()[1]], [successful_jobs()[2]]]},
        )
        self.assertEqual(output, "passed=true\n")

    def test_no_registered_runs_falls_back_to_running_the_release_suite(self):
        output, _requests, _log = self.run_gate({}, {})
        self.assertEqual(output, "passed=false\n")

    def test_api_errors_fail_closed_without_accepting_tests(self):
        output, _requests, _log = self.run_gate({}, {}, errors=["/workflows/test.yml/runs"], succeeds=False)
        self.assertNotIn("passed=true", output)

    def test_a_run_for_a_different_commit_is_rejected(self):
        output, _requests, _log = self.run_gate(
            {RELEASE_SHA: [successful_run(CODE_SHA)]}, {"101": successful_jobs()}, succeeds=False
        )
        self.assertNotIn("passed=true", output)

    def test_reuses_validation_on_an_intermediate_code_equivalent_commit(self):
        intermediate = "c" * 40
        output, requests, _log = self.run_gate(
            {RELEASE_SHA: [successful_run(RELEASE_SHA)], intermediate: [successful_run(intermediate, 102)]},
            {"101": [{"name": "changes", "conclusion": "success"}], "102": successful_jobs()},
            equivalent_commits=[RELEASE_SHA, intermediate, CODE_SHA],
        )
        self.assertEqual(output, "passed=true\n")
        self.assertFalse(any("head_sha=" + CODE_SHA in request for request in requests))

    def test_equivalent_candidates_must_match_the_resolved_boundaries(self):
        for candidates in (
            [RELEASE_SHA, "c" * 40],
            ["c" * 40, CODE_SHA],
            "not-a-list",
            [RELEASE_SHA, "g" * 40, CODE_SHA],
        ):
            with self.subTest(candidates=candidates):
                output, requests, _log = self.run_gate(
                    {},
                    {},
                    equivalent_commits=candidates,
                    succeeds=False,
                )
                self.assertNotIn("passed=true", output)
                self.assertEqual(requests, [])

    def test_workflow_supplies_the_release_and_code_commit_to_the_gate(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/publish-pypi.yml").read_text())
        gate = next(step for step in workflow["jobs"]["tests_gate"]["steps"] if step.get("id") == "gate")
        self.assertEqual(gate["env"]["RELEASE_SHA"], "${{ github.sha }}")
        self.assertEqual(gate["env"]["CODE_COMMIT"], "${{ steps.resolve.outputs.code_commit }}")
        self.assertEqual(gate["env"]["EQUIVALENT_COMMITS"], "${{ steps.resolve.outputs.equivalent_commits }}")


if __name__ == "__main__":
    unittest.main()
