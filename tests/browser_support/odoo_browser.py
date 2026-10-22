"""Authenticated Playwright session for Odoo browser tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from browser_support.ui_text import LocalizedUI


def normalize_locale(locale: str | None) -> str | None:
    """Normalize locale separators while preserving the complete locale code."""
    if not locale:
        return None
    parts = locale.replace("-", "_").split("_")
    if len(parts) == 1:
        return parts[0].lower()
    return "_".join([parts[0].lower(), parts[1].upper(), *parts[2:]])


class OdooBrowserSession(LocalizedUI):
    """Own one browser context, authenticated page and Odoo JSON-RPC session."""

    def __init__(
        self,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
        page: Page,
        base_url: str,
        database: str,
    ) -> None:
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.console_errors: list[str] = []
        self._effective_locale: str | None = None
        self.page.on("pageerror", lambda error: self.console_errors.append(str(error)))
        self.page.on(
            "console",
            lambda message: self.console_errors.append(message.text) if message.type == "error" else None,
        )

    @classmethod
    def login(
        cls,
        base_url: str,
        database: str,
        login: str,
        password: str,
        *,
        headless: bool = True,
        viewport: dict[str, int] | None = None,
        has_touch: bool = False,
    ) -> OdooBrowserSession:
        if not all((base_url, database, login, password)):
            raise ValueError("base URL, database, login, and password are required")
        playwright = sync_playwright().start()
        browser = None
        context = None
        try:
            disable_sandbox = os.getenv("ODOO_BROWSER_NO_SANDBOX", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            chromium_args = ["--no-sandbox"] if disable_sandbox and sys.platform.startswith("linux") else []
            browser = playwright.chromium.launch(
                headless=headless,
                args=chromium_args,
            )
            context = browser.new_context(
                viewport=viewport or {"width": 1440, "height": 1000},
                has_touch=has_touch,
            )
            page = context.new_page()
            session = cls(playwright, browser, context, page, base_url, database)
            session.authenticate(login, password)
            return session
        except Exception:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
            playwright.stop()
            raise

    def _login_url(self) -> str:
        login_url = urljoin(self.base_url + "/", "web/login")
        return login_url + "?" + urlencode({"db": self.database})

    def authenticate(self, login: str, password: str) -> None:
        """Authenticate this browser context as an Odoo user."""
        if not login or not password:
            raise ValueError("login and password are required")
        self.page.goto(self._login_url(), wait_until="domcontentloaded")
        self.page.locator('input[name="login"]').fill(login)
        self.page.locator('input[name="password"]').fill(password)
        self.page.locator('button[type="submit"]').click()
        self.page.wait_for_url("**/odoo**", timeout=30000)

    def logout_and_clear_cookies(self) -> None:
        """Invalidate the server session and leave a clean database login page."""
        logout_url = urljoin(self.base_url + "/", "web/session/logout")
        self.page.goto(
            logout_url + "?" + urlencode({"redirect": self._login_url()}),
            wait_until="domcontentloaded",
        )
        self.context.clear_cookies()
        if any(cookie["name"] == "session_id" for cookie in self.context.cookies(self.base_url)):
            raise AssertionError("Odoo session_id cookie remains after clearing browser cookies")
        self.page.goto(self._login_url(), wait_until="domcontentloaded")
        self.page.locator('input[name="login"]').wait_for(state="visible", timeout=10000)

    def session_info(self) -> dict:
        response = self.page.request.post(
            urljoin(self.base_url + "/", "web/session/get_session_info"),
            data={"jsonrpc": "2.0", "method": "call", "params": {}, "id": 1},
        )
        payload = response.json()
        if response.status != 200 or payload.get("error"):
            raise AssertionError(f"Odoo session info failed: {payload.get('error', payload)!r}")
        return payload["result"]

    def effective_locale(self) -> str | None:
        """Return the authenticated Odoo user locale, cached for this login."""
        if self._effective_locale is None:
            self._effective_locale = self.session_info().get("user_context", {}).get("lang")
        return self._effective_locale

    def verify_locale(self, expected: str) -> str:
        """Require the authenticated session and rendered document to use expected."""
        wanted = normalize_locale(expected)
        info = self.session_info()
        actual = normalize_locale(info.get("user_context", {}).get("lang"))
        rendered = normalize_locale(info.get("bundle_params", {}).get("lang"))
        document = normalize_locale(self.page.locator("html").get_attribute("lang"))
        if actual != wanted or rendered != wanted or document != wanted:
            diagnostic_dir = Path(os.environ.get("MM_PLAYWRIGHT_SCREENSHOT_DIR", "/tmp/meeting-playwright"))
            diagnostic_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            diagnostic_dir.chmod(0o700)
            stem = f"locale-mismatch-{wanted or 'unknown'}-{os.getpid()}"
            (diagnostic_dir / f"{stem}.html").write_text(
                self.page.locator("html").evaluate("element => element.outerHTML"), encoding="utf-8"
            )
            self.page.screenshot(path=str(diagnostic_dir / f"{stem}.png"), full_page=True)
            raise AssertionError(
                f"Expected browser locale {wanted!r}, got session={actual!r}, "
                f"translation bundle={rendered!r}, html[lang]={document!r}. "
                f"console errors={self.console_errors!r}. "
                f"Rendered DOM and screenshot: {diagnostic_dir / stem}.*"
            )
        return wanted

    def switch_user(self, login: str, password: str) -> None:
        """Log out, clear all browser cookies, and authenticate another configured user."""
        self.logout_and_clear_cookies()
        self.authenticate(login, password)
        info = self.session_info()
        actual_login = info.get("username")
        if actual_login != login:
            raise AssertionError(f"Expected authenticated user {login!r}, got {actual_login!r}.")
        self._effective_locale = info.get("user_context", {}).get("lang")
        self.verify_locale(self._effective_locale or "")

    def new_page(self) -> Page:
        page = self.context.new_page()
        page.on("pageerror", lambda error: self.console_errors.append(str(error)))
        page.on(
            "console",
            lambda message: self.console_errors.append(message.text) if message.type == "error" else None,
        )
        return page

    def rpc(
        self,
        model: str,
        method: str,
        args: list,
        kwargs: dict | None = None,
        *,
        page: Page | None = None,
    ):
        request_page = page or self.page
        endpoint = urljoin(
            self.base_url + "/",
            f"web/dataset/call_kw/{model}/{method}",
        )
        response = request_page.request.post(
            endpoint,
            data={
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "model": model,
                    "method": method,
                    "args": args,
                    "kwargs": kwargs or {},
                },
                "id": 1,
            },
        )
        payload = response.json()
        if response.status != 200 or payload.get("error"):
            raise AssertionError(f"Odoo RPC failed: {payload.get('error', payload)!r}")
        return payload["result"]

    def record(self, model: str, record_id: int, fields: list[str], *, page: Page | None = None):
        return self.rpc(model, "read", [[record_id], fields], page=page)[0]

    def close(self) -> None:
        try:
            self.context.close()
        finally:
            try:
                self.browser.close()
            finally:
                self.playwright.stop()
