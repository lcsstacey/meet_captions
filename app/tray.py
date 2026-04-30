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

    answer_act = QAction("Answer this", menu)
    answer_act.triggered.connect(lambda: trigger_analysis("Answer"))
    menu.addAction(answer_act)

    spot_act = QAction("Spotlight…", menu)
    spot_act.triggered.connect(bus.spotlight_requested.emit)
    menu.addAction(spot_act)

    analyse_act = QAction("Run default analysis", menu)
    analyse_act.triggered.connect(lambda: trigger_analysis())
    menu.addAction(analyse_act)

    menu.addSeparator()

    toggle_act = QAction("Show captions overlay", menu, checkable=True)
    toggle_act.setChecked(settings().overlay_enabled)

    def _on_toggle(checked: bool) -> None:
        cfg = settings()
        cfg.overlay_enabled = checked
        cfg.save()
        bus.overlay_visibility_changed.emit(checked)

    toggle_act.toggled.connect(_on_toggle)
    bus.overlay_visibility_changed.connect(toggle_act.setChecked)
    menu.addAction(toggle_act)

    coach_act = QAction("Show Coach panel", menu, checkable=True)
    coach_act.setChecked(settings().coach_enabled)

    def _on_coach(checked: bool) -> None:
        cfg = settings()
        cfg.coach_enabled = checked
        cfg.save()
        bus.coach_visibility_changed.emit(checked)

    coach_act.toggled.connect(_on_coach)
    bus.coach_visibility_changed.connect(coach_act.setChecked)
    menu.addAction(coach_act)

    stealth_act = QAction("Stealth — hide everything", menu)
    stealth_act.triggered.connect(bus.stealth_toggle_requested.emit)
    menu.addAction(stealth_act)

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
