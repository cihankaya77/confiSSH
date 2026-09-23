"""Small, dependency-free localization layer for ConfiSSH."""
from __future__ import annotations

import json
import os
from pathlib import Path


SUPPORTED_LANGUAGES = ("system", "en", "tr")
_catalog: dict[str, str] = {}
_language = "en"


def _system_language() -> str:
    for variable in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(variable, "").split(".", 1)[0].split("@", 1)[0]
        if value.lower().startswith("tr"):
            return "tr"
    return "en"


def set_language(language: str) -> str:
    """Select a language and return the resolved language code."""
    global _catalog, _language
    requested = language if language in SUPPORTED_LANGUAGES else "system"
    _language = _system_language() if requested == "system" else requested
    _catalog = {}
    if _language != "en":
        path = Path(__file__).parent / "resources" / "locales" / f"{_language}.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _catalog = {str(key): str(value) for key, value in loaded.items()}
        except (OSError, ValueError, TypeError):
            _language = "en"
    return _language


def get_language() -> str:
    return _language


def translate(message: str) -> str:
    return _catalog.get(message, message)


def ntranslate(singular: str, plural: str, count: int) -> str:
    message = singular if count == 1 else plural
    return translate(message)


_ = translate
ngettext = ntranslate
set_language("en")
