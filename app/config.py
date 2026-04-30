"""Persistent user settings stored as JSON next to the app."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

log = logging.getLogger("lumen.config")

ROOT_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT_DIR / "lumen_settings.json"
TRANSCRIPT_FILE = ROOT_DIR / "meet_captions.txt"
CONTEXT_FILE = ROOT_DIR / "context.txt"
HISTORY_FILE = ROOT_DIR / "lumen_history.json"


# Caption position presets, mapped to CSS flex alignment.
POSITION_PRESETS = {
    "Bottom": ("flex-end", "center", "0 0 8vh 0"),
    "Top": ("flex-start", "center", "8vh 0 0 0"),
    "Center": ("center", "center", "0"),
    "Top-Right": ("flex-start", "flex-end", "6vh 4vw 0 0"),
    "Bottom-Left": ("flex-end", "flex-start", "0 0 6vh 4vw"),
}


@dataclass
class Settings:
    # Caption display
    caption_position: str = "Bottom"
    caption_font_size: int = 32
    caption_ttl_seconds: int = 15
    show_speaker: bool = True
    color_speakers: bool = True
    glass_plate: bool = True
    accent_color: str = "#7C5CFF"   # primary brand
    caption_color: str = "#FFEB3B"  # default yellow
    speaker_color: str = "#80DEEA"

    # AI
    gemini_model: str = "gemini-2.5-flash"
    analysis_ttl_seconds: int = 30
    analysis_mode: str = "Answer"   # see ai.MODES for valid values
    max_transcript_chars: int = 16_000
    auto_answer_questions: bool = False  # auto-fire Answer when "?" detected
    last_caption_window: int = 600       # chars used as the "current question"

    # Personalisation — folded into every prompt.
    resume_text: str = ""
    role_text: str = ""
    notes_text: str = ""

    # Behaviour
    analysis_hotkey: str = "0"
    quit_hotkey: str = "ctrl+shift+q"
    toggle_overlay_hotkey: str = "ctrl+shift+o"
    spotlight_hotkey: str = "ctrl+shift+space"
    stealth_hotkey: str = "ctrl+shift+h"
    flask_host: str = "127.0.0.1"
    flask_port: int = 5000
    overlay_enabled: bool = True
    autostart_overlay: bool = True
    minimise_to_tray: bool = True

    # Coach panel — interactive, movable, persistent.
    coach_enabled: bool = True
    coach_x: int = 60
    coach_y: int = 60
    coach_w: int = 520
    coach_h: int = 360
    coach_opacity: int = 92  # 0–100

    @classmethod
    def load(cls) -> "Settings":
        if not SETTINGS_FILE.exists():
            inst = cls()
            inst.save()
            return inst
        try:
            data: dict[str, Any] = json.loads(SETTINGS_FILE.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            log.exception("Could not read %s; using defaults.", SETTINGS_FILE)
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})

    def save(self) -> None:
        try:
            SETTINGS_FILE.write_text(
                json.dumps(asdict(self), indent=2), encoding="utf-8"
            )
        except OSError:
            log.exception("Could not write %s", SETTINGS_FILE)


# Singleton accessor pattern: load once, mutate in place, save on demand.
_settings: Settings | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings
