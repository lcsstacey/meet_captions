"""Transparent click-through overlay window."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

from .config import settings
from .overlay_render import BLANK_HTML, STARTUP_HTML
from .state import bus, is_analyzing

log = logging.getLogger("lumen.overlay")


class OverlayWindow(QMainWindow):
    """A frameless, click-through, always-on-top transparent surface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lumen Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.webview = QWebEngineView(self)
        self.webview.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.webview.setHtml(STARTUP_HTML)
        self.setCentralWidget(self.webview)

        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_display)

        bus.overlay_update.connect(self._on_update)
        bus.overlay_blank.connect(self._clear_display)
        bus.overlay_visibility_changed.connect(self._set_visible)

        if settings().autostart_overlay and settings().overlay_enabled:
            self.showFullScreen()

    # -- public ----------------------------------------------------------- #

    def _set_visible(self, visible: bool) -> None:
        if visible:
            self.showFullScreen()
        else:
            self.hide()

    # -- internals -------------------------------------------------------- #

    def _on_update(self, raw_html: str, auto_clear_seconds: int) -> None:
        if not settings().overlay_enabled:
            return
        if not self.isVisible():
            self.showFullScreen()
        self.webview.setHtml(raw_html)
        self._clear_timer.stop()
        if auto_clear_seconds > 0:
            self._clear_timer.start(auto_clear_seconds * 1000)

    def _clear_display(self) -> None:
        if is_analyzing():
            return
        self.webview.setHtml(BLANK_HTML)


def install(app: QApplication) -> OverlayWindow:
    win = OverlayWindow()
    app.aboutToQuit.connect(win.close)
    return win
