"""Explicit runtime configuration for the Behave acceptance suite."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

DATABASE_RE = re.compile(r"^[A-Za-z0-9_]{1,63}$")
SUPPORTED_SCOPES = frozenset({"core", "project", "calendar", "all"})


def _actor_credentials(environment: Mapping[str, str], password: str, role: str) -> tuple[str | None, str | None]:
    login = environment.get(f"ODOO_{role.upper()}_LOGIN", "").strip() or None
    actor_password = environment.get(f"ODOO_{role.upper()}_PASSWORD") or None
    if role == "reviewer" and login and not actor_password:
        actor_password = password
    if actor_password and not login:
        raise AcceptanceConfigurationError(f"ODOO_{role.upper()}_PASSWORD requires ODOO_{role.upper()}_LOGIN")
    if role == "reader" and bool(login) != bool(actor_password):
        raise AcceptanceConfigurationError("ODOO_READER_LOGIN and ODOO_READER_PASSWORD must be set together")
    return login, actor_password


def _validate_distinct_actors(editor: str, reviewer: str | None, reader: str | None) -> None:
    if reviewer == editor or reader == editor or (reader and reader == reviewer):
        raise AcceptanceConfigurationError("configured editor, reviewer and reader accounts must be distinct")


class AcceptanceConfigurationError(ValueError):
    """The suite was not explicitly configured for a disposable test target."""


@dataclass(frozen=True)
class AcceptanceConfig:
    base_url: str
    database: str
    login: str
    password: str
    scope: str
    reviewer_login: str | None = None
    reviewer_password: str | None = None
    reader_login: str | None = None
    reader_password: str | None = None
    headful: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> AcceptanceConfig:
        if environment.get("ODOO_ACCEPTANCE_ALLOW_DISPOSABLE") != "1":
            raise AcceptanceConfigurationError(
                "set ODOO_ACCEPTANCE_ALLOW_DISPOSABLE=1 only for a disposable test environment"
            )

        database = environment.get("ODOO_DB", "").strip()
        if not DATABASE_RE.fullmatch(database):
            raise AcceptanceConfigurationError(
                "ODOO_DB must be an explicit database identifier using letters, digits or underscores"
            )

        raw_url = environment.get("ODOO_BASE_URL", "").strip()
        try:
            parsed = urlsplit(raw_url)
            valid_url = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
            )
            # Accessing port validates malformed/out-of-range port values.
            _ = parsed.port
        except ValueError:
            valid_url = False
        if not valid_url:
            raise AcceptanceConfigurationError(
                "ODOO_BASE_URL must be an explicit HTTP(S) URL without embedded credentials, query or fragment"
            )
        base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))

        login = environment.get("ODOO_LOGIN", "").strip()
        password = environment.get("ODOO_PASSWORD", "")
        if not login or not password:
            raise AcceptanceConfigurationError("ODOO_LOGIN and ODOO_PASSWORD are required")

        reviewer_login, reviewer_password = _actor_credentials(environment, password, "reviewer")
        reader_login, reader_password = _actor_credentials(environment, password, "reader")
        _validate_distinct_actors(login, reviewer_login, reader_login)

        scope = environment.get("ODOO_ACCEPTANCE_SCOPE", "").strip().lower()
        if scope not in SUPPORTED_SCOPES:
            raise AcceptanceConfigurationError(
                "ODOO_ACCEPTANCE_SCOPE must be one of: " + ", ".join(sorted(SUPPORTED_SCOPES))
            )

        return cls(
            base_url=base_url,
            database=database,
            login=login,
            password=password,
            scope=scope,
            reviewer_login=reviewer_login,
            reviewer_password=reviewer_password,
            reader_login=reader_login,
            reader_password=reader_password,
            headful=environment.get("PLAYWRIGHT_HEADFUL") == "1",
        )
