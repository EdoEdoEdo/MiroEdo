"""
Minimal i18n: no Flask, no thread locals. Locale is a process-wide setting
(set once at startup via `set_locale(...)`) or passed explicitly.

For multi-tenant scenarios, instantiate `Locale` objects directly.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict

_LOCALES_DIR = os.path.join(os.path.dirname(__file__), "..", "locales")

_lock = threading.Lock()
_languages: Dict[str, Dict[str, str]] = {}
_translations: Dict[str, Dict[str, Any]] = {}
_default_locale = "it"


def _load() -> None:
    global _languages, _translations
    if _languages:
        return
    with _lock:
        if _languages:
            return
        with open(os.path.join(_LOCALES_DIR, "languages.json"), "r", encoding="utf-8") as f:
            _languages = json.load(f)
        for fname in os.listdir(_LOCALES_DIR):
            if fname.endswith(".json") and fname != "languages.json":
                name = fname[:-5]
                with open(os.path.join(_LOCALES_DIR, fname), "r", encoding="utf-8") as f:
                    _translations[name] = json.load(f)


_load()


def set_default_locale(locale: str) -> None:
    """Process-wide default."""
    global _default_locale
    if locale in _translations:
        _default_locale = locale


def get_locale() -> str:
    return _default_locale


def t(key: str, *, locale: str | None = None, **kwargs: Any) -> str:
    """Translate dotted key with optional placeholders."""
    loc = locale or _default_locale
    messages = _translations.get(loc) or _translations.get("en") or {}

    value: Any = messages
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    # Fallback chain: requested → en → zh → key
    if value is None and loc != "en":
        value = _walk(_translations.get("en", {}), key)
    if value is None and loc != "zh":
        value = _walk(_translations.get("zh", {}), key)
    if value is None:
        return key

    out = str(value)
    for k, v in kwargs.items():
        out = out.replace(f"{{{k}}}", str(v))
    return out


def _walk(messages: Dict[str, Any], key: str) -> Any:
    value: Any = messages
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def get_language_instruction(locale: str | None = None) -> str:
    loc = locale or _default_locale
    lang = _languages.get(loc) or _languages.get("en") or {}
    return lang.get("llmInstruction", "Please respond in English.")
