"""Strict, addon-scoped lookups for translated browser UI strings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .catalog_lookup import CatalogLookup


@lru_cache(maxsize=16)
def _lookup(addons_root: str, language: str):
    return CatalogLookup(Path(addons_root), language)


def ui_text(
    addons_root: Path,
    language: str | None,
    module: str,
    msgid: str,
    *,
    context: str | None = None,
    plural_index: int | None = None,
) -> str:
    """Return source text for English or a strict translation from one addon PO."""
    if not language or language.split("_", 1)[0].lower() == "en":
        return msgid
    lookup = _lookup(str(addons_root.resolve()), language)
    return lookup.translate(module, msgid, context=context, plural_index=plural_index)


def configured_addons_root() -> Path:
    """Return the root of this addon checkout."""
    return Path(__file__).resolve().parents[2]


class LocalizedUI:
    """Shared locale-aware text and selector helpers for browser test suites."""

    def ui_text(self, module, msgid, *, context=None, plural_index=None):
        return ui_text(
            configured_addons_root(),
            self.effective_locale(),
            module,
            msgid,
            context=context,
            plural_index=plural_index,
        )

    def ui_selector(self, module, selector, *msgids):
        """Translate catalog strings embedded in a browser selector."""
        for msgid in msgids:
            selector = selector.replace(msgid, self.ui_text(module, msgid))
        return selector
