"""Spotlight — a small frameless input bar for ad-hoc questions.

Triggered via the spotlight hotkey. The user types a question; we send it to
Gemini together with the current transcript and personal context, and route
the answer to the coach panel.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .ai import trigger_analysis
from .config import settings
from .state import bus


class Spotlight(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(620, 120)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        card = QFrame()
        card.setObjectName("SpotCard")
        card.setStyleSheet(self._stylesheet())
        outer.addWidget(card)

        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(60)
        sh.setOffset(0, 18)
        sh.setColor(QColor(0, 0, 0, 220))
        card.setGraphicsEffect(sh)

        body = QVBoxLayout(card)
        body.setContentsMargins(20, 16, 20, 16)
        body.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        icon = QLabel("✦")
        icon.setObjectName("SpotIcon")
        title = QLabel("Ask Lumen")
        title.setObjectName("SpotTitle")
        hint = QLabel("Esc to dismiss")
        hint.setObjectName("SpotHint")
        head.addWidget(icon)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(hint)
        body.addLayout(head)

        self._input = QLineEdit()
        self._input.setObjectName("SpotInput")
        self._input.setPlaceholderText(
            "Ask anything — the live transcript and your context are included…"
        )
        self._input.returnPressed.connect(self._submit)
        body.addWidget(self._input)

        bus.spotlight_requested.connect(self._open)

    # ------------------------------------------------------------------ open
    def _open(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - self.width() // 2,
                geom.top() + int(geom.height() * 0.22),
            )
        self._input.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(50, self._input.setFocus)

    # ----------------------------------------------------------------- close
    def keyPressEvent(self, e):  # type: ignore[override]
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(e)

    def _submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        trigger_analysis(custom_prompt=text)
        self.hide()

    # ----------------------------------------------------------------- style
    def _stylesheet(self) -> str:
        accent = settings().accent_color
        return f"""
        QFrame#SpotCard {{
            background: rgba(15,17,24,0.96);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 18px;
        }}
        QLabel#SpotIcon {{ color: {accent}; font-size: 18px; }}
        QLabel#SpotTitle {{ color: #fff; font-size: 14px; font-weight: 700;
                            letter-spacing: 0.3px; }}
        QLabel#SpotHint {{ color: #6A7185; font-size: 11px; }}
        QLineEdit#SpotInput {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            color: #fff; font-size: 16px;
            padding: 12px 14px;
            selection-background-color: {accent};
        }}
        QLineEdit#SpotInput:focus {{ border-color: {accent}; }}
        """


def install(app: QApplication) -> Spotlight:
    s = Spotlight()
    app.aboutToQuit.connect(s.close)
    return s
