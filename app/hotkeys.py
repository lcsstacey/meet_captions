"""Global hotkeys, registered via the `keyboard` package."""

from __future__ import annotations

import logging
import threading

from .ai import trigger_analysis
from .config import settings
from .state import bus

log = logging.getLogger("lumen.hotkeys")

try:
    import keyboard  # type: ignore
except ImportError:  # pragma: no cover
    keyboard = None  # type: ignore[assignment]


_overlay_visible = True


def _toggle_overlay() -> None:
    global _overlay_visible
    cfg = settings()
    _overlay_visible = not _overlay_visible
    cfg.overlay_enabled = _overlay_visible
    cfg.save()
    bus.overlay_visibility_changed.emit(_overlay_visible)


def setup() -> None:
    if keyboard is None:
        log.warning("`keyboard` package unavailable; global hotkeys disabled.")
        return

    cfg = settings()
    try:
        keyboard.add_hotkey(
            cfg.analysis_hotkey,
            lambda: threading.Thread(
                target=trigger_analysis, daemon=True
            ).start(),
        )
        keyboard.add_hotkey(cfg.toggle_overlay_hotkey, _toggle_overlay)
        keyboard.add_hotkey(cfg.quit_hotkey, bus.quit_requested.emit)
        log.info(
            "Hotkeys: %s = analyse, %s = toggle overlay, %s = quit",
            cfg.analysis_hotkey,
            cfg.toggle_overlay_hotkey,
            cfg.quit_hotkey,
        )
    except Exception:  # noqa: BLE001 — registration may need elevated perms.
        log.exception(
            "Could not register global hotkeys "
            "(on macOS/Linux you may need to run with sudo)."
        )
