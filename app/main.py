"""Application entry point. Wires server, overlay, coach, dashboard, tray, hotkeys."""

from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QWidget

from . import APP_NAME
from .coach import install as install_coach
from .config import settings
from .dashboard import Dashboard, make_logo_icon
from .hotkeys import setup as setup_hotkeys
from .overlay import install as install_overlay
from .server import start_in_background
from .spotlight import install as install_spotlight
from .state import bus
from .tray import install as install_tray


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


class StealthManager:
    """Hide every Lumen surface on a single hotkey, restore on the next press."""

    def __init__(self, surfaces: list[QWidget]) -> None:
        self._surfaces = surfaces
        self._was_visible: list[bool] = []
        self._hidden = False
        bus.stealth_toggle_requested.connect(self.toggle)

    def toggle(self) -> None:
        if self._hidden:
            for w, was in zip(self._surfaces, self._was_visible):
                if was:
                    w.show()
                    w.raise_()
            self._hidden = False
        else:
            self._was_visible = [w.isVisible() for w in self._surfaces]
            for w in self._surfaces:
                w.hide()
            self._hidden = True


def main() -> int:
    _configure_logging()
    log = logging.getLogger("lumen")

    start_in_background()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(make_logo_icon(64))
    app.setFont(QFont("Segoe UI Variable", 9))

    overlay = install_overlay(app)
    coach = install_coach(app)
    spotlight = install_spotlight(app)

    dashboard = Dashboard()
    dashboard.show()

    tray = install_tray(app, dashboard)

    setup_hotkeys()
    bus.quit_requested.connect(app.quit)

    # Stealth — hide every surface on demand.
    StealthManager([overlay, coach, dashboard, spotlight])

    log.info(
        "Lumen ready. Tray: %s. Coach: %s.",
        "yes" if tray else "no",
        "on" if settings().coach_enabled else "off",
    )
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
