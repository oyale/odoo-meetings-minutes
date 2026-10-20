"""Helpers for explicit role accounts in multi-actor acceptance scenarios."""


def login_as_configured_actor(context, role: str):
    config = context.acceptance_config
    login = getattr(config, f"{role}_login")
    password = getattr(config, f"{role}_password") or config.password
    if not login or not password:
        raise AssertionError(f"This scenario requires configured ODOO_{role.upper()}_LOGIN")
    session = context.browser_session
    session.page.goto(f"{config.base_url}/web/session/logout?redirect=/web/login?db={config.database}")
    session.page.locator('input[name="login"]').fill(login)
    session.page.locator('input[name="password"]').fill(password)
    session.page.locator('button[type="submit"]').click()
    session.page.wait_for_url("**/odoo**", timeout=30000)
    return session
