"""Authenticated Playwright session for Odoo browser tests."""

from __future__ import annotations

import os
import sys
from urllib.parse import urlencode, urljoin

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


class OdooBrowserSession:
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
            login_url = urljoin(base_url.rstrip("/") + "/", "web/login")
            page.goto(login_url + "?" + urlencode({"db": database}), wait_until="domcontentloaded")
            page.locator('input[name="login"]').fill(login)
            page.locator('input[name="password"]').fill(password)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/odoo**", timeout=30000)
            return session
        except Exception:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
            playwright.stop()
            raise

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
