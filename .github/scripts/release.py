#!/usr/bin/env python3
"""Prepare, commit, push, and optionally publish an Odoo Meetings release."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDONS = (
    "community_meetings",
    "community_meetings_calendar",
    "community_meetings_project",
    "community_meetings_extension_demo",
)
CHANGELOG = ROOT / "CHANGELOG.md"
RELEASE_FOLLOWUPS = ROOT / "RELEASE_FOLLOWUPS.json"
METAPACKAGE = ROOT / "setup/_metapackage/pyproject.toml"
VERSION_RE = re.compile(r"18\.0\.\d+\.\d+")
RELEASE_HEADING_RE = re.compile(r"^## Odoo Meetings Minutes (18\.0\.\d+\.\d+) \(", re.MULTILINE)
FOLLOWUP_AREAS = {
    "documentation",
    "screenshots",
    "user_surface_inventory",
    "translations",
    "tests_and_validation",
    "migration",
    "security",
    "accessibility",
    "other",
}


def git(*args: str, check: bool = True, capture: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode:
        raise SystemExit(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip() if capture else ""


def parse_version(version: str) -> tuple[int, int, int, int]:
    if not VERSION_RE.fullmatch(version):
        raise SystemExit(f"Invalid suite/module version: {version}")
    return tuple(map(int, version.split(".")))  # type: ignore[return-value]


def next_release_version(latest: str, today: dt.date | None = None) -> str:
    today = today or dt.datetime.now().astimezone().date()
    date_segment = int(today.strftime("%Y%m%d"))
    latest_parts = parse_version(latest)
    if latest_parts[2] > date_segment:
        raise SystemExit("The latest release date is in the future; pass --version explicitly.")
    sequence = latest_parts[3] + 1 if latest_parts[2] == date_segment else 0
    return f"18.0.{date_segment}.{sequence}"


def changelog_release_versions() -> list[str]:
    return RELEASE_HEADING_RE.findall(CHANGELOG.read_text(encoding="utf-8"))


def latest_release_tag() -> str:
    tags = git("tag", "--list", "18.0.*", "v18.0.*").splitlines()
    tagged = [tag for tag in tags if VERSION_RE.fullmatch(normalize_tag(tag))]
    if not tagged:
        raise SystemExit("No 18.0 release tags found; cannot determine the release baseline.")
    return max(tagged, key=lambda tag: parse_version(normalize_tag(tag)))


def normalize_tag(tag: str) -> str:
    return tag.removeprefix("v")


def check_clean_state() -> None:
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("Tracked changes are present. Commit or stash them before preparing a release.")


def check_release_followups() -> None:
    try:
        ledger = json.loads(RELEASE_FOLLOWUPS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read release follow-up ledger {RELEASE_FOLLOWUPS}: {error}") from error
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1:
        raise SystemExit(f"Invalid release follow-up ledger schema in {RELEASE_FOLLOWUPS}.")
    pending = ledger.get("pending")
    if not isinstance(pending, list):
        raise SystemExit(f"The 'pending' field must be a list in {RELEASE_FOLLOWUPS}.")
    for index, item in enumerate(pending, start=1):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("ticket"), str)
            or not item["ticket"].strip()
            or item.get("addon") not in (*ADDONS, "suite")
            or item.get("area") not in FOLLOWUP_AREAS
            or not isinstance(item.get("action"), str)
            or not item["action"].strip()
        ):
            raise SystemExit(f"Invalid pending follow-up #{index} in {RELEASE_FOLLOWUPS}.")
    if pending:
        details = "\n".join(
            f"  - {item['ticket']} [{item['addon']} / {item['area']}]: {item['action']}"
            for item in pending
        )
        raise SystemExit(
            "Release blocked by unresolved follow-ups:\n"
            f"{details}\n"
            "Resolve these items and remove them from RELEASE_FOLLOWUPS.json; "
            "see .github/RELEASE_READINESS.md."
        )


def changed_addons_since(tag: str) -> list[str]:
    paths = git("diff", "--name-only", f"{tag}...HEAD").splitlines()
    changed = set()
    for path in paths:
        addon = path.split("/", 1)[0]
        if addon not in ADDONS:
            continue
        if path.startswith(f"{addon}/readme/newsfragments/"):
            continue
        changed.add(addon)
    return [addon for addon in ADDONS if addon in changed]


def manifest_version(contents: str) -> str:
    manifest = ast.literal_eval(contents)
    return manifest["version"]


def next_addon_version(current: str, previous: str) -> str:
    previous_parts = tuple(map(int, previous.split(".")))
    current_parts = tuple(map(int, current.split(".")))
    if len(previous_parts) != 5 or len(current_parts) != 5:
        raise SystemExit("Expected Odoo addon versions in five-part format.")
    if current_parts < previous_parts:
        raise SystemExit(f"Addon version went backwards from {previous} to {current}.")
    if current_parts == previous_parts:
        current_parts = (*current_parts[:-1], current_parts[-1] + 1)
    return ".".join(map(str, current_parts))


def version_at_tag(tag: str, addon: str) -> str:
    contents = git("show", f"{tag}:{addon}/__manifest__.py")
    return manifest_version(contents)


def bumped_manifest(addon: str, tag: str) -> tuple[str, str]:
    path = ROOT / addon / "__manifest__.py"
    contents = path.read_text(encoding="utf-8")
    previous = manifest_version(git("show", f"{tag}:{addon}/__manifest__.py"))
    current = manifest_version(contents)
    new_version = next_addon_version(current, previous)
    if new_version != current:
        pattern = re.compile(r"(?m)^(\s*['\"]version['\"]\s*:\s*['\"])" + re.escape(current) + r"(['\"])")
        updated, count = pattern.subn(rf"\g<1>{new_version}\g<2>", contents, count=1)
        if count != 1:
            raise SystemExit(f"Could not safely update the version in {path}.")
        path.write_text(updated, encoding="utf-8")
        return current, new_version
    return current, current


def run_precommit_hook(hook: str, files: list[str], manual: bool = False) -> None:
    precommit = shutil.which("pre-commit")
    if not precommit:
        raise SystemExit("pre-commit is required; install the repository's hooks first.")
    command = [precommit, "run", hook]
    if manual:
        command.extend(["--hook-stage", "manual"])
    if files:
        command.extend(["--files", *files])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    print(output, end="")
    if result.returncode == 0:
        return
    if "files were modified by this hook" not in output:
        raise SystemExit(f"Pre-commit hook {hook} failed; release stopped.")

    changed = git("diff", "--name-only").splitlines()
    if not changed:
        raise SystemExit(f"Pre-commit hook {hook} failed without a reviewable diff.")
    git("add", "--", *changed)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise SystemExit(f"Pre-commit hook {hook} did not pass after staging its output.")


def read_release_notes(changelog: str, version: str) -> str:
    heading = f"## Odoo Meetings Minutes {version} ("
    lines = changelog.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(heading)), None)
    if start is None:
        raise SystemExit(f"Could not find release notes for {version}.")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end]).strip() + "\n"


def release_tag_guard(tag: str) -> str:
    versions = changelog_release_versions()
    if not versions:
        raise SystemExit("CHANGELOG.md has no release history.")
    latest_changelog = max(versions, key=parse_version)
    if latest_changelog != normalize_tag(tag):
        raise SystemExit(
            f"Latest changelog release is {latest_changelog}, but latest "
            f"git tag is {tag}. "
            "Publish/tag the existing release before preparing another one."
        )
    return latest_changelog


def pending_prepared_release(tag: str) -> str | None:
    versions = changelog_release_versions()
    if not versions:
        raise SystemExit("CHANGELOG.md has no release history.")
    latest_changelog = max(versions, key=parse_version)
    if latest_changelog == normalize_tag(tag):
        return None
    expected_subject = f"chore(release): prepare {latest_changelog}"
    subject = git("log", "-1", "--format=%s")
    if (
        parse_version(latest_changelog) > parse_version(normalize_tag(tag))
        and subject == expected_subject
        and not git("tag", "--list", latest_changelog)
        and not git("tag", "--list", f"v{latest_changelog}")
    ):
        return latest_changelog
    raise SystemExit(
        f"Latest changelog release is {latest_changelog}, but latest git tag is {tag}. "
        "Publish/tag the existing release before preparing another one."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Suite release version; defaults to today's next sequence")
    parser.add_argument("--dry-run", action="store_true", help="Only report the planned version bumps")
    parser.add_argument("--apply", action="store_true", help="Prepare and commit the release locally")
    parser.add_argument("--push", action="store_true", help="Push the release commit to origin/18.0")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Push and create a GitHub Release, which triggers PyPI publication",
    )
    return parser


def preflight(args: argparse.Namespace) -> tuple[str, str, list[str], bool]:
    if git("branch", "--show-current") != "18.0":
        raise SystemExit("Release preparation must run on branch 18.0.")
    check_clean_state()
    check_release_followups()

    if args.push:
        check_push_target()
    if args.publish:
        check_gh_auth()

    tag = latest_release_tag()
    pending_result = pending_release_plan(args, tag)
    if pending_result:
        return pending_result

    latest = release_tag_guard(tag)
    version = args.version or next_release_version(latest)
    if parse_version(version) <= parse_version(latest):
        raise SystemExit(f"{version} must be newer than the latest release {latest}.")
    if git("tag", "--list", version) or git("tag", "--list", f"v{version}"):
        raise SystemExit(f"Tag {version} already exists.")
    if f"## Odoo Meetings Minutes {version} (" in CHANGELOG.read_text(encoding="utf-8"):
        raise SystemExit(f"{version} is already in CHANGELOG.md.")

    addons = changed_addons_since(tag)
    check_release_prerequisites(addons)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github/scripts/check_towncrier_fragments.py"),
            tag,
            "HEAD",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github/scripts/prepare_release.py"),
            f"--version={version}",
            "--draft",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return version, tag, addons, False


def pending_release_plan(args: argparse.Namespace, tag: str) -> tuple[str, str, list[str], bool] | None:
    pending = pending_prepared_release(tag)
    if not pending:
        return None
    if args.version and args.version != pending:
        raise SystemExit(f"A prepared release {pending} is waiting to be pushed/published.")
    if not (args.push or args.publish or args.dry_run):
        raise SystemExit(f"Release {pending} is already prepared; rerun with --push or --publish.")
    return pending, tag, [], True


def check_release_prerequisites(addons: list[str]) -> None:
    required = ["pre-commit", "towncrier"]
    if addons:
        required.append("pandoc")
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise SystemExit("Release prerequisites missing: " + ", ".join(missing))


def check_push_target() -> None:
    git("fetch", "origin", "18.0:refs/remotes/origin/18.0", "--tags")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/18.0", "HEAD"],
        cwd=ROOT,
        check=False,
    )
    if ancestry.returncode:
        raise SystemExit("origin/18.0 is not an ancestor of HEAD; update the branch first.")


def check_gh_auth() -> None:
    gh = shutil.which("gh")
    if not gh:
        raise SystemExit("GitHub CLI gh is required for --publish.")
    subprocess.run([gh, "auth", "status"], cwd=ROOT, check=True)


def show_plan(version: str, tag: str, addons: list[str]) -> None:
    print(f"Release: {version} (based on {tag})")
    if addons:
        print("Addon versions:")
        for addon in addons:
            previous = version_at_tag(tag, addon)
            current = manifest_version((ROOT / addon / "__manifest__.py").read_text())
            target = next_addon_version(current, previous)
            print(f"  {addon}: {current} -> {target}")
    else:
        print("No addon package changes detected; only the suite metapackage will be released.")

    has_fragments = any(
        fragment for addon in ADDONS for fragment in (ROOT / addon / "readme/newsfragments").glob("*.*.md")
    )
    if not addons and not has_fragments:
        raise SystemExit("No changed addons or release fragments found; nothing to release.")


def release_check_files(tag: str) -> list[str]:
    """Check committed release contents as well as newly staged metadata."""
    committed = git("diff", "--name-only", "--diff-filter=ACMRT", f"{tag}...HEAD").splitlines()
    staged = git("diff", "--cached", "--name-only", "--diff-filter=ACMRT").splitlines()
    return sorted(path for path in set(committed + staged) if (ROOT / path).is_file())


def prepare_commit(version: str, tag: str, addons: list[str]) -> None:
    bumped = []
    for addon in addons:
        old, new = bumped_manifest(addon, tag)
        bumped.append(addon)
        print(f"Prepared {addon} version {old} -> {new}")

    manifest_paths = [f"{addon}/__manifest__.py" for addon in bumped]
    if manifest_paths:
        git("add", "--", *manifest_paths)
        run_precommit_hook("oca-gen-addon-readme", manifest_paths)
        run_precommit_hook("oca-gen-metapackage", manifest_paths)
        run_precommit_hook("oca-gen-addons-table", [], manual=True)

    metapackage_text = METAPACKAGE.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^(version = ")[^"]+("$)',
        rf"\g<1>{version}\g<2>",
        metapackage_text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not safely set the suite metapackage version.")
    METAPACKAGE.write_text(updated, encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github/scripts/prepare_release.py"),
            f"--version={version}",
        ],
        cwd=ROOT,
        check=True,
    )
    git("add", "--", "CHANGELOG.md", "README.md", "setup/_metapackage/pyproject.toml")
    fragment_paths = [f"{addon}/readme/newsfragments" for addon in ADDONS]
    git("add", "-u", "--", *fragment_paths)
    existing_files = release_check_files(tag)
    if existing_files:
        precommit = shutil.which("pre-commit")
        if not precommit:
            raise SystemExit("pre-commit is required to validate the release commit.")
        subprocess.run([precommit, "run", "--files", *existing_files], cwd=ROOT, check=True)
    if not git("diff", "--cached", "--name-only"):
        raise SystemExit("Release preparation produced no changes; refusing an empty commit.")
    git("commit", "-m", f"chore(release): prepare {version}", capture=False)


def push_release() -> None:
    git("push", "origin", "HEAD:refs/heads/18.0", capture=False)


def publish_release(version: str) -> None:
    notes = read_release_notes(CHANGELOG.read_text(encoding="utf-8"), version)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as notes_file:
        notes_file.write(notes)
        notes_path = notes_file.name
    try:
        subprocess.run(
            [
                shutil.which("gh") or "gh",
                "release",
                "create",
                version,
                "--target",
                "18.0",
                "--title",
                version,
                "--notes-file",
                notes_path,
            ],
            cwd=ROOT,
            check=True,
        )
    finally:
        os.unlink(notes_path)


def main() -> int:
    args = build_parser().parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")
    if args.publish:
        args.push = True
    if args.dry_run and (args.apply or args.push):
        raise SystemExit("Use --dry-run by itself, or use --apply/--push/--publish.")
    if not (args.apply or args.push or args.publish):
        args.dry_run = True
    version, tag, addons, pending = preflight(args)
    if pending:
        print(f"Resuming prepared release {version} (based on {tag}).")
        if args.dry_run:
            return 0
        if args.push:
            push_release()
        if args.publish:
            publish_release(version)
        return 0
    execute_plan(args, version, tag, addons)
    return 0


def execute_plan(args: argparse.Namespace, version: str, tag: str, addons: list[str]) -> None:
    show_plan(version, tag, addons)
    if args.dry_run:
        return
    prepare_commit(version, tag, addons)
    if args.push:
        push_release()
    if args.publish:
        publish_release(version)


if __name__ == "__main__":
    raise SystemExit(main())
