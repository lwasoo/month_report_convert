"""Persistent user preferences for update checks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .defaults import APP_NAME


def update_preferences_path() -> Path:
    override = os.environ.get("FILE_TOOLBOX_UPDATE_PREFS_PATH", "").strip()
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME / "update_preferences.json"


def load_update_preferences() -> dict[str, object]:
    path = update_preferences_path()
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_update_preferences(preferences: dict[str, object]) -> None:
    path = update_preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")


def is_auto_update_check_enabled() -> bool:
    return not bool(load_update_preferences().get("skip_auto_update_check"))


def set_auto_update_check_enabled(enabled: bool) -> None:
    preferences = load_update_preferences()
    if enabled:
        preferences.pop("skip_auto_update_check", None)
    else:
        preferences["skip_auto_update_check"] = True
    save_update_preferences(preferences)
