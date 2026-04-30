"""Application entry point. Wires server, overlay, dashboard, tray, hotkeys."""

from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from . import APP_NAME
from .dashboard import Dashboard, make_logo_icon
from .hotkeys import setup as setup_hotkeys
from .overlay import install as install_overlay
from .server import start_in_background
from .state import bus
from .tray import install as install_tray


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()
    log = logging.getLogger("lumen")

    # Start the caption server before Qt — it's pure background.
    start_in_background()

    # Qt high-DPI scaling defaults on PyQt6 are good; just construct the app.
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # tray keeps app alive
    app.setWindowIcon(make_logo_icon(64))

    # Use Segoe UI on Windows, fall back gracefully elsewhere.
    app.setFont(QFont("Segoe UI Variable", 9))

    overlay = install_overlay(app)  # noqa: F841 — kept alive by closure
    dashboard = Dashboard()
    dashboard.show()

    tray = install_tray(app, dashboard)  # noqa: F841

    setup_hotkeys()
    bus.quit_requested.connect(app.quit)

    log.info("Lumen ready. Tray: %s.", "yes" if tray else "no tray (falling back)")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
