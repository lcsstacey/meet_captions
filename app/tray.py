"""System tray integration."""

from __future__ import annotations

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME
from .ai import trigger_analysis
from .config import settings
from .dashboard import Dashboard, make_logo_icon
from .state import bus


def install(app: QApplication, dashboard: Dashboard) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(make_logo_icon(64), parent=app)
    tray.setToolTip(APP_NAME)

    menu = QMenu()

    open_act = QAction("Open dashboard", menu)
    open_act.triggered.connect(lambda: (dashboard.showNormal(), dashboard.raise_(), dashboard.activateWindow()))
    menu.addAction(open_act)

    menu.addSeparator()

    analyse_act = QAction("Analyse now", menu)
    analyse_act.triggered.connect(lambda: trigger_analysis())
    menu.addAction(analyse_act)

    toggle_act = QAction("Toggle overlay", menu, checkable=True)
    toggle_act.setChecked(settings().overlay_enabled)

    def _on_toggle(checked: bool) -> None:
        cfg = settings()
        cfg.overlay_enabled = checked
        cfg.save()
        bus.overlay_visibility_changed.emit(checked)

    toggle_act.toggled.connect(_on_toggle)
    bus.overlay_visibility_changed.connect(toggle_act.setChecked)
    menu.addAction(toggle_act)

    menu.addSeparator()

    quit_act = QAction("Quit Lumen", menu)
    quit_act.triggered.connect(bus.quit_requested.emit)
    menu.addAction(quit_act)

    tray.setContextMenu(menu)

    def _on_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if dashboard.isVisible():
                dashboard.hide()
            else:
                dashboard.showNormal()
                dashboard.raise_()
                dashboard.activateWindow()

    tray.activated.connect(_on_activated)
    tray.show()
    return tray
