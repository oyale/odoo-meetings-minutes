#!/usr/bin/env python3
"""Build the root Markdown changelog with each addon's manifest version."""

import argparse
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "towncrier.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
MIN_TOWNCRIER = (23, 6)


def addon_version(addon):
    manifest = ast.literal_eval((ROOT / addon / "__manifest__.py").read_text())
    return manifest["version"]


def add_version_table(changelog, version):
    heading = f"## Odoo Meetings Minutes {version} ("
    lines = changelog.splitlines()
    index = next((i for i, line in enumerate(lines) if line.startswith(heading)), None)
    if index is None:
        raise SystemExit(f"Towncrier did not generate the {version} heading.")
    sections = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["tool"]["towncrier"]["section"]
    table = [
        "### Addon versions",
        "",
        "| Addon | Odoo module version |",
        "|---|---:|",
    ]
    for section in sections:
        addon = Path(section["path"]).parts[0]
        table.append(f"| {section['name']} | `{addon_version(addon)}` |")
    lines[index + 1 : index + 1] = ["", *table, ""]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines).rstrip()) + "\n"


def towncrier_command():
    command = shutil.which("towncrier")
    if not command:
        raise SystemExit("Towncrier is required; install towncrier==23.11.0.")
    result = subprocess.run([command, "--version"], check=True, capture_output=True, text=True)
    match = re.search(r"(\d+)\.(\d+)", result.stdout)
    if not match or tuple(map(int, match.groups())) < MIN_TOWNCRIER:
        raise SystemExit("Towncrier 23.6 or newer is required for Markdown output.")
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Suite version, e.g. 18.0.20261019.2")
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Preview without writing or removing fragments",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"18\.0\.\d+\.\d+", args.version):
        parser.error("version must match 18.0.<date-or-sequence>.<revision>")
    if not CHANGELOG.is_file():
        raise SystemExit("CHANGELOG.md is missing its release notes history.")
    release_heading = f"## Odoo Meetings Minutes {args.version} ("
    if release_heading in CHANGELOG.read_text(encoding="utf-8"):
        raise SystemExit(f"{args.version} is already in CHANGELOG.md; refusing a duplicate.")

    command = towncrier_command()
    invocation = [command, "build", f"--version={args.version}"]
    if args.draft:
        result = subprocess.run(
            [*invocation, "--draft"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        print(add_version_table(result.stdout, args.version), end="")
    else:
        # Validate Towncrier's rendered heading and the manifest/config data
        # before the non-draft build consumes any news fragments.
        preview = subprocess.run(
            [*invocation, "--draft"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        add_version_table(preview.stdout, args.version)
        subprocess.run([*invocation, "--yes"], cwd=ROOT, check=True)
        CHANGELOG.write_text(
            add_version_table(CHANGELOG.read_text(encoding="utf-8"), args.version),
            encoding="utf-8",
        )


if __name__ == "__main__":
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required (for tomllib).")
    main()
