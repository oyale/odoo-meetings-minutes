"""Strict gettext lookup for browser tests, independent of project tooling."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class _Entry:
    context: str | None = None
    msgid: str | None = None
    plural: str | None = None
    translations: dict[int, str] = field(default_factory=dict)


def _decode_po_string(path: Path, number: int, raw: str) -> str:
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError) as error:
        raise ValueError(f"{path}:{number}: invalid PO string: {error}") from error
    if not isinstance(value, str):
        raise TypeError(f"{path}:{number}: PO field is not a string")
    return value


def _apply_po_field(
    entry: _Entry, name: str, index: int | None, value: str
) -> None:
    if name == "msgctxt":
        entry.context = value
    elif name == "msgid":
        entry.msgid = value
    elif name == "msgid_plural":
        entry.plural = value
    else:
        entry.translations[index or 0] = value


def _append_po_continuation(entry: _Entry, name: str, index: int | None, value: str) -> None:
    if name == "msgctxt":
        entry.context = (entry.context or "") + value
    elif name == "msgid":
        entry.msgid = (entry.msgid or "") + value
    elif name == "msgid_plural":
        entry.plural = (entry.plural or "") + value
    else:
        entry.translations[index or 0] = entry.translations.get(index or 0, "") + value


def _parse_po(path: Path) -> list[_Entry]:
    entries: list[_Entry] = []
    entry = _Entry()
    active: tuple[str, int | None] | None = None

    def finish() -> None:
        nonlocal entry, active
        if entry.msgid is not None:
            entries.append(entry)
        entry = _Entry()
        active = None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read catalog {path}: {error}") from error

    field_re = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr)(?:\[(\d+)\])?\s+(".*")$')
    for number, line in enumerate(lines, 1):
        if not line.strip():
            finish()
            continue
        if line.startswith("#"):
            continue
        match = field_re.match(line)
        if match:
            name, raw_index, raw_value = match.groups()
            index = int(raw_index) if raw_index is not None else None
            value = _decode_po_string(path, number, raw_value)
            _apply_po_field(entry, name, index, value)
            active = name, index
            continue
        if line.startswith('"') and active:
            name, index = active
            value = _decode_po_string(path, number, line)
            _append_po_continuation(entry, name, index, value)
            continue
        raise ValueError(f"{path}:{number}: unsupported or malformed PO syntax")
    finish()
    if not entries or entries[0].msgid != "":
        raise ValueError(f"{path}: missing gettext header entry")
    return entries

def _validate_po(path: Path) -> None:
    executable = shutil.which("msgfmt")
    if not executable:
        raise ValueError("GNU gettext msgfmt is required for catalog validation")
    result = subprocess.run(
        [executable, "--check", "-o", "/dev/null", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"msgfmt --check failed for {path}: {detail}")


class CatalogLookup:
    """Resolve one message from the requested addon's validated locale catalog."""

    def __init__(self, addons_root: Path, language: str | None):
        self.addons_root = Path(addons_root)
        self.language = language
        self._catalogs: dict[tuple[str, str], tuple[Path, list[_Entry]]] = {}

    def translate(
        self,
        module: str,
        msgid: str,
        *,
        context: str | None = None,
        plural_index: int | None = None,
    ) -> str:
        """Return source text without a locale, otherwise require a catalog match."""
        if self.language is None:
            return msgid
        key = module, self.language
        if key not in self._catalogs:
            directory = self.addons_root / module
            if not directory.is_dir():
                raise ValueError(f"addon not found: {directory}")
            language_code = self.language.replace("-", "_").split("_", 1)[0]
            path = directory / "i18n" / f"{language_code}.po"
            if not path.is_file():
                raise ValueError(f"catalog for locale {self.language!r} not found: {path}")
            _validate_po(path)
            self._catalogs[key] = path, _parse_po(path)
        path, entries = self._catalogs[key]
        matches = [
            item
            for item in entries
            if item.msgid == msgid
            and (item.plural is not None or item.msgid != "")
            and (context is None or item.context == context)
        ]
        if context is None and len({item.context for item in matches}) > 1:
            raise ValueError(f"{module}/{self.language}: {msgid!r} is ambiguous in {path}; pass context")
        if len(matches) != 1:
            raise ValueError(
                f"{module}/{self.language}: expected one catalog entry for {msgid!r} in {path}, "
                f"found {len(matches)}"
            )
        entry = matches[0]
        if entry.plural is not None and plural_index is None:
            raise ValueError(f"{module}/{self.language}: {msgid!r} is plural in {path}; pass plural_index")
        if entry.plural is None and plural_index is not None:
            raise ValueError(f"{module}/{self.language}: {msgid!r} is singular in {path}; omit plural_index")
        value = entry.translations.get(plural_index or 0, "")
        if not value.strip():
            raise ValueError(
                f"{module}/{self.language}: empty translation for {entry.context or '<no context>'}: "
                f"{msgid!r} in {path}"
            )
        return value
