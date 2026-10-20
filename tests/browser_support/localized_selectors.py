"""Make UI browser selectors and text expectations work in translated databases."""

from __future__ import annotations

import gettext
import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import Frame, Locator, Page
from playwright.sync_api._generated import LocatorAssertions, PageAssertions


class SpanishPlaywrightLocalization:
    """Accept English test copy and its shipped Spanish translation in UI checks."""

    def __init__(self, addon_paths: list[Path]):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="meeting-es-translations-")
        self.translations: dict[str, str] = {}
        for index, addon_path in enumerate(addon_paths):
            catalog = addon_path / "i18n" / "es.po"
            if not catalog.is_file():
                continue
            compiled = Path(self.temp_dir.name) / f"{index}.mo"
            subprocess.run(
                ["msgfmt", "--check", "-o", str(compiled), str(catalog)],
                check=True,
                capture_output=True,
                text=True,
            )
            with compiled.open("rb") as stream:
                translation = gettext.GNUTranslations(stream)
            # GNUTranslations does not expose all entries, so walk the parsed
            # catalog's message table; this is also what the UI bundles use.
            for key, value in translation._catalog.items():
                if isinstance(key, str) and isinstance(value, str) and value:
                    self.translations[key] = value
        self.translations.update(
            {
                "are not resolved": "no están resueltos",
                "agenda point(s) are not resolved": "punto(s) de la agenda no están resueltos",
                "Why reopen this point?": "¿Por qué reabrir este punto?",
                "Add a line": "Añadir una línea",
                "Email": "Correo electrónico",
            }
        )
        self.patchers = []
        self._install()

    def _translated(self, value, exact=None):
        def escaped(text):
            return re.escape(text).replace("/", r"\/")

        if isinstance(value, str):
            translated = self.translations.get(value)
            if not translated and value.startswith("Related: "):
                translated = self.translations.get("Related", "Relacionado") + value[
                    len("Related") :
                ]
            if not translated or translated == value:
                return value
            alternatives = (escaped(value), escaped(translated))
            flags = 0
        elif isinstance(value, re.Pattern):
            raw = value.pattern
            unwrapped = raw.removeprefix("^").removesuffix("$")
            translated = self.translations.get(unwrapped)
            if not translated and raw.startswith("^"):
                prefix = raw[1:]
                translated = self.translations.get(prefix)
                if translated:
                    return re.compile(
                        r"^(?:%s|%s)" % (prefix, escaped(translated)), value.flags
                    )
            if not translated or translated == unwrapped:
                return value
            flags = value.flags
            if raw.startswith("^") and raw.endswith("$"):
                return re.compile(
                    r"^(?:%s|%s)$" % (raw[1:-1], escaped(translated)), flags
                )
            return re.compile(r"(?:%s|%s)" % (raw, escaped(translated)), flags)
        else:
            return value
        pattern = "(?:%s|%s)" % alternatives
        if exact:
            pattern = "^(?:%s)$" % pattern
        return re.compile(pattern, flags)

    def _translated_css(self, selector):
        if not isinstance(selector, str):
            return selector
        pattern = re.compile(r'\[(aria-label|title|placeholder)\s*=\s*(["\'])(.*?)\2\]')

        def replace(match):
            original = match.group(3)
            translated = self.translations.get(original)
            if not translated or translated == original:
                return match.group(0)
            attribute = match.group(1)
            quote = match.group(2)
            return (
                f':is([{attribute}={quote}{original}{quote}], '
                f'[{attribute}={quote}{translated}{quote}])'
            )

        return pattern.sub(replace, selector)

    def _kwargs(self, kwargs, key):
        if key in kwargs and kwargs[key] is not None:
            kwargs[key] = self._translated(kwargs[key], kwargs.get("exact"))
        return kwargs

    def _install(self):
        for cls in (Page, Frame, Locator):
            for method_name, key in (
                ("get_by_role", "name"),
                ("get_by_text", "text"),
                ("get_by_label", "text"),
                ("get_by_placeholder", "text"),
            ):
                original = getattr(cls, method_name)

                def localized(instance, *args, __original=original, __key=key, **kwargs):
                    if __key == "name":
                        self._kwargs(kwargs, "name")
                    elif args:
                        args = (self._translated(args[0], kwargs.get("exact")), *args[1:])
                    elif "text" in kwargs:
                        self._kwargs(kwargs, "text")
                    return __original(instance, *args, **kwargs)

                self.patchers.append(patch.object(cls, method_name, localized))

            original_locator = cls.locator

            def localized_locator(instance, selector, *args, __original=original_locator, **kwargs):
                return __original(
                    instance, self._translated_css(selector), *args, **kwargs
                )

            self.patchers.append(patch.object(cls, "locator", localized_locator))

        original_filter = Locator.filter

        def localized_filter(instance, *args, **kwargs):
            for key in ("has_text", "has_not_text"):
                if key in kwargs and kwargs[key] is not None:
                    kwargs[key] = self._translated(kwargs[key])
            return original_filter(instance, *args, **kwargs)

        self.patchers.append(patch.object(Locator, "filter", localized_filter))

        original_select_option = Locator.select_option

        def localized_select_option(instance, *args, **kwargs):
            label = kwargs.get("label")
            if isinstance(label, str):
                translated = self.translations.get(label)
                if translated and translated != label:
                    labels = {label, translated}
                    option = instance.locator("option").evaluate_all(
                        "(options, labels) => options.find((item) => labels.includes(item.label))?.value",
                        list(labels),
                    )
                    if option is not None:
                        kwargs.pop("label")
                        kwargs["value"] = option
            return original_select_option(instance, *args, **kwargs)

        self.patchers.append(
            patch.object(Locator, "select_option", localized_select_option)
        )

        for method_name in ("to_contain_text", "to_have_text"):
            original = getattr(LocatorAssertions, method_name)

            def localized_assertion(
                instance,
                expected,
                *args,
                __original=original,
                __method_name=method_name,
                **kwargs,
            ):
                if isinstance(expected, str | re.Pattern):
                    expected = self._translated(
                        expected, exact=False
                    )
                elif isinstance(expected, list):
                    expected = [self._translated(item, exact=False) for item in expected]
                return __original(instance, expected, *args, **kwargs)

            self.patchers.append(patch.object(LocatorAssertions, method_name, localized_assertion))

        original_attribute = LocatorAssertions.to_have_attribute

        def localized_attribute(instance, name, value, *args, **kwargs):
            if name in {"aria-label", "title", "placeholder"} and isinstance(value, str):
                value = self._translated(value)
            return original_attribute(instance, name, value, *args, **kwargs)

        self.patchers.append(
            patch.object(LocatorAssertions, "to_have_attribute", localized_attribute)
        )

        original_title = PageAssertions.to_have_title

        def localized_page_title(instance, expected, *args, **kwargs):
            if isinstance(expected, str | re.Pattern):
                expected = self._translated(expected)
            return original_title(instance, expected, *args, **kwargs)

        self.patchers.append(patch.object(PageAssertions, "to_have_title", localized_page_title))
        for patcher in self.patchers:
            patcher.start()

    def close(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temp_dir.cleanup()
