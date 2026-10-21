"""Shared policy for named screenshots produced by Playwright browser tests."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.") or "capture"


def _configured_viewports() -> list[dict[str, Any]]:
    raw = os.environ.get("MM_PLAYWRIGHT_SCREENSHOT_VIEWPORTS", "")
    if not raw:
        return []
    try:
        viewports = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("MM_PLAYWRIGHT_SCREENSHOT_VIEWPORTS must contain a JSON list") from error
    if not isinstance(viewports, list):
        raise ValueError("MM_PLAYWRIGHT_SCREENSHOT_VIEWPORTS must contain a JSON list")
    for viewport in viewports:
        if (
            not isinstance(viewport, dict)
            or not isinstance(viewport.get("name"), str)
            or type(viewport.get("width")) is not int
            or type(viewport.get("height")) is not int
            or viewport["width"] < 1
            or viewport["height"] < 1
        ):
            raise ValueError("each screenshot viewport needs name, positive width and height")
    return viewports


def capture_checkpoint(
    page,
    name: str,
    test_id: str,
    locale: str,
    viewport: dict[str, int] | None = None,
    capture_target=None,
) -> list[Path]:
    """Capture a named visual checkpoint according to the current run settings."""
    if os.environ.get("MM_PLAYWRIGHT_SCREENSHOTS", "checkpoints").lower() in {
        "off", "0", "false", "no"
    }:
        return []

    selected = {
        value.strip()
        for value in os.environ.get("MM_PLAYWRIGHT_SCREENSHOT_NAMES", "").split(",")
        if value.strip()
    }
    if selected and name not in selected:
        return []

    root = Path(
        os.environ.get("MM_PLAYWRIGHT_SCREENSHOT_DIR", "/tmp/meeting-playwright")
    )
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = root / _safe_name(test_id)
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.chmod(0o700)

    original = page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
    viewports = _configured_viewports()
    if not viewports:
        size = viewport or original
        viewports = [{"name": "custom" if viewport else "current", **size}]
    paths = []
    try:
        for size in viewports:
            page.set_viewport_size({"width": size["width"], "height": size["height"]})
            filename = "{}-{}-{}-{}x{}.png".format(
                _safe_name(name), _safe_name(locale), _safe_name(size["name"]),
                size["width"], size["height"],
            )
            path = target / filename
            if capture_target is None:
                page.screenshot(path=str(path), full_page=True)
            else:
                capture_target.screenshot(path=str(path))
            path.chmod(0o600)
            paths.append(path)
    finally:
        page.set_viewport_size(original)
    return paths


def capture_failure(page, test_id: str) -> Path | None:
    """Save the current page after a failed browser test, unless captures are off."""
    if os.environ.get("MM_PLAYWRIGHT_SCREENSHOTS", "checkpoints").lower() in {
        "off", "0", "false", "no"
    }:
        return None
    root = Path(
        os.environ.get("MM_PLAYWRIGHT_SCREENSHOT_DIR", "/tmp/meeting-playwright")
    )
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = root / _safe_name(test_id)
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.chmod(0o700)
    size = page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
    path = target / f"failure-current-{size['width']}x{size['height']}.png"
    page.screenshot(path=str(path), full_page=True)
    path.chmod(0o600)
    return path
