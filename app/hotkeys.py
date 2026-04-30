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


def _toggle_overlay() -> None:
    cfg = settings()
    cfg.overlay_enabled = not cfg.overlay_enabled
    cfg.save()
    bus.overlay_visibility_changed.emit(cfg.overlay_enabled)


def setup() -> None:
    if keyboard is None:
        log.warning("`keyboard` package unavailable; global hotkeys disabled.")
        return

    cfg = settings()
    bindings = [
        (cfg.analysis_hotkey, lambda: threading.Thread(
            target=trigger_analysis, daemon=True
        ).start(), "analyse"),
        (cfg.toggle_overlay_hotkey, _toggle_overlay, "toggle overlay"),
        (cfg.spotlight_hotkey, bus.spotlight_requested.emit, "spotlight"),
        (cfg.stealth_hotkey, bus.stealth_toggle_requested.emit, "stealth"),
        (cfg.quit_hotkey, bus.quit_requested.emit, "quit"),
    ]
    registered = []
    for hk, fn, label in bindings:
        if not hk:
            continue
        try:
            keyboard.add_hotkey(hk, fn)
            registered.append(f"{hk}={label}")
        except Exception:  # noqa: BLE001 — registration may need elevated perms.
            log.exception("Could not register hotkey %r", hk)

    if registered:
        log.info("Hotkeys: %s", ", ".join(registered))
    else:
        log.warning("No global hotkeys registered.")
