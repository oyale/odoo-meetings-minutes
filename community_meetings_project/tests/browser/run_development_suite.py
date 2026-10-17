#!/usr/bin/env python3
"""Run the Project browser extension in the existing development database."""

import sys
from pathlib import Path

CORE_BROWSER = Path(__file__).resolve().parents[3] / "community_meetings" / "tests" / "browser"
sys.path.insert(0, str(CORE_BROWSER))
from run_development_suite import main


if __name__ == "__main__":
    raise SystemExit(main(script_path=Path(__file__).with_name("full_project_playwright.py"), project=True))
