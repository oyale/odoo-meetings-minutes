"""Exercise Odoo test classification using real commits and the workflow CLIs."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MANIFEST = """{
    "name": "Fixture",
    "version": "18.0.1.0.0",
    "depends": ["base"],
}
"""


class OdooTestFilterTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.area = Path(area.name)
        self.root = self.area / "repository"
        self.root.mkdir()
        self.environment = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        self.git("init", "-q", "--initial-branch=18.0")
        self.git("config", "user.name", "CI fixture")
        self.git("config", "user.email", "ci@example.invalid")
        self.initial = self.commit(
            {
                "community_meetings/models/meeting.py": "VALUE = 1\n",
                "community_meetings/__manifest__.py": MANIFEST,
                "pyproject.toml": "[tool.ruff]\nline-length = 119\n",
                "setup/_metapackage/pyproject.toml": '[project]\nversion = "18.0.20261105.0"\n',
            }
        )

    def git(self, *arguments):
        return subprocess.check_output(
            ["git", *arguments], cwd=self.root, env=self.environment, text=True, stderr=subprocess.PIPE
        ).strip()

    def commit(self, files):
        for name, content in files.items():
            path = self.root / name
            if content is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        self.git("add", "--all")
        self.git("commit", "-qm", "Fixture change")
        return self.git("rev-parse", "HEAD")

    def run_filter(self, base, head, *, event="push", force=False):
        output = self.area / "output"
        output.write_text("")
        environment = {
            **self.environment,
            "EVENT_NAME": event,
            "PUSH_BASE": base,
            "PR_BASE": base,
            "HEAD_SHA": head,
            "FORCE_TESTS": str(force).lower(),
            "GITHUB_OUTPUT": str(output),
        }
        subprocess.run(
            [sys.executable, str(SCRIPTS / "filter_odoo_tests.py")],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        return output.read_text()

    def test_dependabot_lint_update_does_not_run_odoo(self):
        head = self.commit({".pre-commit-config.yaml": "repos: []\n"})
        self.assertEqual(self.run_filter(self.initial, head), "run_tests=false\n")

    def test_publish_gate_and_its_tests_do_not_run_odoo(self):
        head = self.commit(
            {
                ".github/scripts/reuse_release_tests.py": "print('gate')\n",
                ".github/tests/test_release_test_gate.py": "# Gate regression\n",
                ".github/workflows/pre-commit.yml": "name: Lint\n",
                ".github/workflows/publish-pypi.yml": "name: Publish\n",
            }
        )
        self.assertEqual(self.run_filter(self.initial, head), "run_tests=false\n")

    def test_known_lint_and_documentation_tools_skip_the_matrix(self):
        for name in (
            ".github/dependabot.yml",
            ".github/workflows/docs.yml",
            ".github/scripts/check_towncrier_fragments.py",
            ".github/scripts/filter_odoo_tests.py",
            ".github/scripts/last_code_commit.py",
            ".github/scripts/odoo_code_changes.py",
            ".ruff.toml",
            "ruff.toml",
            "towncrier.toml",
            "towncrier-check/community_meetings.toml",
            "docs/user/guide.md",
            "community_meetings/readme/USAGE.md",
        ):
            with self.subTest(name=name):
                base = self.git("rev-parse", "HEAD")
                head = self.commit({name: "# Tooling or documentation change\n"})
                self.assertEqual(self.run_filter(base, head), "run_tests=false\n")

    def test_addon_runtime_tests_and_test_environment_changes_still_run(self):
        for name in (
            "community_meetings/models/meeting.py",
            "community_meetings/views/meeting_views.xml",
            "community_meetings/static/src/live_meeting/live_meeting.js",
            "community_meetings/tests/test_workflow.py",
            "community_meetings/security/rules.xml",
            ".github/workflows/test.yml",
            ".github/workflows/acceptance.yml",
            "tests/browser_support/meeting.py",
            "requirements.txt",
            "unknown-tool.py",
        ):
            with self.subTest(name=name):
                base = self.git("rev-parse", "HEAD")
                head = self.commit({name: "# Runtime, tests or unknown change\n"})
                self.assertEqual(self.run_filter(base, head), "run_tests=true\n")

    def test_lint_change_cannot_hide_a_runtime_change(self):
        head = self.commit(
            {
                ".pre-commit-config.yaml": "repos: []\n",
                "community_meetings/models/meeting.py": "VALUE = 2\n",
            }
        )
        self.assertEqual(self.run_filter(self.initial, head), "run_tests=true\n")

    def test_version_only_changes_skip_but_manifest_dependencies_run(self):
        version = self.commit(
            {
                "community_meetings/__manifest__.py": MANIFEST.replace("18.0.1.0.0", "18.0.1.0.1"),
                "setup/_metapackage/pyproject.toml": '[project]\nversion = "18.0.20261105.1"\n',
            }
        )
        self.assertEqual(self.run_filter(self.initial, version), "run_tests=false\n")
        dependencies = self.commit(
            {
                "community_meetings/__manifest__.py": MANIFEST.replace('["base"]', '["base", "mail"]'),
            }
        )
        self.assertEqual(self.run_filter(version, dependencies), "run_tests=true\n")

    def test_ruff_only_project_config_skips_but_build_config_runs(self):
        ruff = self.commit({"pyproject.toml": "[tool.ruff]\nline-length = 100\n"})
        self.assertEqual(self.run_filter(self.initial, ruff), "run_tests=false\n")
        build = self.commit({"pyproject.toml": '[build-system]\nrequires = ["whool"]\n'})
        self.assertEqual(self.run_filter(ruff, build), "run_tests=true\n")
        invalid = self.commit({"pyproject.toml": "[invalid\n"})
        self.assertEqual(self.run_filter(build, invalid), "run_tests=true\n")

    def test_deleted_runtime_code_still_runs(self):
        head = self.commit({"community_meetings/models/meeting.py": None})
        self.assertEqual(self.run_filter(self.initial, head), "run_tests=true\n")

    def test_moving_runtime_code_into_docs_still_runs(self):
        head = self.commit(
            {
                "community_meetings/models/meeting.py": None,
                "docs/old_model.py": "VALUE = 1\n",
            }
        )
        self.assertEqual(self.run_filter(self.initial, head), "run_tests=true\n")

    def test_pr_uses_the_same_classification(self):
        head = self.commit({".pre-commit-config.yaml": "repos: []\n"})
        self.assertEqual(self.run_filter(self.initial, head, event="pull_request"), "run_tests=false\n")

    def test_force_unknown_event_or_missing_comparison_runs_conservatively(self):
        head = self.commit({".pre-commit-config.yaml": "repos: []\n"})
        self.assertEqual(self.run_filter(self.initial, head, force=True), "run_tests=true\n")
        self.assertEqual(self.run_filter(self.initial, head, event="workflow_call"), "run_tests=true\n")
        self.assertEqual(self.run_filter("0" * 40, head), "run_tests=true\n")
        self.assertEqual(self.run_filter("f" * 40, head), "run_tests=true\n")

    def test_release_candidates_stop_at_the_last_odoo_change(self):
        code = self.commit({"community_meetings/models/meeting.py": "VALUE = 2\n"})
        tooling = self.commit({".pre-commit-config.yaml": "repos: []\n"})
        metadata = self.commit(
            {
                "community_meetings/__manifest__.py": MANIFEST.replace("18.0.1.0.0", "18.0.1.0.1"),
            }
        )
        self.git("tag", "fixture-release", metadata)
        output = self.area / "resolve-output"
        environment = {**self.environment, "RELEASE_TAG": "fixture-release", "GITHUB_OUTPUT": str(output)}
        legacy = subprocess.check_output(
            [sys.executable, str(SCRIPTS / "last_code_commit.py")],
            cwd=self.root,
            env=environment,
            text=True,
        ).strip()
        self.assertEqual(legacy, code)
        subprocess.run(
            [sys.executable, str(SCRIPTS / "last_code_commit.py"), "--github-output"],
            cwd=self.root,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertTrue(output.exists(), "resolver must expose the safe equivalent candidates to the workflow")
        values = dict(row.split("=", 1) for row in output.read_text().splitlines())
        self.assertEqual(values["code_commit"], code)
        self.assertEqual(json.loads(values["equivalent_commits"]), [metadata, tooling, code])

    def test_test_environment_change_is_a_release_validation_boundary(self):
        environment_change = self.commit({".github/workflows/test.yml": "name: Changed Odoo environment\n"})
        head = self.commit({".pre-commit-config.yaml": "repos: []\n"})
        self.git("tag", "fixture-release", head)
        resolved = subprocess.check_output(
            [sys.executable, str(SCRIPTS / "last_code_commit.py")],
            cwd=self.root,
            env={**self.environment, "RELEASE_TAG": "fixture-release"},
            text=True,
        ).strip()
        self.assertEqual(resolved, environment_change)


if __name__ == "__main__":
    unittest.main()
