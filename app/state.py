"""Process-wide signals & shared state, all Qt-thread-safe."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class CaptionEvent:
    speaker: str
    text: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AnalysisEvent:
    mode: str
    raw_html: str
    plain_summary: str
    timestamp: datetime = field(default_factory=datetime.now)


class Bus(QObject):
    """All cross-thread communication funnels through here."""

    # Overlay updates: (html, auto_clear_seconds). 0 = persist.
    overlay_update = pyqtSignal(str, int)
    # Tells the overlay to fade away to a blank state.
    overlay_blank = pyqtSignal()

    # Dashboard live feed.
    caption_received = pyqtSignal(object)  # CaptionEvent
    analysis_completed = pyqtSignal(object)  # AnalysisEvent
    status_changed = pyqtSignal(str, str)    # level (info|warn|error), message

    # Lifecycle.
    quit_requested = pyqtSignal()
    overlay_visibility_changed = pyqtSignal(bool)
    settings_changed = pyqtSignal()


# Module-level singletons.
bus = Bus()

# Held while an analysis is on screen so live captions don't overwrite it.
analysis_lock = threading.Lock()


def is_analyzing() -> bool:
    return analysis_lock.locked()
